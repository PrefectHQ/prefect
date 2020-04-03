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

    def read(self, arg: Optional[str] = None) -> Any:
        """
        Returns the underlying value regardless of the argument passed.

        Args:
            - arg (str): an unused argument
        """
        return self.value

    def write(self) -> str:
        """
        Returns the repr of the underlying value, purely for convenience.

        Returns:
            - str: the repr of the result
        """
        return repr(self.value)

    def exists(self) -> bool:
        """
        Confirms the existence of the Constant value stored in the Result.

        The value stored within a Constant is logically always present,
        so `True` is returned.

        Returns:
            - bool: True, confirming the constant exists.
        """

        return True
