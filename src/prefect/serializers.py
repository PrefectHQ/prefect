"""
Data serializer implementations

These serializers are registered for use with `DataDocument` types
"""
import base64
import json
import warnings
from typing import Any

import cloudpickle
import pydantic

from prefect.orion.serializers import register_serializer
from prefect.orion.schemas.data import DataDocument
from prefect.client import OrionClient, inject_client


@register_serializer("json")
class JSONSerializer:
    """
    Serializes data to JSON.

    Input types must be compatible with the stdlib json library.

    Wraps the `json` library to serialize to UTF-8 bytes instead of string types.
    """

    @staticmethod
    def dumps(data: Any) -> bytes:
        return json.dumps(data).encode()

    @staticmethod
    def loads(blob: bytes) -> Any:
        return json.loads(blob.decode())


@register_serializer("text")
class TextSerializer:
    @staticmethod
    def dumps(data: str) -> bytes:
        return data.encode()

    @staticmethod
    def loads(blob: bytes) -> str:
        return blob.decode()


@register_serializer("cloudpickle")
class PickleSerializer:
    """
    Serializes arbitrary objects using the pickle protocol.

    Wraps `cloudpickle` to encode bytes in base64 for safe transmission and handle
    objects that cannot be serialized without throwing an exception.
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


@inject_client
async def resolve_datadoc(datadoc: DataDocument, client: OrionClient) -> Any:
    if not isinstance(datadoc, DataDocument):
        raise TypeError(
            f"`resolve_datadoc` received invalid type {type(datadoc).__name__}"
        )
    result = datadoc
    while isinstance(result, DataDocument):
        if result.encoding == "orion":
            inner_doc_bytes = await client.retrieve_data(result)
            try:
                result = DataDocument.parse_raw(inner_doc_bytes)
            except pydantic.ValidationError as exc:
                raise ValueError(
                    "Expected `orion` encoded document to contain another data "
                    "document but it could not be parsed."
                ) from exc
        else:
            result = result.decode()
    return result
