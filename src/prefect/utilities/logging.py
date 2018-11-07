# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula
import json
import logging
import queue
import requests

from logging.handlers import QueueHandler, QueueListener
from prefect.client import Client
from prefect.configuration import config


class RemoteHandler(logging.StreamHandler):
    def __init__(self):
        super().__init__()
        self.logger_server = config.cloud.logger_server

    def emit(self, record):
        r = requests.post(self.logger_server, params=record.__dict__)


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

    ## send logs to server
    if config.prefect_cloud is True:
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
