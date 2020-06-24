import base64
import json
from typing import Any

import cloudpickle


__all__ = ("Serializer", "PickleSerializer", "JSONSerializer")


class Serializer:
    """
    Serializers are used by Results to handle the transformation of Python
    objects to and from bytes.

    Subclasses should implement `serialize` and `deserialize`.
    """

    def __eq__(self, other: Any) -> bool:
        return type(self) == type(other)

    def serialize(self, value: Any) -> bytes:
        """
        Serialize an object to bytes.

        Args:
            - value (Any): the value to serialize

        Returns:
            - bytes: the serialized value
        """
        raise NotImplementedError

    def deserialize(self, value: bytes) -> Any:
        """
        Deserialize an object from bytes.

        Args:
            - value (bytes): the value to deserialize

        Returns:
            - Any: the deserialized value
        """
        raise NotImplementedError


class PickleSerializer(Serializer):
    """A `Serializer` that uses cloudpickle to serialize Python objects."""

    def serialize(self, value: Any) -> bytes:
        """
        Serialize an object to bytes using cloudpickle.

        Args:
            - value (Any): the value to serialize

        Returns:
            - bytes: the serialized value
        """
        return cloudpickle.dumps(value)

    def deserialize(self, value: bytes) -> Any:
        """
        Deserialize an object from bytes using cloudpickle.

        Args:
            - value (bytes): the value to deserialize

        Returns:
            - Any: the deserialized value
        """
        try:
            return cloudpickle.loads(value)
        except Exception as exc:
            try:
                # old versions of Core encoded pickles with base64
                return cloudpickle.loads(base64.b64decode(value))
            except Exception:
                # if there's an error with the backwards-compatible step,
                # reraise the original exception
                raise exc


class JSONSerializer(Serializer):
    """A Serializer that uses JSON to serialize objects"""

    def serialize(self, value: Any) -> bytes:
        """
        Serialize an object to JSON

        Args:
            - value (Any): the value to serialize

        Returns:
            - bytes: the serialized value
        """
        return json.dumps(value).encode()

    def deserialize(self, value: bytes) -> Any:
        """
        Deserialize an object from JSON

        Args:
            - value (bytes): the value to deserialize

        Returns:
            - Any: the deserialized value
        """
        return json.loads(value)
