import json

from typing import Any

from prefect.engine.result import Result


class PrefectResult(Result):
    """
    Hook for storing and retrieving JSON serializable Python objects that can
    safely be stored directly in a Prefect database.

    Args:
        - **kwargs (Any, optional): any additional `Result` initialization options
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

    def read(self, filepath: str) -> Result:
        """
        Returns the underlying value regardless of the argument passed.

        Args:
            - filepath (str): an unused argument

        Returns:
            - Result: a new result instance with the data represented by the filepath
        """
        new = self.copy()
        new.value = json.loads(filepath)
        new.filepath = filepath
        return new

    def write(self, value: Any, **kwargs: Any) -> Result:
        """
        JSON serializes `self.value` and returns `self`.

        Args:
            - value (Any): the value to write; will then be stored as the `value` attribute
                of the returned `Result` instance
            - **kwargs (optional): unused, for compatibility with the interface

        Returns:
            - Result: returns a new `Result` with both `value` and `filepath` attributes
        """
        new = self.copy()
        new.value = value
        new.filepath = json.dumps(new.value)
        return new

    def exists(self, filepath: str) -> bool:
        """
        Confirms that the provided value is JSON deserializable.

        Args:
            - filepath (str): the value to test

        Returns:
            - bool: whether the provided string can be deserialized
        """
        try:
            json.loads(filepath)
            return True
        except:
            return False
