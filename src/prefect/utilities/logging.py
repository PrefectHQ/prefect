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

import logging.config
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


def configure_logging() -> logging.Logger:
    """
    Configures logging for Prefect from the `prefect.config.logging` section

    Returns:
        - logging.Logger: The root `prefect` logger
    """
    logging.config.dictConfig(context.config.logging.setup)

    # Add context injector
    logging.setLogRecordFactory(_log_record_context_injector)

    logger = logging.getLogger("prefect")
    return logger


context.logger = prefect_logger = configure_logging()


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
    # TODO: Handle empty strings here too; it's weird to get a `prefect.` logger
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
