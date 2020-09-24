from typing import Any

from prefect.engine.result import Result
from prefect.engine.serializers import JSONSerializer, Serializer, DateTimeSerializer


class PrefectResult(Result):
    """
    Hook for storing and retrieving JSON serializable Python objects that can
    safely be stored directly in a Prefect database.

    Args:
        - **kwargs (Any, optional): any additional `Result` initialization options
    """

    def __init__(self, **kwargs: Any) -> None:
        if "serializer" not in kwargs:
            kwargs["serializer"] = JSONSerializer()
        super().__init__(**kwargs)

    @property  # type: ignore
    def serializer(self) -> Serializer:  # type: ignore
        return self._serializer

    @serializer.setter
    def serializer(self, val: Serializer) -> None:  # type: ignore
        if not isinstance(val, (JSONSerializer, DateTimeSerializer)):
            raise TypeError(
                "PrefectResult only supports JSONSerializer or DateTimeSerializer"
            )
        self._serializer = val

    def read(self, location: str) -> Result:
        """
        Returns the underlying value regardless of the argument passed.

        Args:
            - location (str): an unused argument

        Returns:
            - Result: a new result instance with the data represented by the location
        """
        new = self.copy()
        new.value = self.serializer.deserialize(location.encode("utf-8"))
        new.location = location
        return new

    def write(self, value_: Any, **kwargs: Any) -> Result:
        """
        JSON serializes `self.value` and returns `self`.

        Args:
            - value_ (Any): the value to write; will then be stored as the `value` attribute
                of the returned `Result` instance
            - **kwargs (optional): unused, for compatibility with the interface

        Returns:
            - Result: returns a new `Result` with both `value` and `location` attributes
        """
        new = self.copy()
        new.value = value_
        new.location = self.serializer.serialize(new.value).decode("utf-8")
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
            self.serializer.deserialize(location.encode("utf-8"))
            return True
        except Exception:
            return False
