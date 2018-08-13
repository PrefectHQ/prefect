"""
Parent classes which are used to build custom functionality to allow serializable
objects in the prefect library.
"""

from prefect.utilities import json
from typing import Any


class Serializer:
    """
    Parent implementation of a class in which objects can be serialized and deserialized.
    """

    @classmethod
    def serialize(cls, object: Any) -> str:
        raise NotImplementedError()

    @classmethod
    def deserialize(cls, key: str) -> Any:
        raise NotImplementedError()


class JSONSerializer:
    """
    Parent implementation that uses the `prefect.utilities.json` object to serialize
    and deserialize custom json objects.
    """

    @classmethod
    def serialize(cls, object: Any) -> str:
        """
        Serialized an object using `prefect.utilities.json`

        Args:
            object (Any): an object to be dumped to a json string

        Returns:
            An encoded json string
        """
        return json.dumps(object)

    @classmethod
    def deserialize(cls, key: str) -> Any:
        """
        Deserializes an encoded json string using `prefect.utilities.json`

        Args:
            key (str): a json string to be loaded

        Returns:
            An dencoded json string in the form of the original object before serialization
        """
        return json.loads(key)
