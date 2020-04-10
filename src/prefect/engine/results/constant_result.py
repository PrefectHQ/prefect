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
        super().__init__(**kwargs)

    def read(self, location: str) -> Result:
        """
        Returns the underlying value regardless of the argument passed.

        Args:
            - location (str): an unused argument
        """
        return self

    def write(self, value: Any, **kwargs: Any) -> Result:
        """
        Returns the repr of the underlying value, purely for convenience.

        Args:
            - value (Any): the value to store on the class; must be the same as `self.value`
                and is exposed purely for interface compatibility
            - **kwargs (optional): unused, for compatibility with the interface

        Returns:
            - Result: returns self

        Raises:
            ValueError: if the provided result is distinct from `self.value`
        """
        if self.value != value:
            raise ValueError("Cannot write new values to `ConstantResult` types.")
        self.location = repr(self.value)
        return self

    def exists(self, location: str) -> bool:
        """
        As all Python objects are valid constants, always returns `True`.

        Args:
             - location (str): for interface compatibility

        Returns:
            - bool: True, confirming the constant exists.
        """
        return True
