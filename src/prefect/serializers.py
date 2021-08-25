import base64
import json
import warnings
from typing import Any

import cloudpickle

from prefect.orion.serializers import register_serializer


@register_serializer("json")
class JSONSerializer:
    """Wrapper for the `json` library to handle bytes instead of strings"""

    @staticmethod
    def dumps(blob: bytes) -> Any:
        return json.loads(blob.decode())

    @staticmethod
    def loads(data: Any) -> bytes:
        return json.dumps(data).encode()


@register_serializer("cloudpickle")
class PickleSerializer:
    """
    Wrapper for `cloudpickle` to encode bytes in base64 for safe transmission and handle
    objects that cannot be serialized without throwing an exception
    """

    @staticmethod
    def dumps(data: Any) -> bytes:
        try:
            data_bytes = cloudpickle.dumps(data)
        except Exception:
            warnings.warn(f"Failed to pickle data of type {type(data)}", stacklevel=3)
            data_bytes = cloudpickle.dumps(repr(data))

        return base64.encodebytes(data_bytes)

    @staticmethod
    def loads(blob: bytes) -> Any:
        return cloudpickle.loads(base64.decodebytes(blob))
