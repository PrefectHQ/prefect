from typing import Any, Generic, TypeVar

T = TypeVar("T")


class unmapped:
    """A container that acts as an infinite array where all items are the same
    value. Used for Task.map where there is a need to map over a single
    value"""

    def __init__(self, value: Any):
        self.value = value

    def __getitem__(self, _) -> Any:
        return self.value


class Quote(Generic[T]):
    """
    Simple wrapper to mark an expression as a different type so it will not be coerced
    by Prefect. For example, if you want to return a state from a flow without having
    the flow assume that state.
    """

    def __init__(self, data: T) -> None:
        self.data = data

    def unquote(self) -> T:
        return self.data


def quote(expr: T) -> Quote[T]:
    """
    Create a `Quote` object

    Examples:
        >>> from prefect.utilities.collections import quote
        >>> x = quote(1)
        >>> x.unquote()
        1
    """
    return Quote(expr)
