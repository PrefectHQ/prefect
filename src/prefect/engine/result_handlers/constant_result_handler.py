from typing import Any

from prefect.engine.result_handlers import ResultHandler


class ConstantResultHandler(ResultHandler):
    """
    Hook for storing and retrieving constant Python objects. Only intended to be used
    internally.

    Args:
        - value (Any): the underlying value that we wish to "handle"
    """

    def __init__(self, value: Any) -> None:
        self.value = value
        super().__init__()

    def read(self, arg: str) -> Any:
        """
        Returns the underlying value regardless of the argument passed.

        Args:
            - arg (str): an unused argument
        """
        return self.value

    def write(self, result: Any) -> str:
        """
        Returns the repr of the underlying value, purely for convenience.

        Args:
            - result (Any): the result to represent

        Returns:
            - str: the repr of the result
        """
        return repr(self.value)
