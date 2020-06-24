import json

from typing import Any

from prefect.engine.result import Result
from prefect.engine.serializers import JSONSerializer


class PrefectResult(Result):
    """
    Hook for storing and retrieving JSON serializable Python objects that can
    safely be stored directly in a Prefect database.

    Args:
        - **kwargs (Any, optional): any additional `Result` initialization options
    """

    def __init__(self, **kwargs: Any) -> None:
        if "serializer" in kwargs:
            raise ValueError("PrefectResult must use a JSONSerializer")
        kwargs["serializer"] = JSONSerializer()
        super().__init__(**kwargs)

    def read(self, location: str) -> Result:
        """
        Returns the underlying value regardless of the argument passed.

        Args:
            - location (str): an unused argument

        Returns:
            - Result: a new result instance with the data represented by the location
        """
        new = self.copy()
        new.value = self.serializer.deserialize(location)
        new.location = location
        return new

    def write(self, value: Any, **kwargs: Any) -> Result:
        """
        JSON serializes `self.value` and returns `self`.

        Args:
            - value (Any): the value to write; will then be stored as the `value` attribute
                of the returned `Result` instance
            - **kwargs (optional): unused, for compatibility with the interface

        Returns:
            - Result: returns a new `Result` with both `value` and `location` attributes
        """
        new = self.copy()
        new.value = value
        new.location = self.serializer.serialize(new.value).decode()
        return new

    def exists(self, location: str, **kwargs: Any) -> bool:
        """
        Confirms that the provided value is JSON deserializable.

        Args:
            - location (str): the value to test
            - **kwargs (Any): unused, for compatibility with the interface

        Returns:
            - bool: whether the provided string can be deserialized
        """
        try:
            json.loads(location)
            return True
        except:
            return False
