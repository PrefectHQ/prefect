import atexit
import logging
import os
import queue
import time
from logging.handlers import QueueHandler, QueueListener
from typing import Any

import prefect
from prefect.configuration import config


class RemoteHandler(logging.StreamHandler):
    def __init__(self) -> None:
        super().__init__()
        self.logger_server = config.cloud.log
        self.client = None
        self.errored_out = False

    def emit(self, record) -> None:  # type: ignore
        try:
            if self.errored_out is True:
                return
            if self.client is None:
                from prefect.client import Client

                self.client = Client()  # type: ignore
            assert isinstance(self.client, Client)  # mypy assert
            r = self.client.post(path="", server=self.logger_server, **record.__dict__)
        except:
            self.errored_out = True


old_factory = logging.getLogRecordFactory()


def cloud_record_factory(*args: Any, **kwargs: Any) -> Any:
    record = old_factory(*args, **kwargs)
    record.flow_run_id = prefect.context.get("flow_run_id", "")  # type: ignore
    record.task_run_id = prefect.context.get("task_run_id", "")  # type: ignore
    return record


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
        logging.setLogRecordFactory(cloud_record_factory)
        remote_handler = RemoteHandler()
        logger.addHandler(remote_handler)

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
