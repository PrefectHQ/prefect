from typing import Any, Optional

from prefect.engine.result import Result


class ConstantResult(Result):
    """
    Hook for storing and retrieving constant Python objects. Only intended to be used
    internally.

    Args:
        - value (Any): the underlying value this Result should represent
    """

    def __init__(self, value: Any = None, **kwargs: Any) -> None:
        self.value = value
        super().__init__(value=value, **kwargs)

    def read(self, loc: str = None) -> Any:
        """
        Returns the underlying value regardless of the argument passed.

        Args:
            - loc (str): an unused argument
        """
        return self.value

    def write(self, **kwargs: Any) -> Result:
        """
        Returns the repr of the underlying value, purely for convenience.

        Args:
            - **kwargs (optional): unused, for compatibility with the interface

        Returns:
            - Result: returns self
        """
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

        return True
