"""
Utility functions for interacting with and configuring logging.  The main entrypoint for retrieving loggers for
customization is the `get_logger` utility.

Note that Prefect Tasks come equipped with their own loggers.  These can be accessed via:
    - `self.logger` if implementing a Task class
    - `prefect.context.get("logger")` if using the `task` decorator

When running locally, log levels and message formatting are set via your Prefect configuration file.
"""
import logging
import time
from typing import Any

import pendulum

import prefect
from prefect.configuration import config


class CloudHandler(logging.StreamHandler):
    def __init__(self) -> None:
        super().__init__()
        self.client = None
        self.errored_out = False

    def emit(self, record) -> None:  # type: ignore
        try:
            from prefect.client import Client

            if self.errored_out is True:
                return
            if self.client is None:
                self.client = Client()  # type: ignore

            assert isinstance(self.client, Client)  # mypy asser

            record_dict = record.__dict__.copy()
            flow_run_id = prefect.context.get("flow_run_id", None)
            task_run_id = prefect.context.get("task_run_id", None)
            timestamp = pendulum.from_timestamp(record_dict.get("created", time.time()))
            name = record_dict.get("name", None)
            message = record_dict.get("message", None)
            level = record_dict.get("level", None)

            self.client.write_run_log(
                flow_run_id=flow_run_id,
                task_run_id=task_run_id,
                timestamp=timestamp,
                name=name,
                message=message,
                level=level,
                info=record_dict,
            )
        except:
            self.errored_out = True


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
    logger = logging.getLogger(name)
    handler = logging.StreamHandler()
    formatter = logging.Formatter(config.logging.format)
    formatter.converter = time.gmtime  # type: ignore
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(config.logging.level)

    # send logs to server
    if config.logging.log_to_cloud:
        logger.addHandler(CloudHandler())
    return logger


prefect_logger = configure_logging()


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
