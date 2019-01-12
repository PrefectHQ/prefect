# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

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


class ResultHandler:
    def serialize(self, result: Any) -> str:
        raise NotImplementedError()

    def deserialize(self, loc: str) -> Any:
        raise NotImplementedError()
