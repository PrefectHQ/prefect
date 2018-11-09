# Licensed under LICENSE.md; also available at https://www.prefect.io/licenses/alpha-eula

"""
Parent classes which are used to build custom functionality to allow serializable
objects in the prefect library.
"""

from typing import Any

import json


class Serializer:
    """
    Parent implementation of a class in which objects can be serialized and deserialized.
    """

    @classmethod
    def serialize(cls, object: Any) -> str:
        """
        Serialize provided object.

        Args:
            - object (Any): object to serialize

        Returns:
            - str: serialized object

        Raises:
            - NotImplementedError: if this method hasn't been implemented in the child class
        """
        raise NotImplementedError()

    @classmethod
    def deserialize(cls, key: str) -> Any:
        """
        Deserialize provided key.

        Args:
            - key (str): serialized key to deserialize

        Returns:
            - Any: deserialized object

        Raises:
            - NotImplementedError: if this method hasn't been implemented in the child class
        """
        raise NotImplementedError()


class JSONSerializer:
    @classmethod
    def serialize(cls, object: Any) -> str:
        """
        Serializes an object

        Args:
            - object (Any): an object to be dumped to a json string

        Returns:
            - str: An encoded json string
        """
        return json.dumps(object)

    @classmethod
    def deserialize(cls, key: str) -> Any:
        """
        Deserializes an encoded json string

        Args:
            - key (str): a json string to be loaded

        Returns:
            - A decoded json string in the form of the original object before serialization
        """
        return json.loads(key)
