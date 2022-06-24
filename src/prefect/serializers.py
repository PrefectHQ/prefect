"""
Data serializer implementations

These serializers are registered for use with `DataDocument` types
"""
import base64
import json
from typing import TYPE_CHECKING, Any
from uuid import UUID

import cloudpickle

from prefect.orion.serializers import register_serializer

if TYPE_CHECKING:
    from prefect.packaging.base import PackageManifest


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

    Wraps `cloudpickle` to encode bytes in base64 for safe transmission.
    """

    @staticmethod
    def dumps(data: Any) -> bytes:
        data_bytes = cloudpickle.dumps(data)

        return base64.encodebytes(data_bytes)

    @staticmethod
    def loads(blob: bytes) -> Any:
        return cloudpickle.loads(base64.decodebytes(blob))
        # TODO: Consider adding python version data to pickle payloads to raise
        #       more helpful errors for users.
        #       A TypeError("expected bytes-like object, not int") will be raised if
        #       a document is deserialized by Python 3.7 and serialized by 3.8+


@register_serializer(encoding="blockstorage")
class BlockStorageSerializer:
    @staticmethod
    def dumps(block_document: dict) -> bytes:
        # Handling for block_id is to account for deployments created pre-2.0b6
        block_document_id = block_document.get(
            "block_document_id"
        ) or block_document.get("block_id")
        if block_document_id is not None:
            block_document_id = str(block_document_id)
        block_document = {
            "data": json.dumps(block_document["data"]),
            "block_document_id": block_document_id,
        }
        return json.dumps(block_document).encode()

    @staticmethod
    def loads(blob: bytes) -> dict:
        block_document = json.loads(blob.decode())
        # Handling for block_id is to account for deployments created pre-2.0b6
        block_document_id = block_document.get(
            "block_document_id"
        ) or block_document.get("block_id")
        if block_document_id is not None:
            block_document_id = UUID(block_document_id)
        return {
            "data": json.loads(block_document["data"]),
            "block_document_id": block_document_id,
        }


@register_serializer("package-manifest")
class PackageManifestSerializer:
    """
    Serializes a package manifest.
    """

    @staticmethod
    def dumps(data: "PackageManifest") -> bytes:
        return data.json().encode()

    @staticmethod
    def loads(blob: bytes) -> "PackageManifest":
        from prefect.packaging.base import PackageManifest

        return PackageManifest.parse_raw(blob)
