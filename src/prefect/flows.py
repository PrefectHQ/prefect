from __future__ import annotations

import inspect
from functools import update_wrapper
from functools import partial
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Coroutine,
    Iterable,
    TypeVar,
    cast,
    overload,
    Union,
    Generic,
)

from typing_extensions import ParamSpec

from prefect import State
from prefect.executors import BaseExecutor, LocalExecutor
from prefect.orion.utilities.functions import parameter_schema
from prefect.utilities.asyncio import is_async_fn
from prefect.utilities.callables import get_call_parameters
from prefect.utilities.hashing import file_hash

T = TypeVar("T")
ResultT = TypeVar("ResultT")  # The return type of the user's function
ParamsT = ParamSpec("ParamsT")  # The parameters of the flow


class Flow(Generic[ParamsT, ResultT]):
    """
    Base class representing Prefect workflows.
    """

    def __init__(
        self,
        fn: Callable[ParamsT, ResultT],
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
        self.isasync = is_async_fn(self.fn)

        # Version defaults to a hash of the function's file
        flow_file = fn.__globals__.get("__file__")  # type: ignore
        self.version = version or (file_hash(flow_file) if flow_file else None)

        self.parameters = parameter_schema(self.fn)

    @overload
    def __call__(
        self: "Flow[ParamsT, Coroutine[Any, Any, T]]",
        *args: "ParamsT.args",
        **kwargs: "ParamsT.kwargs",
    ) -> Awaitable[State[T]]:
        ...

    @overload
    def __call__(
        self: "Flow[ParamsT, T]",
        *args: "ParamsT.args",
        **kwargs: "ParamsT.kwargs",
    ) -> State[T]:
        ...

    def __call__(
        self,
        *args: "ParamsT.args",
        **kwargs: "ParamsT.kwargs",
    ):
        from prefect.engine import enter_flow_run_engine

        # Convert the call args/kwargs to a parameter dict
        parameters = get_call_parameters(self.fn, args, kwargs)

        return enter_flow_run_engine(self, parameters)


@overload
def flow(__fn: Callable[ParamsT, ResultT]) -> Flow[ParamsT, ResultT]:
    ...


@overload
def flow(
    *,
    name: str = None,
    version: str = None,
    executor: BaseExecutor = None,
    description: str = None,
    tags: Iterable[str] = None,
) -> Callable[[Callable[ParamsT, ResultT]], Flow[ParamsT, ResultT]]:
    ...


def flow(
    __fn=None,
    *,
    name: str = None,
    version: str = None,
    executor: BaseExecutor = None,
    description: str = None,
    tags: Iterable[str] = None,
):
    if __fn:
        return cast(Flow[ParamsT, ResultT], Flow(fn=__fn))
    else:
        return cast(
            Callable[[Callable[ParamsT, ResultT]], Flow[ParamsT, ResultT]],
            partial(
                Flow,
                name=name,
                version=version,
                executor=executor,
                description=description,
                tags=tags,
            ),
        )
