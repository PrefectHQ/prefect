# type: ignore
# mypy does not yet support `ParamSpec`; this file should be type checked with pyright

import inspect
from functools import update_wrapper
from typing import (
    Any,
    Awaitable,
    Callable,
    Generic,
    Iterable,
    Type,
    TypeVar,
    Union,
    cast,
    overload,
)

from typing_extensions import Literal, ParamSpec

from prefect import State
from prefect.executors import BaseExecutor, LocalExecutor
from prefect.orion.schemas.core import FlowRun
from prefect.orion.utilities.functions import parameter_schema
from prefect.utilities.callables import get_call_parameters
from prefect.utilities.hashing import file_hash

ParametersT = ParamSpec("ParametersT")  # The parameters of the flow
ReturnT = TypeVar("ReturnT")  # The return type wrapped in an `Awaitable` if async
ResultT = TypeVar("ResultT")  # The return type of the user's functino


class Flow(Generic[ParametersT, ReturnT]):
    """
    Base class representing Prefect workflows.
    """

    @overload
    def __init__(
        self: "Flow[ParametersT, Awaitable[ResultT]]",
        fn: Callable[ParametersT, Awaitable[ResultT]],
        name: str = None,
        version: str = None,
        executor: BaseExecutor = None,
        description: str = None,
        tags: Iterable[str] = None,
    ):
        ...

    @overload
    def __init__(
        self: "Flow[ParametersT, ResultT]",
        fn: Callable[ParametersT, ResultT],
        name: str = None,
        version: str = None,
        executor: BaseExecutor = None,
        description: str = None,
        tags: Iterable[str] = None,
    ):
        ...

    def __init__(
        self,
        fn: Any,
        name: str = None,
        version: str = None,
        executor: BaseExecutor = None,
        description: str = None,
        tags: Iterable[str] = None,
    ):
        if not callable(fn):
            raise TypeError("'fn' must be callable")

        self.name = name or fn.__name__

        self.tags = set(tags if tags else [])
        self.executor = executor or LocalExecutor()

        self.description = description or inspect.getdoc(fn)
        update_wrapper(self, fn)
        self.fn = fn
        self.isasync = inspect.iscoroutinefunction(self.fn)

        # Version defaults to a hash of the function's file
        flow_file = fn.__globals__.get("__file__")  # type: ignore
        self.version = version or (file_hash(flow_file) if flow_file else None)

        self.parameters = parameter_schema(self.fn)

    @overload
    def __call__(
        self: "Flow[ParametersT, Awaitable[ResultT]]",
        *args: "ParametersT.args",
        **kwargs: "ParametersT.kwargs",
    ) -> Awaitable[State[ResultT]]:
        ...

    @overload
    def __call__(
        self: "Flow[ParametersT, ResultT]",
        *args: "ParametersT.args",
        **kwargs: "ParametersT.kwargs",
    ) -> State[ResultT]:
        ...

    def __call__(self, *args, **kwargs):
        from prefect.engine import enter_flow_run_engine

        # Convert the call args/kwargs to a parameter dict
        parameters = get_call_parameters(self.fn, args, kwargs)

        return enter_flow_run_engine(self, parameters)


@overload
def to_flow(
    __fn: Callable[ParametersT, Awaitable[ReturnT]]
) -> Callable[ParametersT, Awaitable[State[ReturnT]]]:
    ...


@overload
def to_flow(
    __fn: Callable[ParametersT, ReturnT]
) -> Callable[ParametersT, State[ReturnT]]:
    ...


def to_flow(fn):
    return cast(
        Callable[ParametersT, Union[State[ReturnT], Awaitable[State[ReturnT]]]],
        Flow(
            fn=fn,
            name=name,
            version=version,
            executor=executor,
            description=description,
            tags=tags,
        ),
    )


@overload
def flow(
    *,
    name: str = None,
    version: str = None,
    executor: BaseExecutor = None,
    description: str = None,
    tags: Iterable[str] = None,
) -> Callable[
    [Callable[ParametersT, Awaitable[ReturnT]]],
    Callable[ParametersT, Awaitable[State[ReturnT]]],
]:
    ...


@overload
def flow(
    *,
    name: str = None,
    version: str = None,
    executor: BaseExecutor = None,
    description: str = None,
    tags: Iterable[str] = None,
) -> Callable[[Callable[ParametersT, ReturnT]], Callable[ParametersT, State[ReturnT]]]:
    ...


def flow(
    __fn=None, *, name=None, version=None, executor=None, description=None, tags=None
):

    if __fn:
        return to_flow(__fn)
    else:
        return to_flow
