# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula
import logging
import os
import prefect
import queue

from logging.handlers import QueueHandler, QueueListener
from prefect.configuration import config


class RemoteHandler(logging.StreamHandler):
    def __init__(self) -> None:
        super().__init__()
        self.logger_server = config.cloud.log
        self.client = None

    def emit(self, record):
        if self.client is None:
            from prefect.client import Client

            self.client = Client()
        r = self.client.post(path="", server=self.logger_server, **record.__dict__)


old_factory = logging.getLogRecordFactory()


def cloud_record_factory(*args, **kwargs):
    record = old_factory(*args, **kwargs)
    record.flowrunid = prefect.context.get("flow_run_id", "")
    record.taskrunid = prefect.context.get("task_run_id", "")
    return record


def configure_logging() -> logging.Logger:
    """
    Creates a "prefect" root logger with a `StreamHandler` that has level and formatting
    set from `prefect.config`.

    Returns:
        logging.Logger
    """
    logger = logging.getLogger("prefect")
    handler = logging.StreamHandler()
    formatter = logging.Formatter(config.logging.format)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(config.logging.level)

    # send logs to server
    if config.prefect_cloud is True:
        logging.setLogRecordFactory(cloud_record_factory)
        log_queue = queue.Queue(-1)  # unlimited size queue
        queue_handler = QueueHandler(log_queue)
        remote_handler = RemoteHandler()
        remote_listener = QueueListener(log_queue, remote_handler)
        logger.addHandler(queue_handler)
        remote_listener.start()

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
        logging.Logger
    """
    if name is None:
        return prefect_logger
    else:
        return prefect_logger.getChild(name)
