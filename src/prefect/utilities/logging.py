"""
Utility functions for interacting with and configuring logging.  The main entrypoint for
retrieving loggers for customization is the `get_logger` utility.

Note that Prefect Tasks come equipped with their own loggers.  These can be accessed via:
    - `self.logger` if implementing a Task class
    - `prefect.context.get("logger")` if using the `task` decorator

When running locally, log levels and message formatting are set via your Prefect configuration file.
"""
import atexit
import json
import logging
import sys
import threading
import time
from queue import Empty, Queue
from typing import Any

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


class CloudHandler(logging.StreamHandler):
    def __init__(self) -> None:
        super().__init__(sys.stdout)
        self.client = None
        self.logger = logging.getLogger("CloudHandler")
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            context.config.logging.format, context.config.logging.datefmt
        )
        formatter.converter = time.gmtime  # type: ignore
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(context.config.logging.level)

    @property
    def queue(self) -> Queue:
        if not hasattr(self, "_queue"):
            self._queue = Queue()  # type: Queue
            self._flush = False
            self.start()
        return self._queue

    def flush(self) -> None:
        self._flush = True
        if self.client is not None:
            self.batch_upload()
            self._thread.join()

    def batch_upload(self) -> None:
        logs = []
        try:
            while True:
                log = self.queue.get(False)
                logs.append(log)
        except Empty:
            pass

        if logs:
            try:
                assert self.client is not None
                self.client.write_run_logs(logs)
            except Exception as exc:
                message = "Failed to write log with error: {}".format(str(exc))
                self.logger.critical(message)

                # Attempt to write batch error log otherwise log invalid cloud communication
                try:
                    assert self.client is not None
                    self.client.write_run_logs([self._make_error_log(message)])
                except Exception:
                    self.logger.critical("Unable to write logs to Prefect Cloud")

    def _monitor(self) -> None:
        while not self._flush:
            self.batch_upload()
            time.sleep(self.heartbeat)

    def __del__(self) -> None:
        if hasattr(self, "_thread"):
            self.flush()
            atexit.unregister(self.flush)

    def start(self) -> None:
        if not hasattr(self, "_thread"):
            self.heartbeat = context.config.cloud.logging_heartbeat
            self._thread = t = threading.Thread(
                target=self._monitor, name="PrefectCloudLoggingThread"
            )
            t.daemon = True
            t.start()
            atexit.register(self.flush)

    def put(self, log: dict) -> None:
        try:
            json.dumps(log)  # make sure the payload is serializable
            self.queue.put(log)
        except TypeError as exc:
            message = "Failed to write log with error: {}".format(str(exc))
            self.logger.critical(message)

            self.queue.put(self._make_error_log(message))

    def emit(self, record) -> None:  # type: ignore
        # if we shouldn't log to cloud, don't emit
        if not prefect.context.config.logging.log_to_cloud:
            return

        try:
            from prefect.client import Client

            if self.client is None:
                self.client = Client()  # type: ignore

            assert isinstance(self.client, Client)  # mypy assert

            record_dict = record.__dict__.copy()

            # ensures emitted logs respect configured logging level
            config_level = getattr(
                logging, prefect.context.config.logging.level, logging.INFO
            )

            if record_dict["levelno"] < config_level:
                return

            # remove potentially non-json serializable formatting args
            record_dict.pop("args", None)

            log = dict()
            log["flow_run_id"] = prefect.context.get("flow_run_id", None)
            log["task_run_id"] = prefect.context.get("task_run_id", None)
            log["timestamp"] = pendulum.from_timestamp(
                record_dict.pop("created", time.time())
            ).isoformat()
            log["name"] = record_dict.pop("name", None)
            log["message"] = record_dict.pop("message", None)
            log["level"] = record_dict.pop("levelname", None)

            if record_dict.get("exc_text") is not None:
                log["message"] += "\n" + record_dict.pop("exc_text", "")
                record_dict.pop("exc_info", None)

            log["info"] = record_dict
            self.put(log)
        except Exception as exc:
            message = "Failed to write log with error: {}".format(str(exc))
            self.logger.critical(message)

            self.put(self._make_error_log(message))

    def _make_error_log(self, message: str) -> dict:
        log = dict()
        log["flow_run_id"] = prefect.context.get("flow_run_id", None)
        log["timestamp"] = pendulum.from_timestamp(time.time()).isoformat()
        log["name"] = self.logger.name
        log["message"] = message
        log["level"] = "CRITICAL"
        log["info"] = {}

        return log


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
        value = prefect.context.get(attr, None)
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

    # we set the cloud handler to DEBUG level
    # but the handler itself will dynamically respond
    # to the configured level in the emit() method call
    cloud_handler = CloudHandler()
    cloud_handler.setLevel("DEBUG")
    logger.addHandler(cloud_handler)
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
