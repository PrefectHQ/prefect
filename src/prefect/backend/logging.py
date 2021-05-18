import atexit
import logging

import logging.config
import sys
import threading
import time
import warnings
from queue import Empty, Queue
from typing import Any, List, Optional

import pendulum

from prefect.utilities.context import context


MAX_LOG_LENGTH = 1_000_000  # 1 MB - max length of a single log message
MAX_BATCH_LOG_LENGTH = 20_000_000  # 20 MB - max total batch size for log messages


class LogManager:
    """A global log manager for managing all logs to be sent to Prefect"""

    def __init__(self) -> None:
        self.queue = Queue()  # type: Queue[dict]
        self.pending_logs = []  # type: List[dict]
        self.thread = None  # type: Optional[threading.Thread]
        self.client = None  # type: Optional[prefect.Client]
        self.pending_length = 0
        self._stopped = threading.Event()

    def ensure_started(self) -> None:
        """Ensure the log manager is started"""
        if self.thread is None:
            self.client = prefect.Client()
            self.logging_period = context.config.cloud.logging_heartbeat
            self.thread = threading.Thread(
                target=self._write_logs_loop,
                name="prefect-log-manager",
                daemon=True,
            )
            self.thread.start()
            atexit.register(self._on_shutdown)

    def _on_shutdown(self) -> None:
        """Called via atexit, flushes all logs and stops the background thread"""
        # Sometimes a signal can hit the process at shutdown multiple times,
        # interrupting an active shutdown hook. To give a better chance of the
        # shutdown hook succeeding, we retry a few times, ignoring extra
        # `SystemExit` exceptions raised here. Note that this won't prevent
        # shutdown (the interpreter is already shutting down regardless).
        for _ in range(3):
            try:
                self.stop()
                return
            except SystemExit:
                pass

    def stop(self) -> None:
        """Flush all logs and stop the background thread"""
        if self.thread is not None:
            self._stopped.set()
            self.thread.join()
            self._write_logs()
            self.thread = None
            self.client = None

    def _write_logs_loop(self) -> None:
        """Runs in a background thread, uploads logs periodically in a loop"""
        while not self._stopped.wait(self.logging_period):
            self._write_logs()

    def _write_logs(self) -> None:
        """Upload logs in batches until the queue is empty"""
        assert self.client is not None  # mypy

        # Read all logs from the queue into the `pending_logs` list. This
        # is stored on the manager to ensure that logs aren't dropped in
        # the case of an upload error, and will be retried later. This
        # could be due to an api error, or due to a shutdown signal
        # interrupting a log upload.
        #
        # We batch uploads with a max total length to prevent uploading too
        # large a payload at once. This call will continue to loop until
        # the queue is empty or an error occurs on upload (usually only one
        # iteration is sufficient)
        cont = True
        while cont:
            try:
                while self.pending_length < MAX_BATCH_LOG_LENGTH:
                    log = self.queue.get_nowait()
                    self.pending_length += len(log.get("message", ""))
                    self.pending_logs.append(log)
            except Empty:
                cont = False

            if self.pending_logs:
                try:
                    self.client.write_run_logs(self.pending_logs)
                    self.pending_logs = []
                    self.pending_length = 0
                except Exception as exc:
                    # An error occurred on upload, warn and exit the loop (will
                    # retry later)
                    warnings.warn(f"Failed to write logs with error: {exc!r}")
                    cont = False

    def enqueue(self, message: dict) -> None:
        """Enqueue a new log message to be uploaded.

        Args:
            - message (dict): a log message to upload.
        """
        self.ensure_started()
        self.queue.put(message)


class CloudHandler(logging.Handler):
    """A handler for sending logs to the prefect API"""

    def emit(self, record: logging.LogRecord) -> None:  # type: ignore
        """Emit a new log"""
        # if we shouldn't log to cloud, don't emit
        if not context.config.logging.log_to_cloud:
            return

        # ensures emitted logs respect configured logging level
        config_level = getattr(logging, context.config.logging.level, logging.INFO)

        if record.levelno < config_level:
            return

        msg = self.format(record)
        if len(msg) > MAX_LOG_LENGTH:
            get_logger("prefect.logging").warning(
                "Received a log message of %d bytes, exceeding the limit of %d. "
                "The output will be truncated",
                len(msg),
                MAX_LOG_LENGTH,
            )
            msg = msg[:MAX_LOG_LENGTH]

        log = {
            "flow_run_id": context.get("flow_run_id"),
            "task_run_id": context.get("task_run_id"),
            "timestamp": pendulum.from_timestamp(
                getattr(record, "created", None) or time.time()
            ).isoformat(),
            "name": getattr(record, "name", None),
            "level": getattr(record, "levelname", None),
            "message": msg,
        }
        LOG_MANAGER.enqueue(log)


LOG_MANAGER = LogManager()
