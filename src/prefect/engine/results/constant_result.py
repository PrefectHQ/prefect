from typing import Any
from prefect.engine.result import Result


class ConstantResult(Result):
    """
    Hook for storing and retrieving constant Python objects. Only intended to be used
    internally.  The "backend" in this instance is the class instance itself.

    Args:
        - **kwargs (Any, optional): any additional `Result` initialization options
    """

    def __init__(self, **kwargs: Any) -> None:
        if "serializer" in kwargs:
            raise ValueError("Can't pass a serializer to a ConstantResult.")
        super().__init__(**kwargs)

    def read(self, location: str) -> Result:
        """
        Will return the underlying value regardless of the argument passed.

        Args:
            - location (str): an unused argument
        """
        return self

    def write(self, value_: Any, **kwargs: Any) -> Result:
        """
        Will return the repr of the underlying value, purely for convenience.

        Args:
            - value_ (Any): unused, for interface compatibility
            - **kwargs (optional): unused, for interface compatibility

        Raises:
            - ValueError: ConstantResults cannot be written to
        """
        raise ValueError("Cannot write values to `ConstantResult` types.")

    def exists(self, location: str, **kwargs: Any) -> bool:
        """
        As all Python objects are valid constants, always returns `True`.

        Args:
             - location (str): for interface compatibility
             - **kwargs (Any): string format arguments for `location`

        Returns:
            - bool: True, confirming the constant exists.
        """
        return True
