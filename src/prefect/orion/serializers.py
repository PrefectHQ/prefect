from typing import Any, Dict, Tuple, TypeVar, Union

from typing_extensions import Protocol

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
