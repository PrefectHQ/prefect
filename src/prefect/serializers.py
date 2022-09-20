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

import abc
import base64
import json
import warnings
from typing import Any, Generic, TypeVar

import cloudpickle
import pydantic
from anyio._core._exceptions import ExceptionGroup
from pydantic import BaseModel
from typing_extensions import Literal

from prefect.orion.serializers import register_serializer
from prefect.utilities.importtools import from_qualified_name
from prefect.utilities.pydantic import add_type_dispatch

D = TypeVar("D")


def _exception_group_reduce_patch(self: ExceptionGroup):
    return (self.__class__, (self.exceptions,))


@add_type_dispatch
class Serializer(BaseModel, Generic[D], abc.ABC):
    """
    A serializer that can encode objects of type 'D' into bytes.
    """

    type: str

    def dumps(self, obj: D) -> bytes:
        """Encode the object into a blob of bytes."""

    def loads(self, blob: bytes) -> D:
        """Decode the blob of bytes into an object."""


class PickleSerializer(Serializer):
    """
    Serializes objects using the pickle protocol.

    Wraps pickles in base64 for safe transmission.
    """

    type: Literal["pickle"] = "pickle"

    picklelib: str = "cloudpickle"
    picklelib_version: str = None

    @pydantic.validator("picklelib")
    def check_picklelib(cls, value):
        """
        Check that the given pickle library is importable and has dumps/loads methods.
        """
        try:
            pickler = from_qualified_name(value)
        except (ImportError, AttributeError) as exc:
            raise ValueError(
                f"Failed to import requested pickle library: {value!r}."
            ) from exc

        if not callable(getattr(pickler, "dumps", None)):
            raise ValueError(
                f"Pickle library at {value!r} does not have a 'dumps' method."
            )

        if not callable(getattr(pickler, "loads", None)):
            raise ValueError(
                f"Pickle library at {value!r} does not have a 'loads' method."
            )

        return value

    @pydantic.root_validator
    def check_picklelib_version(cls, values):
        """
        Infers a default value for `picklelib_version` if null or ensures it matches
        the version retrieved from the `pickelib`.
        """
        picklelib = values.get("picklelib")
        picklelib_version = values.get("picklelib_version")

        if not picklelib:
            raise ValueError("Unable to check version of unrecognized picklelib module")

        pickler = from_qualified_name(picklelib)
        pickler_version = getattr(pickler, "__version__", None)

        if not picklelib_version:
            values["picklelib_version"] = pickler_version
        elif picklelib_version != pickler_version:
            warnings.warn(
                f"Mismatched {picklelib!r} versions. Found {pickler_version} in the "
                f"environment but {picklelib_version} was requested. This may cause "
                "the serializer to fail.",
                RuntimeWarning,
                stacklevel=3,
            )

        return values

    def dumps(self, obj: Any) -> bytes:
        pickler = from_qualified_name(self.picklelib)

        # Workaround for exception group type which is otherwise not recoverable after
        # serialization
        if isinstance(obj, ExceptionGroup):
            obj.__reduce__ = _exception_group_reduce_patch

        blob = pickler.dumps(obj)

        return base64.encodebytes(blob)

    def loads(self, blob: bytes) -> Any:
        pickler = from_qualified_name(self.picklelib)
        return pickler.loads(base64.decodebytes(blob))


# DEPRECATED
# Data document serializers ----------------


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
