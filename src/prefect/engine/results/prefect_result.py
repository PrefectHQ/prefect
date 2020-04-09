import json

from typing import Any

from prefect.engine.result import Result


class PrefectResult(Result):
    """
    Hook for storing and retrieving JSON serializable Python objects that can
    safely be stored directly in a Prefect database.

    Args:
        - value (Any): the underlying value this Result should represent
    """

    def __init__(self, value: Any = None, **kwargs: Any) -> None:
        self.value = value
        super().__init__(value=value, **kwargs)

    def read(self, loc: str) -> Result:
        """
        Returns the underlying value regardless of the argument passed.

        Args:
            - loc (str): an unused argument
        """
        new = self.copy()
        new.value = json.loads(loc)
        new.filepath = loc
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

    def exists(self, loc: str) -> bool:
        """
        Confirms that the provided value is JSON deserializable.

        Args:
             - loc (str): the value to test

        Returns:
            - bool: whether the provided string can be deserialized
        """
        try:
            json.loads(loc)
            return True
        except:
            return False
