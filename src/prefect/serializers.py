"""
Data serializer implementations

These serializers are registered for use with `DataDocument` types
"""
import base64
import json
from typing import TYPE_CHECKING, Any

import cloudpickle

from prefect.orion.serializers import register_serializer

if TYPE_CHECKING:
    from prefect.packaging.base import PackageManifest
    from prefect.results import _Result


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


@register_serializer("result")
class ResultSerializer:
    """
    Serializes a result object
    """

    @staticmethod
    def dumps(data: "_Result") -> bytes:
        return data.json().encode()

    @staticmethod
    def loads(blob: bytes) -> "_Result":
        from prefect.results import _Result

        return _Result.parse_raw(blob)
