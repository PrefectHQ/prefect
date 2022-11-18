from abc import ABC
from typing import Generic, TypeVar

T = TypeVar("T")


class BaseAnnotation(ABC, Generic[T]):
    """
    Base class for Prefect annotation types
    """

    def __init__(self, value: T):
        self.value = value

    def unwrap(self) -> T:
        return self.value

    def __eq__(self, other: object) -> bool:
        if not type(self) == type(other):
            return False
        return self.unwrap() == other.unwrap()


class unmapped(BaseAnnotation[T]):
    """
    Wrapper for iterables.

    Indicates that this input should be sent as-is to all runs created during a mapping
    operation instead of being split.
    """

    def __getitem__(self, _) -> T:
        # Internally, this acts as an infinite array where all items are the same value
        return self.unwrap()


class allow_failure(BaseAnnotation[T]):
    """
    Wrapper for states or futures.

    Indicates that the upstream run for this input can be failed.

    Generally, Prefect will not allow a downstream run to start if any of its inputs
    are failed. This annotation allows you to opt into receiving a failed input
    downstream.

    If the input is from a failed run, the attached exception will be passed to your
    function.
    """


class Quote(BaseAnnotation[T]):
    """
    Simple wrapper to mark an expression as a different type so it will not be coerced
    by Prefect. For example, if you want to return a state from a flow without having
    the flow assume that state.
    """

    def unquote(self) -> T:
        return self.unwrap()


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


class NotSet:
    """
    Singleton to distinguish `None` from a value that is not provided by the user.
    """
