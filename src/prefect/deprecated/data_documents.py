import base64
import json
from typing import TYPE_CHECKING, Any, Dict, Generic, Tuple, Type, TypeVar, Union

import cloudpickle
from typing_extensions import Protocol

from prefect.orion.utilities.schemas import PrefectBaseModel

if TYPE_CHECKING:
    from prefect.packaging.base import PackageManifest
    from prefect.results import _Result


T = TypeVar("T", bound="DataDocument")  # Generic for DataDocument class types
D = TypeVar("D", bound=Any)  # Generic for DataDocument data types

_SERIALIZERS: Dict[str, "Serializer"] = {}
D = TypeVar("D")


class Serializer(Protocol[D]):
    """
    Define a serializer that can encode data of type 'D' into bytes
    """

    @staticmethod
    def dumps(data: D, **kwargs: Any) -> bytes:
        raise NotImplementedError

    @staticmethod
    def loads(blob: bytes) -> D:
        raise NotImplementedError


def register_serializer(
    encoding: Union[str, Tuple[str, ...]], serializer: Serializer = None
):
    """Register dispatch of `func` on arguments of encoding `encoding`"""

    def wrapper(serializer):
        if isinstance(encoding, tuple):
            for e in encoding:
                register_serializer(e, serializer)
        else:
            _SERIALIZERS[encoding] = serializer
        return serializer

    return wrapper(serializer) if serializer is not None else wrapper


def lookup_serializer(encoding: str) -> Serializer:
    """Return the serializer implementation for the given ``encoding``"""
    try:
        return _SERIALIZERS[encoding]
    except KeyError:
        raise ValueError(f"Unregistered encoding {encoding!r}")


class DataDocument(PrefectBaseModel, Generic[D]):
    """
    A data document includes an encoding string and a blob of encoded data

    Subclasses can define the expected type for the blob's underlying type using the
    generic variable `D`.

    For example `DataDocument[str]` indicates that a string should be passed when
    creating the document and a string will be returned when it is decoded.
    """

    encoding: str
    blob: bytes

    # A cache for the decoded data, see `DataDocument.decode`
    _data: D
    __slots__ = ["_data"]

    @classmethod
    def encode(
        cls: Type["DataDocument"], encoding: str, data: D, **kwargs: Any
    ) -> "DataDocument[D]":
        """
        Create a new data document

        A serializer must be registered for the given `encoding`
        """
        # Dispatch encoding
        blob = lookup_serializer(encoding).dumps(data, **kwargs)

        inst = cls(blob=blob, encoding=encoding)
        inst._cache_data(data)
        return inst

    def decode(self) -> D:
        """
        Get the data from a data document

        A serializer must be registered for the document's encoding
        """
        if self.has_cached_data():
            return self._data

        # Dispatch decoding
        data = lookup_serializer(self.encoding).loads(self.blob)

        self._cache_data(data)
        return data

    def _cache_data(self, data) -> None:
        # Use object's setattr to avoid a pydantic 'field does not exist' error
        # See https://github.com/samuelcolvin/pydantic/issues/655
        object.__setattr__(self, "_data", data)

    def has_cached_data(self):
        return hasattr(self, "_data")

    def __str__(self) -> str:
        if self.has_cached_data():
            return repr(self._data)
        else:
            return repr(self)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(encoding={self.encoding!r})"


@register_serializer("json")
class DocumentJSONSerializer:
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
class DocumentPickleSerializer:
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
