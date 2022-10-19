from typing import Any, Generic, TypeVar

T = TypeVar("T")


class unmapped:
    """
    Wrapper for iterables.

    Indicates that this input should be sent as-is to all runs created during a mapping
    operation instead of being split.
    """

    def __init__(self, value: Any):
        self.value = value

    def __getitem__(self, _) -> Any:
        # Internally, this acts as an infinite array where all items are the same value
        return self.value


class allow_failure:
    """
    Wrapper for states or futures.

    Indicates that the upstream run for this input can be failed.

    Generally, Prefect will not allow a downstream run to start if any of its inputs
    are failed. This annotation allows you to opt into receiving a failed input
    downstream.

    If the input is from a failed run, the attached exception will be passed to your
    function.
    """

    def __init__(self, value: Any):
        self.value = value

    def unwrap(self) -> Any:
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


class NotSet:
    """
    Singleton to distinguish `None` from a value that is not provided by the user.
    """
