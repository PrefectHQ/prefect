import warnings
from operator import itemgetter
from typing import Any, cast

from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema, to_json
from typing_extensions import Self, TypeVar

T = TypeVar("T", infer_variance=True)


class BaseAnnotation(tuple[T]):
    """
    Base class for Prefect annotation types.

    Inherits from `tuple` for unpacking support in other tools.
    """

    __slots__ = ()

    def __new__(cls, value: T) -> Self:
        return super().__new__(cls, (value,))

    # use itemgetter to minimise overhead, just like namedtuple generated code would
    value: T = cast(T, property(itemgetter(0)))

    def unwrap(self) -> T:
        return self[0]

    def rewrap(self, value: T) -> Self:
        return type(self)(value)

    def __eq__(self, other: Any) -> bool:
        if type(self) is not type(other):
            return False
        return super().__eq__(other)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self[0]!r})"


class unmapped(BaseAnnotation[T]):
    """
    Wrapper for iterables.

    Indicates that this input should be sent as-is to all runs created during a mapping
    operation instead of being split.
    """

    def __getitem__(self, _: object) -> T:  # type: ignore[override]  # pyright: ignore[reportIncompatibleMethodOverride]
        # Internally, this acts as an infinite array where all items are the same value
        return super().__getitem__(0)


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
class Quote(quote[T]):
    def __new__(cls, expr: T) -> Self:
        warnings.warn(
            "Use of `Quote` is deprecated. Use `quote` instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return super().__new__(cls, expr)


class NotSet:
    """
    Singleton to distinguish `None` from a value that is not provided by the user.
    """


class freeze(BaseAnnotation[T]):
    """
    Wrapper for parameters in deployments.

    Indicates that this parameter should be frozen in the UI and not editable
    when creating flow runs from this deployment.

    Example:
    ```python
    @flow
    def my_flow(customer_id: str):
        # flow logic

    deployment = my_flow.deploy(parameters={"customer_id": freeze("customer123")})
    ```
    """

    def __new__(cls, value: T) -> Self:
        try:
            to_json(value)
        except Exception:
            raise ValueError("Value must be JSON serializable")
        return super().__new__(cls, value)

    def unfreeze(self) -> T:
        """Return the unwrapped value."""
        return self.unwrap()

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source: type[Any], handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls,  # Use the class itself as the validator
            core_schema.any_schema(),
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda x: x.unfreeze()  # Serialize by unwrapping the value
            ),
        )
