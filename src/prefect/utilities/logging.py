"""
Utility functions for interacting with and configuring logging.  The main entrypoint for retrieving loggers for
customization is the `get_logger` utility.

Note that Prefect Tasks come equipped with their own loggers.  These can be accessed via:
    - `self.logger` if implementing a Task class
    - `prefect.context.get("logger")` if using the `task` decorator

When running locally, log levels and message formatting are set via your Prefect configuration file.
"""
import atexit
import logging
import threading
import time
from queue import Queue, Empty
from typing import Any

import pendulum

import prefect
from prefect.utilities.context import context


class CloudHandler(logging.StreamHandler):
    def __init__(self) -> None:
        super().__init__()
        self.client = None
        self.logger = logging.getLogger("CloudHandler")
        handler = logging.StreamHandler()
        formatter = logging.Formatter(context.config.logging.format)
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
                self.logger.critical(
                    "Failed to write log with error: {}".format(str(exc))
                )

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
        self.queue.put(log)

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
            log = dict()
            log["flowRunId"] = prefect.context.get("flow_run_id", None)
            log["taskRunId"] = prefect.context.get("task_run_id", None)
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
            self.logger.critical("Failed to write log with error: {}".format(str(exc)))


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
    formatter = logging.Formatter(context.config.logging.format)
    formatter.converter = time.gmtime  # type: ignore
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(context.config.logging.level)

    cloud_handler = CloudHandler()
    cloud_handler.setLevel("DEBUG")
    logger.addHandler(cloud_handler)
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
