"""
Utility functions for interacting with and configuring logging.  The main entrypoint for
retrieving loggers for customization is the `get_logger` utility.

Note that Prefect Tasks come equipped with their own loggers.  These can be accessed via:
    - `self.logger` if implementing a Task class
    - `prefect.context.get("logger")` if using the `task` decorator

When running locally, log levels and message formatting are set via your Prefect configuration file.
"""
import atexit
import logging
import sys
import threading
import time
import warnings
from queue import Empty, Queue
from typing import Any, List, Optional

import pendulum

import prefect
from prefect.utilities.context import context

_original_log_record_factory = logging.getLogRecordFactory()

PREFECT_LOG_RECORD_ATTRIBUTES = (
    "flow_name",
    "flow_run_id",
    "task_name",
    "task_slug",
    "task_run_id",
)

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
        self._stopped = False

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
            self._stopped = True
            self.thread.join()
            self._write_logs()
            self.thread = None
            self.client = None

    def _write_logs_loop(self) -> None:
        """Runs in a background thread, uploads logs periodically in a loop"""
        while not self._stopped:
            cont = True
            while cont:
                cont = self._write_logs()
            time.sleep(self.logging_period)

    def _write_logs(self) -> bool:
        """Upload a single batch of logs.

        Returns:
            - bool: Whether `_write_logs` should be called again this round.
        """
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
        return cont

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


def _log_record_context_injector(*args: Any, **kwargs: Any) -> logging.LogRecord:
    """
    A custom logger LogRecord Factory that injects selected context parameters into newly
    created logs.

    Args:
        - *args: arguments to pass to the original LogRecord Factory
        - **kwargs: keyword arguments to pass to the original LogRecord Factory

    Returns:
        - logging.LogRecord: the newly created LogRecord
    """
    record = _original_log_record_factory(*args, **kwargs)

    additional_attrs = context.config.logging.get("log_attributes", [])

    for attr in PREFECT_LOG_RECORD_ATTRIBUTES + tuple(additional_attrs):
        value = context.get(attr, None)
        if value or attr in additional_attrs:
            setattr(record, attr, value)

    return record


def _create_logger(name: str) -> logging.Logger:
    """
    Creates a logger with a `StreamHandler` that has level and formatting
    set from `prefect.config`.

    Args:
        - name (str): Name to use for logger.

    Returns:
        - logging.Logger: a configured logging object
    """
    logging.setLogRecordFactory(_log_record_context_injector)

    logger = logging.getLogger(name)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        context.config.logging.format, context.config.logging.datefmt
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(context.config.logging.level)
    logger.addHandler(CloudHandler())
    return logger


def configure_logging(testing: bool = False) -> logging.Logger:
    """
    Creates a "prefect" root logger with a `StreamHandler` that has level and formatting
    set from `prefect.config`.

    Args:
        - testing (bool, optional): a boolean specifying whether this configuration
            is for testing purposes only; this helps us isolate any global state during testing
            by configuring a "prefect-test-logger" instead of the standard "prefect" logger

    Returns:
        - logging.Logger: a configured logging object
    """
    name = "prefect-test-logger" if testing else "prefect"
    return _create_logger(name)


context.logger = prefect_logger = configure_logging()


def configure_extra_loggers() -> None:
    """
    Creates a "Prefect" configured logger for all strings in extra_loggers config list.
    The logging.extra_loggers config defaults to an empty list.
    """
    loggers = context.config.logging.get("extra_loggers", [])
    for l in loggers:
        _create_logger(l)


configure_extra_loggers()


def create_diagnostic_logger(name: str) -> logging.Logger:
    """
    Create a logger that does not use the `CloudHandler` but preserves all other
    Prefect logging configuration.  For diagnostic / debugging / internal use only.
    """
    logger = _create_logger(name)
    logger.handlers = [h for h in logger.handlers if not isinstance(h, CloudHandler)]
    return logger


def get_logger(name: str = None) -> logging.Logger:
    """
    Returns a "prefect" logger.

    Args:
        - name (str): if `None`, the root Prefect logger is returned. If provided, a child
            logger of the name `"prefect.{name}"` is returned. The child logger inherits
            the root logger's settings.

    Returns:
        - logging.Logger: a configured logging object with the appropriate name
    """

    if name is None:
        return prefect_logger
    else:
        return prefect_logger.getChild(name)


LOG_MANAGER = LogManager()


class RedirectToLog:
    """
    Custom redirect of stdout messages to logs

    Args:
        - logger (logging.Logger, optional): an optional logger to redirect stdout. If
            not provided a logger names `stdout` will be created.
    """

    def __init__(self, logger: logging.Logger = None) -> None:
        self.stdout_logger = logger or get_logger("stdout")

    def write(self, s: str) -> None:
        """
        Write message from stdout to a prefect logger.
        Note: blank newlines will not be logged.

        Args:
            s (str): the message from stdout to be logged
        """
        if not isinstance(s, str):
            # stdout is expecting str
            raise TypeError(f"string argument expected, got {type(s)}")

        if s.strip():
            self.stdout_logger.info(s)

    def flush(self) -> None:
        """
        Implemented flush operation for logger handler
        """
        for handler in self.stdout_logger.handlers:
            handler.flush()
