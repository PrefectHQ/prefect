from collections import OrderedDict
from collections.abc import Iterator as IteratorABC
from dataclasses import fields, is_dataclass
from functools import partial
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Optional,
    Union,
    overload,
    cast,
    TypeVar,
    Generic,
)
from unittest.mock import Mock
from uuid import UUID

import prefect
from prefect.client import OrionClient
from prefect.orion.schemas.states import State
from prefect.utilities.asyncio import sync_compatible

if TYPE_CHECKING:
    from prefect.executors import BaseExecutor
    from prefect.orion.schemas.core import FlowRun, TaskRun


R = TypeVar("R")


class PrefectFuture(Generic[R]):
    def __init__(
        self,
        flow_run_id: UUID,
        client: OrionClient,
        executor: "BaseExecutor",
        task_run_id: UUID = None,
        _final_state: Any = None,  # Exposed for testing
    ) -> None:
        self.flow_run_id = flow_run_id
        self.task_run_id = task_run_id
        self.run_id = self.task_run_id or self.flow_run_id
        self._client = client
        self._final_state: Any = _final_state
        self._exception: Optional[Exception] = None
        self._executor = executor

    @overload
    async def wait(self, timeout: float) -> Optional[State[R]]:
        ...

    @overload
    async def wait(self, timeout: None = None) -> State[R]:
        ...

    @sync_compatible
    async def wait(self, timeout=None):
        """
        Wait for the run to finish and return the final state

        If the timeout is reached before the run reaches a final state,
        `None` is returned.
        """
        if self._final_state:
            return self._final_state

        state = await self.get_state()
        if (state.is_completed() or state.is_failed()) and state.data:
            return state

        self._final_state = await self._executor.wait(self, timeout)

        return self._final_state

    @sync_compatible
    async def get_state(self) -> State[R]:
        run: Union[FlowRun, TaskRun]

        if self.task_run_id:
            run = await self._client.read_task_run(self.task_run_id)

        else:
            run = await self._client.read_flow_run(self.flow_run_id)

        if not run:
            raise RuntimeError("Future has no associated run in the server.")

        return run.state

    def __hash__(self) -> int:
        return hash(self.run_id)


async def future_to_data(future: PrefectFuture[R]) -> R:
    return await prefect.get_result(await future.wait())


async def future_to_state(future: PrefectFuture[R]) -> State[R]:
    return await future.wait()


async def resolve_futures(
    expr, resolve_fn: Callable[[PrefectFuture], Awaitable[Any]] = future_to_data
):
    """
    Given a Python built-in collection, recursively find `PrefectFutures` and build a
    new collection with the same structure with futures resolved by `resolve_fn`.

    Unsupported object types will be returned without modification.

    By default, futures are resolved into their underlying data which may wait for
    execution to complete. `resolve_fn` can be passed to convert `PrefectFutures` into
    futures native to another executor.
    """
    # Ensure that the `resolve_fn` is passed on recursive calls
    recurse = partial(resolve_futures, resolve_fn=resolve_fn)

    if isinstance(expr, PrefectFuture):
        return await resolve_fn(expr)

    if isinstance(expr, Mock):
        # Explicitly do not coerce mock objects
        return expr

    # Get the expression type; treat iterators like lists
    typ = list if isinstance(expr, IteratorABC) else type(expr)
    typ = cast(type, typ)  # mypy treats this as 'object' otherwise and complains

    # If it's a python collection, recursively create a collection of the same type with
    # resolved futures

    if typ in (list, tuple, set):
        return typ([await recurse(o) for o in expr])

    if typ in (dict, OrderedDict):
        assert isinstance(expr, (dict, OrderedDict))  # typecheck assertion
        return typ([[await recurse(k), await recurse(v)] for k, v in expr.items()])

    if is_dataclass(expr) and not isinstance(expr, type):
        return typ(
            **{f.name: await recurse(getattr(expr, f.name)) for f in fields(expr)},
        )

    # If not a supported type, just return it
    return expr
