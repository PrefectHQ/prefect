import base64
import importlib
import json
import warnings
from typing import Any

import cloudpickle
import pydantic
from typing_extensions import Literal

from prefect.orion.schemas.data import DataDocument


class JSONDataDocument(DataDocument[Any]):
    encoding: Literal["json"] = "json"

    @staticmethod
    def decode(blob: bytes) -> Any:
        data = json.loads(blob.decode())
        if isinstance(data, dict) and data.get("__pydantic__"):
            data = import_object(data["model"]).parse_raw(data["data"])
        return data

    @staticmethod
    def encode(data: Any) -> bytes:
        if isinstance(data, pydantic.BaseModel):
            # Allow encoding pydantic models as JSON
            data = {
                "__pydantic__": True,
                "model": get_import_name(type(data)),
                "data": data.json(),
            }
        return json.dumps(data).encode()


class CloudpickleDataDocument(DataDocument):
    encoding: Literal["cloudpickle"] = "cloudpickle"

    @staticmethod
    def decode(blob: bytes) -> Any:
        return cloudpickle.loads(base64.decodebytes(blob))

    @staticmethod
    def encode(data: Any) -> bytes:
        try:
            data_bytes = cloudpickle.dumps(data)
        except Exception:
            warnings.warn(f"Failed to pickle data of type {type(data)}", stacklevel=3)
            data_bytes = cloudpickle.dumps(repr(data))

        return base64.encodebytes(data_bytes)


def get_import_name(obj: Any) -> str:
    """
    Given an object, returns its fully-qualified name, meaning a string that represents
    its Python import path

    Args:
        - obj (Any): an importable Python object

    Returns:
        - str: the qualified name
    """
    return obj.__module__ + "." + obj.__qualname__


def import_object(name: str) -> Any:
    """Import an object given a fully-qualified name.

    Args:
        - name (string): The fully-qualified name of the object to import.

    Returns:
        - obj: The object that was imported.

    Example:

    ```python
    >>> obj = import_object("random.randint")
    >>> import random
    >>> obj == random.randint
    True
    ```
    """

    # Try importing it first so we support "module" or "module.sub_module"
    try:
        module = importlib.import_module(name)
        return module
    except ImportError:
        # If no subitem was included raise the import error
        if "." not in name:
            raise

    # Otherwise, we'll try to load it as an attribute of a module
    mod_name, attr_name = name.rsplit(".", 1)
    module = importlib.import_module(mod_name)
    return getattr(module, attr_name)
