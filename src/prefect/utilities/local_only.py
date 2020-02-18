import json
import logging
import sys
from abc import ABC, abstractmethod
from logging import Formatter, LogRecord, Handler, StreamHandler, FileHandler
from pathlib import Path
from typing import Optional, Callable

import prefect
from prefect.utilities.logging import CloudHandler


class LocalOnlyError(Exception):
    """
    Exception raised to replace uncaught exception in task with a
    a generic exception w/o the tasks stack trace.
    """


class LocalOnly(ABC):
    EXTRA_KEY = "_local_only"
    DEBUG_LOGGER = "local_only_debug"

    @abstractmethod
    def remote_formatter(self):
        pass

    @abstractmethod
    def remote_handler(self):
        pass

    @staticmethod
    def apply_local_only():
        module, cls = prefect.config.local_only.cls.rsplit(sep=".", maxsplit=1)
        kwargs = json.loads(prefect.config.local_only.kwargs)
        configurator = getattr(sys.modules[module], cls)(**kwargs)
        configurator.configure()

    def configure(self):
        prefect_logger = prefect.utilities.logging.get_logger()
        remote_handler = self.remote_handler()
        for handler in prefect_logger.handlers:
            if isinstance(handler, remote_handler.__class__):
                # Already applied to logging system.
                return
        for handler in prefect_logger.handlers:
            if isinstance(handler, CloudHandler):
                # ToDo: Update CloudHandler to call some formatter.
                handler.formatter = self.remote_formatter()
        prefect_logger.addHandler(remote_handler)

        # # Used to inspect what is going on in the formatters when exceptions are logged.
        # for handler in prefect_logger.handlers:
        #     if not isinstance(handler, CloudHandler) and isinstance(handler, StreamHandler):
        #         handler.formatter = DebugFormatter()
        #
        # debug_formatter = Formatter(prefect.config.logging.format)
        # debug_handler = FileHandler(
        #     "/Users/nateatkins/projects/cake/prefect-tutorial/cloud/07-safe-hack/debug.log"
        # )
        # # debug_handler = StreamHandler(stream=sys.stderr)
        # debug_handler.setFormatter(debug_formatter)
        # debug_logger = logging.getLogger(self.DEBUG_LOGGER)
        # debug_logger.addHandler(debug_handler)
        # debug_logger.setLevel(logging.DEBUG)

    @classmethod
    def logger(cls, name: Optional[str] = None):
        logger = prefect.utilities.logging.get_logger(name)
        if not prefect.config.local_only.enabled:
            return logger
        cls.apply_local_only()
        return logger

    # @classmethod
    # def get_debug_logger(cls):
    #     return logging.getLogger(cls.DEBUG_LOGGER)


# class DebugFormatter(Formatter):
#     def __init__(self, **kwargs):
#         super().__init__(**kwargs)
#         self.formatter = Formatter(prefect.config.logging.format)
#
#     def format(self, record: LogRecord) -> str:
#         msg = self.formatter.format(record)
#         return msg


class FileRemoteFormatter(Formatter):
    def __init__(self, extra_key: str, url_fn: Callable[[], str], **kwargs):
        super().__init__(**kwargs)
        self.extra_key = extra_key
        self.url = url_fn

    def format(self, record: LogRecord) -> str:
        message = [record.message]
        if getattr(record, self.extra_key, None):
            message.append(self.url())
        msg = "\n".join(message)
        return msg


class FileRemoteHandler(Handler):
    def __init__(self, extra_key: str, filename_fn: Callable[[], Path], **kwargs):
        super().__init__(**kwargs)
        self.extra_key = extra_key
        self.filename = filename_fn

    def handle(self, record: LogRecord):
        # ToDo: This should be in a formatter.
        message = [record.message]
        try:
            local_only_data = getattr(record, self.extra_key)
            message.append(local_only_data)
        except AttributeError:
            # No local only data.
            return
        if record.exc_info:
            message.append(record.exc_text)
        msg = "\n".join(message)
        with self.filename().open("wt") as fh:
            fh.write(msg)


class FileLocalOnly(LocalOnly):
    def __init__(self, root_directory: str):
        self.root_directory = Path(root_directory)

    def _log_path(self) -> Path:
        return (self.root_directory / prefect.context.flow_name).absolute()

    def _log_filename(self) -> Path:
        filename = f'log-{prefect.context.date.isoformat().replace(":", "-").replace("+", "-")}.txt'
        return self._log_path() / f"{filename}"

    def _log_url(self) -> str:
        return f"file:///{self._log_filename()}"

    def remote_formatter(self):
        return FileRemoteFormatter(self.EXTRA_KEY, self._log_url)

    def remote_handler(self):
        return FileRemoteHandler(self.EXTRA_KEY, self._log_filename)

    def configure(self):
        self._log_path().mkdir(exist_ok=True, parents=True)
        super().configure()
