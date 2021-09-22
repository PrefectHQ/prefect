"""
Base workflow class and decorator
"""
# This file requires type-checking with pyright because mypy does not yet support PEP612
# See https://github.com/python/mypy/issues/8645

import inspect
from functools import update_wrapper, partial
from typing import (
    Any,
    Awaitable,
    Callable,
    Coroutine,
    Iterable,
    TypeVar,
    cast,
    overload,
    Generic,
    NoReturn,
    Union,
    Type,
)

from typing_extensions import ParamSpec

from prefect import State
from prefect.executors import BaseExecutor, LocalExecutor
from prefect.orion.utilities.functions import parameter_schema
from prefect.utilities.asyncio import is_async_fn
from prefect.utilities.callables import get_call_parameters
from prefect.utilities.hashing import file_hash

T = TypeVar("T")  # Generic type var for capturing the inner return type of async funcs
R = TypeVar("R")  # The return type of the user's function
P = ParamSpec("P")  # The parameters of the flow


class Flow(Generic[P, R]):
    """
    A Prefect workflow definition

    See the `@flow` decorator for usage details.

    Wraps a user's function with an entrypoint to the Prefect engine. To preserve the
    input and output signatures of the user's functions, we use the generic type
    variables P and R for "Parameters" and "Return Type" respectively.
    """

    def __init__(
        self,
        fn: Callable[P, R],
        name: str = None,
        version: str = None,
        executor: Union[Type[BaseExecutor], BaseExecutor] = LocalExecutor,
        description: str = None,
    ):
        if not callable(fn):
            raise TypeError("'fn' must be callable")

        self.name = name or fn.__name__.replace("_", "-")
        self.executor = executor() if isinstance(executor, type) else executor

        self.description = description or inspect.getdoc(fn)
        update_wrapper(self, fn)
        self.fn = fn
        self.isasync = is_async_fn(self.fn)

        # Version defaults to a hash of the function's file
        flow_file = fn.__globals__.get("__file__")  # type: ignore
        self.version = version or (file_hash(flow_file) if flow_file else None)

        self.parameters = parameter_schema(self.fn)

    @overload
    def __call__(
        self: "Flow[P, NoReturn]", *args: P.args, **kwargs: P.kwargs
    ) -> State[T]:
        # `NoReturn` matches if a type can't be inferred for the function which stops a
        # sync function from matching the `Coroutine` overload
        ...

    @overload
    def __call__(
        self: "Flow[P, Coroutine[Any, Any, T]]", *args: P.args, **kwargs: P.kwargs
    ) -> Awaitable[State[T]]:
        ...

    @overload
    def __call__(self: "Flow[P, T]", *args: P.args, **kwargs: P.kwargs) -> State[T]:
        ...

    def __call__(
        self,
        *args: "P.args",
        **kwargs: "P.kwargs",
    ):
        """
        Run the flow.

        If writing an async flow, this call must be awaited.

        Will create a new flow run in the backing API

        Args:
            *args: Arguments to run the flow with
            **kwargs: Keyword arguments to run the flow with

        Returns:
            The final state of the flow run

        Examples:

            Define a flow

            >>> @flow
            >>> def my_flow(name):
            >>>     print(f"hello {name}")
            >>>     return f"goodbye {name}"

            Run a flow

            >>> my_flow("marvin")
            hello marvin

            Run a flow and get the returned result

            >>> get_result(my_flow("marvin"))
            "goodbye marvin"

            Run a flow with additional tags

            >>> from prefect import tags
            >>> with tags("db", "blue"):
            >>>    my_flow("foo")
        """
        from prefect.engine import enter_flow_run_engine_from_flow_call

        # Convert the call args/kwargs to a parameter dict
        parameters = get_call_parameters(self.fn, args, kwargs)

        return enter_flow_run_engine_from_flow_call(self, parameters)


@overload
def flow(__fn: Callable[P, R]) -> Flow[P, R]:
    ...


@overload
def flow(
    *,
    name: str = None,
    version: str = None,
    executor: BaseExecutor = LocalExecutor,
    description: str = None,
    tags: Iterable[str] = None,
) -> Callable[[Callable[P, R]], Flow[P, R]]:
    ...


def flow(
    __fn=None,
    *,
    name: str = None,
    version: str = None,
    executor: BaseExecutor = LocalExecutor,
    description: str = None,
):
    """
    Decorator to designate a function as a Prefect workflow.

    This decorator may be used for asynchronous or synchronous functions.

    Args:
        name: An optional name for the flow. If not provided, the name will be inferred
            from the given function.
        version: An optional version string for the flow, If not provided, we will
            attempt to create a version string as a hash of the file containing the
            wrapped function. If the file cannot be located, the version will be null.
        executor: An optional executor to use for task execution within the flow. If
            not provided, a `LocalExecutor` will be instantiated.
        description: An optional string description for the flow. If not provided, the
            description will be pulled from the docstring for the decorated function.

    Returns:
        A callable `Flow` object which, when called, will run the flow and return its
        final state.

    Examples:
        Define a simple flow

        >>> from prefect import flow
        >>> @flow
        >>> def add(x, y):
        >>>     return x + y

        Define an async flow

        >>> @flow
        >>> async def add(x, y):
        >>>     return x + y

        Define a flow with a version and description

        >>> @flow(version="first-flow", description="This flow is empty!")
        >>> def my_flow():
        >>>     pass

        Define a flow with a custom name

        >>> @flow(name="The Ultimate Flow")
        >>> def my_flow():
        >>>     pass

        Define a flow that submits its tasks to dask

        >>> from prefect.executors import DaskExecutor
        >>> @flow(executor=DaskExecutor)
        >>> def my_flow():
        >>>     pass

    """
    if __fn:
        return cast(
            Flow[P, R],
            Flow(
                fn=__fn,
                name=name,
                version=version,
                executor=executor,
                description=description,
            ),
        )
    else:
        return cast(
            Callable[[Callable[P, R]], Flow[P, R]],
            partial(
                flow,
                name=name,
                version=version,
                executor=executor,
                description=description,
            ),
        )
