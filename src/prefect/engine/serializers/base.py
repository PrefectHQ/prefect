import pendulum
import datetime
import base64
import json
from typing import Any, Union, Optional

import cloudpickle

__all__ = ("Serializer", "JSONSerializer", "DateTimeSerializer")


class Serializer:
    """
    Serializers are used by Results to handle the transformation of
    Python objects to and from bytes.
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
        pickled = cloudpickle.dumps(value)
        return base64.urlsafe_b64encode(pickled)

    def deserialize(self, value: Union[bytes, str]) -> Any:
        """
        Deserialize an object from bytes.

        Args:
            - value (Union[bytes, str]): the value to deserialize

        Returns:
            - Any: the deserialized value
        """
        decoded = base64.urlsafe_b64decode(value)
        return cloudpickle.loads(decoded)


class JSONSerializer(Serializer):
    """
    JSONSerializers serialize objects to and from JSON
    """

    def serialize(self, value: Any) -> bytes:
        """
        Serialize an object to JSON

        Args:
            - value (Any): the value to serialize

        Returns:
            - bytes: the serialized value
        """
        return json.dumps(value).encode()

    def deserialize(self, value: Union[bytes, str]) -> Any:
        """
        Deserialize an object from JSON

        Args:
            - value (Union[bytes, str]): the value to deserialize

        Returns:
            - Any: the deserialized value
        """
        return json.loads(value)


class DateTimeSerializer(Serializer):
    """
    DateTimeSerializers serialize DateTimes to UTC ISO-6801, and back.
    """

    def serialize(self, value: Union[datetime.datetime, str, None]) -> bytes:
        """
        Serialize a DateTime to bytes

        Args: 
            - value (Union[datetime.datetime, str]): the value to serialize.
                If a string is provided (for example, as an API-supplied Parameter
                value, it is converted to a datetime)

        Returns: - bytes: the serialized value
        """
        if value is None:
            return b""
        elif isinstance(value, str):
            value = pendulum.parse(value)
        return pendulum.instance(value).in_tz("UTC").to_iso8601_string().encode()

    def deserialize(self, value: Union[bytes, str]) -> Optional[datetime.datetime]:
        """
        Deserialize a DateTime from bytes

        Args:
            - value (Union[bytes, str]): the value to deserialize

        Returns:
            - datetime.datetime: the deserialized value
        """
        # an empty string signifies a serialized value of None
        if not value:
            return None
        elif isinstance(value, bytes):
            value = value.decode()
        return pendulum.parse(value)
