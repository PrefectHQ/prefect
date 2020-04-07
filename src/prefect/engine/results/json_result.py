import json

from typing import Any

from prefect.engine.result import Result


class JSONResult(Result):
    """
    Hook for storing and retrieving JSON serializable Python objects that can
    safely be stored directly in a Prefect database.

    Args:
        - value (Any): the underlying value this Result should represent
    """

    def __init__(self, value: Any = None, **kwargs: Any) -> None:
        self.value = value
        super().__init__(value=value, **kwargs)

    def read(self, loc: str = None) -> Result:
        """
        Returns the underlying value regardless of the argument passed.

        Args:
            - loc (str): an unused argument
        """
        new = self.copy()
        new.value = json.loads(loc or new.filepath)
        return new

    def write(self, **kwargs: Any) -> Result:
        """
        Returns the repr of the underlying value, purely for convenience.

        Args:
            - **kwargs (optional): unused, for compatibility with the interface

        Returns:
            - Result: returns self
        """
        self.filepath = json.dumps(self.value)
        return self

    def exists(self, loc: str = None) -> bool:
        """
        Confirms the existence of the Constant value stored in the Result.

        The value stored within a Constant is logically always present,
        so `True` is returned.

        Args:
             - loc (optional): for interface compatibility
        Returns:
            - bool: True, confirming the constant exists.
        """
        return self.filepath is not ""
