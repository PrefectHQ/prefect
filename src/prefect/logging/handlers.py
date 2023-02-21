import atexit
import json
import logging
import queue
import sys
import threading
import time
import traceback
import warnings
from typing import Any, Dict, List, Tuple, Union

import anyio
import pendulum
from rich.console import Console
from rich.highlighter import Highlighter, NullHighlighter
from rich.theme import Theme

import prefect.context
from prefect._internal.compatibility.deprecated import deprecated_callable
from prefect.client.orchestration import get_client
from prefect.exceptions import MissingContextError
from prefect.logging.highlighters import PrefectConsoleHighlighter
from prefect.server.schemas.actions import LogCreate
from prefect.settings import (
    PREFECT_LOGGING_COLORS,
    PREFECT_LOGGING_MARKUP,
    PREFECT_LOGGING_TO_API_BATCH_INTERVAL,
    PREFECT_LOGGING_TO_API_BATCH_SIZE,
    PREFECT_LOGGING_TO_API_ENABLED,
    PREFECT_LOGGING_TO_API_MAX_LOG_SIZE,
    PREFECT_LOGGING_TO_API_WHEN_MISSING_FLOW,
)


class APILogWorker:
    """
    Manages the submission of logs to the API in a background thread.
    """

    def __init__(self, profile_context: prefect.context.SettingsContext) -> None:
        self.profile_context = profile_context.copy()

        self._queue: queue.Queue[Tuple[Dict[str, Any], int]] = queue.Queue()

        self._send_thread = threading.Thread(
            target=self._send_logs_loop,
            name="orion-log-worker",
            daemon=True,
        )
        self._flush_event = threading.Event()
        self._stop_event = threading.Event()
        self._send_logs_finished_event = threading.Event()
        self._lock = threading.Lock()
        self._started = False
        self._stopped = False  # Cannot be started again after stopped

        # Tracks logs that have been pulled from the queue but not sent successfully
        self._pending_logs: List[dict] = []
        self._pending_size: int = 0
        self._retries = 0
        self._max_retries = 3

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
        # Initialize prefect in this new thread, but do not reconfigure logging
        try:
            with self.profile_context:
                while not self._stop_event.is_set():
                    # Wait until flush is called or the batch interval is reached
                    self._flush_event.wait(
                        PREFECT_LOGGING_TO_API_BATCH_INTERVAL.value()
                    )
                    self._flush_event.clear()

                    anyio.run(self.send_logs)

                    # Notify watchers that logs were sent
                    self._send_logs_finished_event.set()
                    self._send_logs_finished_event.clear()

                # After the stop event, we are exiting...
                # Try to send any remaining logs
                anyio.run(self.send_logs, True)

        except Exception:
            if logging.raiseExceptions and sys.stderr:
                sys.stderr.write("--- Error logging to API ---\n")
                sys.stderr.write("The log worker encountered a fatal error.\n")
                traceback.print_exc(file=sys.stderr)
                sys.stderr.write(self.worker_info())

        finally:
            # Set the finished event so anyone waiting on worker completion does not
            # continue to block if an exception is encountered
            self._send_logs_finished_event.set()

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
            PREFECT_LOGGING_TO_API_BATCH_SIZE.value()
            - PREFECT_LOGGING_TO_API_MAX_LOG_SIZE.value(),
            PREFECT_LOGGING_TO_API_MAX_LOG_SIZE.value(),
        )

        # Loop until the queue is empty or we encounter an error
        while not done:
            # Pull logs from the queue until it is empty or we reach the batch size
            try:
                while self._pending_size < max_batch_size:
                    log, log_size = self._queue.get_nowait()
                    self._pending_logs.append(log)
                    self._pending_size += log_size

            except queue.Empty:
                done = True

            if not self._pending_logs:
                continue

            client = get_client()
            client.manage_lifespan = False
            async with client:
                try:
                    await client.create_logs(self._pending_logs)
                    self._pending_logs = []
                    self._pending_size = 0
                    self._retries = 0
                except Exception:
                    # Attempt to send these logs on the next call instead
                    done = True
                    self._retries += 1

                    # Roughly replicate the behavior of the stdlib logger error handling
                    if logging.raiseExceptions and sys.stderr:
                        sys.stderr.write("--- Error logging to API ---\n")
                        traceback.print_exc(file=sys.stderr)
                        sys.stderr.write(self.worker_info())
                        if exiting:
                            sys.stderr.write(
                                "The log worker is stopping and these logs will not be"
                                " sent.\n"
                            )
                        elif self._retries > self._max_retries:
                            sys.stderr.write(
                                "The log worker has tried to send these logs "
                                f"{self._retries} times and will now drop them."
                            )
                        else:
                            sys.stderr.write(
                                "The log worker will attempt to send these logs"
                                " again in "
                                f"{PREFECT_LOGGING_TO_API_BATCH_INTERVAL.value()}s\n"
                            )

                    if self._retries > self._max_retries:
                        # Drop this batch of logs
                        self._pending_logs = []
                        self._pending_size = 0
                        self._retries = 0

    def worker_info(self) -> str:
        """Returns a debugging string with worker log stats"""
        return (
            "Worker information:\n"
            f"    Approximate queue length: {self._queue.qsize()}\n"
            f"    Pending log batch length: {len(self._pending_logs)}\n"
            f"    Pending log batch size: {self._pending_size}\n"
        )

    def enqueue(self, log: Dict[str, Any], log_size: int):
        if self._stopped:
            raise RuntimeError(
                "Logs cannot be enqueued after the API log worker is stopped."
            )
        self._queue.put((log, log_size))

    def flush(self, block: bool = False) -> None:
        with self._lock:
            if not self._started and not self._stopped:
                raise RuntimeError("Worker was never started.")
            self._flush_event.set()
            if block:
                # TODO: Sometimes the log worker will deadlock and never finish
                #       so we will only block for 30 seconds here. When logging is
                #       refactored, this deadlock should be resolved.
                self._send_logs_finished_event.wait(30)

    def start(self) -> None:
        """Start the background thread"""
        with self._lock:
            if not self._started and not self._stopped:
                self._send_thread.start()
                self._started = True
            elif self._stopped:
                raise RuntimeError(
                    "The API log worker cannot be started after stopping."
                )

    def stop(self) -> None:
        """Flush all logs and stop the background thread"""
        with self._lock:
            if self._started:
                self._flush_event.set()
                self._stop_event.set()
                self._send_thread.join()
                self._started = False
                self._stopped = True

    def is_stopped(self) -> bool:
        with self._lock:
            return not self._stopped


class APILogHandler(logging.Handler):
    """
    A logging handler that sends logs to the Prefect API.

    Sends log records to the `APILogWorker` which manages sending batches of logs in
    the background.
    """

    workers: Dict[prefect.context.SettingsContext, APILogWorker] = {}

    def get_worker(self, context: prefect.context.SettingsContext) -> APILogWorker:
        if context not in self.workers:
            worker = self.workers[context] = APILogWorker(context)
            worker.start()

        return self.workers[context]

    @classmethod
    def flush(cls, block: bool = False):
        """
        Tell the `APILogWorker` to send any currently enqueued logs.

        Blocks until enqueued logs are sent if `block` is set.
        """
        for worker in cls.workers.values():
            worker.flush(block)

    def emit(self, record: logging.LogRecord):
        """
        Send a log to the `APILogWorker`
        """
        try:
            profile = prefect.context.get_settings_context()

            if not PREFECT_LOGGING_TO_API_ENABLED.value_from(profile.settings):
                return  # Respect the global settings toggle
            if not getattr(record, "send_to_orion", True):
                return  # Do not send records that have opted out

            log, log_size = self.prepare(record, profile.settings)
            self.get_worker(profile).enqueue(log, log_size)
        except Exception:
            self.handleError(record)

    def handleError(self, record: logging.LogRecord) -> None:
        _, exc, _ = sys.exc_info()

        if isinstance(exc, MissingContextError):
            log_handling_when_missing_flow = (
                PREFECT_LOGGING_TO_API_WHEN_MISSING_FLOW.value()
            )
            if log_handling_when_missing_flow == "warn":
                # Warn when a logger is used outside of a run context, the stack level here
                # gets us to the user logging call
                warnings.warn(str(exc), stacklevel=8)
                return
            elif log_handling_when_missing_flow == "ignore":
                return
            else:
                raise exc

        # Display a longer traceback for other errors
        return super().handleError(record)

    def prepare(
        self, record: logging.LogRecord, settings: prefect.settings.Settings
    ) -> Tuple[Dict[str, Any], int]:
        """
        Convert a `logging.LogRecord` to the API `LogCreate` schema and serialize.

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
            except MissingContextError:
                raise MissingContextError(
                    f"Logger {record.name!r} attempted to send logs to the API without"
                    " a flow run id. The API log handler can only send logs within"
                    " flow run contexts unless the flow run id is manually provided."
                ) from None

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
            message=self.format(record),
        ).dict(json_compatible=True)

        log_size = self.get_log_size(log)
        if log_size > PREFECT_LOGGING_TO_API_MAX_LOG_SIZE.value():
            raise ValueError(
                f"Log of size {log_size} is greater than the max size of "
                f"{PREFECT_LOGGING_TO_API_MAX_LOG_SIZE.value()}"
            )

        return (log, log_size)

    def close(self) -> None:
        """
        Shuts down this handler and the flushes the `APILogWorkers`
        """
        for worker in self.workers.values():
            # Flush instead of closing ecause another instance may be using the worker
            worker.flush()

        return super().close()

    def get_log_size(self, log: Dict[str, Any]) -> int:
        return len(json.dumps(log).encode())


class PrefectConsoleHandler(logging.StreamHandler):
    def __init__(
        self,
        stream=None,
        highlighter: Highlighter = PrefectConsoleHighlighter,
        styles: Dict[str, str] = None,
        level: Union[int, str] = logging.NOTSET,
    ):
        """
        The default console handler for Prefect, which highlights log levels,
        web and file URLs, flow and task (run) names, and state types in the
        local console (terminal).

        Highlighting can be toggled on/off with the PREFECT_LOGGING_COLORS setting.
        For finer control, use logging.yml to add or remove styles, and/or
        adjust colors.
        """
        super().__init__(stream=stream)

        styled_console = PREFECT_LOGGING_COLORS.value()
        markup_console = PREFECT_LOGGING_MARKUP.value()
        if styled_console:
            highlighter = highlighter()
            theme = Theme(styles, inherit=False)
        else:
            highlighter = NullHighlighter()
            theme = Theme(inherit=False)

        self.level = level
        self.console = Console(
            highlighter=highlighter,
            theme=theme,
            file=self.stream,
            markup=markup_console,
        )

    def emit(self, record: logging.LogRecord):
        try:
            message = self.format(record)
            self.console.print(message, soft_wrap=True)
        except RecursionError:
            # This was copied over from logging.StreamHandler().emit()
            # https://bugs.python.org/issue36272
            raise
        except Exception:
            self.handleError(record)


@deprecated_callable(start_date="Feb 2023", help="Use `APILogHandler` instead.")
class OrionHandler(APILogHandler):
    """
    Deprecated. Use `APILogHandler` instead.
    """


@deprecated_callable(start_date="Feb 2023", help="Use `APILogWorker` instead.")
class OrionLogWorker(APILogWorker):
    """
    Deprecated. Use `APILogWorker` instead.
    """
