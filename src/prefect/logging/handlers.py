import atexit
import logging
import logging.handlers
import queue
import sys
import threading
import time
import traceback
from typing import List

import anyio
import pendulum

import prefect

from prefect.orion.schemas.actions import LogCreate
from prefect.client import OrionClient


class OrionLogWorker:
    """
    Manages the submission of logs to Orion in a background thread.
    """

    def __init__(self) -> None:
        self._queue: queue.Queue[dict] = queue.Queue()
        self._send_thread = threading.Thread(
            target=self._send_logs_loop,
            name="orion-log-worker",
            daemon=True,
        )
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._started = False

        # Tracks logs that have been pulled from the queue but not sent successfully
        self._pending_logs: List[dict] = []
        self._pending_size: int = 0

        # Ensure stop is called at exit
        if sys.version_info < (3, 9):
            atexit.register(self.stop)
        else:
            # See related issue at https://bugs.python.org/issue42647
            # The http client uses a thread pool executor to make requests and in 3.9+
            # new threads cannot be spawned after the interpreter finalizes threads
            # which happens _before_ the normal `atexit` hook is called resulting in
            # the failure to send logs.
            from threading import _register_atexit

            _register_atexit(self.stop)

    def _send_logs_loop(self):
        """
        Should only be the target of the `send_thread` as it creates a new event loop.

        Runs until the `stop_event` is set.
        """
        while not self._stop_event.wait(prefect.settings.logging.orion.batch_interval):
            anyio.run(self.send_logs)

        # After the stop event, we are exiting...
        # Try to send any remaining logs
        anyio.run(self.send_logs, True)

    async def send_logs(self, exiting: bool = False) -> None:
        """
        Send all logs in the queue in batches to avoid network limits.

        If a client error is encountered, the logs pulled from the queue are retained
        and will be sent on the next call.

        Note that if there is a single bad log in the queue, this will repeatedly
        fail as we do not ever drop logs. We may want to adjust this behavior in the
        future if there are issues.
        """
        done = False

        # Determine the batch size by removing the max size of a single log to avoid
        # exceeding the max size in normal operation. If the single log size is greater
        # than this difference, we use that instead so logs will still be sent.
        max_batch_size = max(
            prefect.settings.logging.orion.batch_size
            - prefect.settings.logging.orion.max_log_size,
            prefect.settings.logging.orion.max_log_size,
        )

        # Loop until the queue is empty or we encounter an error
        while not done:

            # Pull logs from the queue until it is empty or we reach the batch size
            try:
                while self._pending_size < max_batch_size:
                    log = self._queue.get_nowait()
                    self._pending_logs.append(log)
                    self._pending_size += sys.getsizeof(log)

            except queue.Empty:
                done = True

            if not self._pending_logs:
                continue

            async with OrionClient() as client:
                try:
                    await client.create_logs(self._pending_logs)
                    self._pending_logs = []
                    self._pending_size = 0
                except Exception:
                    # Attempt to send these logs on the next call instead
                    done = True

                    # Roughly replicate the behavior of the stdlib logger error handling
                    if logging.raiseExceptions and sys.stderr:
                        sys.stderr.write("--- Orion logging error ---\n")
                        traceback.print_exc(file=sys.stderr)
                        sys.stderr.write(self.worker_info())
                        if exiting:
                            sys.stderr.write(
                                "The log worker is stopping and these logs will not be sent.\n"
                            )
                        else:
                            sys.stderr.write(
                                "The log worker will attempt to send these logs again in "
                                f"{prefect.settings.logging.orion.batch_interval}s\n"
                            )

    def worker_info(self) -> str:
        """Returns a debugging string with worker log stats"""
        return (
            "Worker information:\n"
            f"    Approximate queue length: {self._queue.qsize()}\n"
            f"    Pending log batch length: {len(self._pending_logs)}\n"
            f"    Pending log batch size: {self._pending_size}\n"
        )

    def enqueue(self, log: LogCreate):
        self._queue.put(log)

    def start(self) -> None:
        """Start the background thread"""
        with self._lock:
            if not self._started:
                self._send_thread.start()
                self._started = True

    def stop(self) -> None:
        """Flush all logs and stop the background thread"""
        with self._lock:
            if self._started:
                self._stop_event.set()
                self._send_thread.join()
                self._started = False


class OrionHandler(logging.Handler):
    """
    A logging handler that sends logs to the Orion API.

    Sends log records to the `OrionLogWorker` which manages sending batches of logs in
    the background.
    """

    worker: OrionLogWorker = None

    @classmethod
    def get_worker(cls) -> OrionLogWorker:
        if not cls.worker:
            cls.worker = OrionLogWorker()
            cls.worker.start()
        return cls.worker

    @classmethod
    def flush(cls):
        """
        Tell the `OrionLogWorker` to send any currently enqueued logs.

        Blocks until enqueued logs are sent.
        """
        if cls.worker:
            cls.worker.stop()

    def emit(self, record: logging.LogRecord):
        """
        Send a log to the `OrionLogWorker`
        """
        try:
            if not prefect.settings.logging.orion.enabled:
                return  # Respect the global settings toggle
            if not getattr(record, "send_to_orion", True):
                return  # Do not send records that have opted out
            self.get_worker().enqueue(self.prepare(record))
        except Exception:
            self.handleError(record)

    def prepare(self, record: logging.LogRecord) -> LogCreate:
        """
        Convert a `logging.LogRecord` to the Orion `LogCreate` schema and serialize.

        This infers the linked flow or task run from the log record or the current
        run context.

        If a flow run id cannot be found, the log will be dropped.

        Logs exceeding the maximum size will be dropped.
        """
        flow_run_id = getattr(record, "flow_run_id", None)
        task_run_id = getattr(record, "task_run_id", None)

        if not flow_run_id:
            try:
                context = prefect.context.get_run_context()
            except:
                raise RuntimeError(
                    "Attempted to send logs to Orion without a flow run id. The "
                    "Orion log handler must be attached to loggers used within flow "
                    "run contexts or the flow run id must be manually provided."
                )

            if hasattr(context, "flow_run"):
                flow_run_id = context.flow_run.id
            elif hasattr(context, "task_run"):
                flow_run_id = context.task_run.flow_run_id
                task_run_id = task_run_id or context.task_run.id
            else:
                raise ValueError(
                    "Encountered malformed run context. Does not contain flow or task "
                    "run information."
                )

        # Parsing to a `LogCreate` object here gives us nice parsing error messages
        # from the standard lib `handleError` method if something goes wrong and
        # prevents malformed logs from entering the queue
        log = LogCreate(
            flow_run_id=flow_run_id,
            task_run_id=task_run_id,
            name=record.name,
            level=record.levelno,
            timestamp=pendulum.from_timestamp(
                getattr(record, "created", None) or time.time()
            ),
            message=record.getMessage(),
        ).dict(json_compatible=True)

        log_size = sys.getsizeof(log)
        if log_size > prefect.settings.logging.orion.max_log_size:
            raise ValueError(
                f"Log of size {log_size} is greater than the max size of "
                f"{prefect.settings.logging.orion.max_log_size}"
            )

        return log

    def close(self) -> None:
        """
        Shuts down this handler and the `OrionLogWorker`.
        """
        if self.worker:
            self.worker.stop()
        return super().close()
