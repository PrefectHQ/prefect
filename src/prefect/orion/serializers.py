from typing import TYPE_CHECKING, Any, Dict, Tuple, TypeVar, Union

from typing_extensions import Protocol

from prefect.orion.utilities.filesystem import (
    FILE_SYSTEM_SCHEMES,
    read_blob,
    write_blob,
)

if TYPE_CHECKING:
    # `DataDocument` is required for the `OrionSerializer` but is a circular import
    from prefect.orion.schemas.data import DataDocument

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


# Server-side serializers --------------------------------------------------------------


@register_serializer(encoding=FILE_SYSTEM_SCHEMES)
class FileSerializer(Serializer[bytes]):
    """
    Persists bytes to a file system and creates a blob with a path to the data for
    future retrieval
    """

    @staticmethod
    def dumps(data: bytes, path: str) -> bytes:
        write_blob(data, path)

        # Return the path as bytes to conform to the spec
        return path.encode()

    @staticmethod
    def loads(blob: bytes) -> bytes:
        path = blob.decode()
        return read_blob(path)


@register_serializer(encoding="orion")
class OrionSerializer(Serializer["DataDocument"]):
    """
    This serializer wraps a data document with an "orion" schema so we can indicate
    that a document should be resolved by sending it to Orion
    """

    @staticmethod
    def dumps(data: "DataDocument") -> bytes:
        return data.json().encode()

    @staticmethod
    def loads(blob: bytes) -> "DataDocument":
        from prefect.orion.schemas.data import DataDocument

        return DataDocument.parse_raw(blob)
