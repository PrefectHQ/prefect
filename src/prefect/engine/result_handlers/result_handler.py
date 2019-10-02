"""
Result Handlers provide the hooks that Prefect uses to store task results in production; a `ResultHandler` can be provided to a `Flow` at creation.

Anytime a task needs its output or inputs stored, a result handler is used to determine where this data should be stored (and how it can be retrieved).
"""
import base64
import tempfile
from typing import Any

import cloudpickle

from prefect import config
from prefect.client.client import Client
from prefect.utilities import logging


class ResultHandler:
    def __init__(self) -> None:
        self.logger = logging.get_logger(type(self).__name__)

    def __repr__(self) -> str:
        return "<ResultHandler: {}>".format(type(self).__name__)

    def write(self, result: Any) -> Any:
        return result

    def read(self, loc: str) -> str:
        return loc

    def __eq__(self, other: object) -> bool:
        """
        Equality depends on result handler type and any public attributes
        """
        if type(self) == type(other):
            assert isinstance(other, ResultHandler)  # mypy assert
            eq = True
            for attr in self.__dict__:
                if attr.startswith("_") or attr == "logger":
                    continue
                eq &= getattr(self, attr, object()) == getattr(other, attr, object())
            return eq
        return False
