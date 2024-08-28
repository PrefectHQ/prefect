import warnings
from abc import ABC
from collections import namedtuple
from typing import Generic, TypeVar

T = TypeVar("T")


class BaseAnnotation(
    namedtuple("BaseAnnotation", field_names="value"), ABC, Generic[T]
):
    """
    Base class for Prefect annotation types.

    Inherits from `namedtuple` for unpacking support in another tools.
    """

    def unwrap(self) -> T:
        return self.value

    def rewrap(self, value: T) -> "BaseAnnotation[T]":
        return type(self)(value)

    def __eq__(self, other: "BaseAnnotation[T]") -> bool:
        if type(self) is not type(other):
            return False
        return self.unwrap() == other.unwrap()

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.value!r})"


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


class quote(BaseAnnotation[T]):
    """
    Simple wrapper to mark an expression as a different type so it will not be coerced
    by Prefect. For example, if you want to return a state from a flow without having
    the flow assume that state.

    quote will also instruct prefect to ignore introspection of the wrapped object
    when passed as flow or task parameter. Parameter introspection can be a
    significant performance hit when the object is a large collection,
    e.g. a large dictionary or DataFrame, and each element needs to be visited. This
    will disable task dependency tracking for the wrapped object, but likely will
    increase performance.

    ```
    @task
    def my_task(df):
        ...

    @flow
    def my_flow():
        my_task(quote(df))
    ```
    """

    def unquote(self) -> T:
        return self.unwrap()


# Backwards compatibility stub for `Quote` class
class Quote(quote):
    def __init__(self, expr):
        warnings.warn(
            "Use of `Quote` is deprecated. Use `quote` instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(expr)


class NotSet:
    """
    Singleton to distinguish `None` from a value that is not provided by the user.
    """
