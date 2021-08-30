from collections import OrderedDict
from collections.abc import Iterator as IteratorABC
from dataclasses import fields, is_dataclass
from functools import partial
from typing import TYPE_CHECKING, Any, Callable, Optional
from unittest.mock import Mock
from uuid import UUID

from prefect.client import OrionClient
from prefect.orion.schemas.states import State, StateType
from prefect.orion.states import StateSet, is_state, is_state_iterable
from prefect.utilities.collections import ensure_iterable
from prefect.utilities.asyncio import run_async_from_worker_thread

if TYPE_CHECKING:
    from prefect.executors import BaseExecutor


class PrefectFuture:
    def __init__(
        self,
        flow_run_id: UUID,
        client: OrionClient,
        executor: "BaseExecutor",
        task_run_id: UUID = None,
        _result: Any = None,  # Exposed for testing
    ) -> None:
        self.flow_run_id = flow_run_id
        self.task_run_id = task_run_id
        self.run_id = self.task_run_id or self.flow_run_id
        self._client = client
        self._result: Any = _result
        self._exception: Optional[Exception] = None
        self._executor = executor

    def result(self, timeout: float = None) -> Optional[State]:
        # TODO: We can make this a dual sync/async interface by returning the coro
        #       directly if this is a future from an async flow/task. This bool just
        #       needs to be attached to the class at some point.
        #       Once this is async compatible, `aresult` can be made private
        return run_async_from_worker_thread(self.aresult, timeout)

    def get_state(self) -> State:
        return run_async_from_worker_thread(self.get_state)

    async def aresult(self, timeout: float = None) -> Optional[State]:
        """
        Return the state of the run the future represents
        """
        if self._result:
            return self._result

        state = await self.aget_state()
        if (state.is_completed() or state.is_failed()) and state.data:
            return state

        self._result = await self._executor.wait(self, timeout)

        return self._result

    async def aget_state(self) -> State:
        if self.task_run_id:
            run = await self._client.read_task_run(self.task_run_id)

        else:
            run = await self._client.read_flow_run(self.flow_run_id)

        if not run:
            raise RuntimeError("Future has no associated run in the server.")
        return run.state

    def __hash__(self) -> int:
        return hash(self.run_id)


async def future_to_data(future: PrefectFuture) -> Any:
    return (await future.aresult()).data


async def future_to_state(future: PrefectFuture) -> Any:
    return await future.aresult()


async def resolve_futures(
    expr, resolve_fn: Callable[[PrefectFuture], Any] = future_to_data
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

    # If it's a python collection, recursively create a collection of the same type with
    # resolved futures

    if typ in (list, tuple, set):
        return typ([await recurse(o) for o in expr])

    if typ in (dict, OrderedDict):
        return typ([[await recurse(k), await recurse(v)] for k, v in expr.items()])

    if is_dataclass(expr) and not isinstance(expr, type):
        return typ(
            **{f.name: await recurse(getattr(expr, f.name)) for f in fields(expr)},
        )

    # If not a supported type, just return it
    return expr


async def return_val_to_state(result: Any) -> State:
    """
    Given a return value from a user-function, create a `State` the run should
    be placed in.

    - If data is returned, we create a 'COMPLETED' state with the data
    - If a single state is returned and is not wrapped in a future, we use that state
    - If an iterable of states are returned, we apply the aggregate rule
    - If a future or iterable of futures is returned, we resolve it into states then
        apply the aggregate rule

    The aggregate rule says that given multiple states we will determine the final state
    such that:

    - If any states are not COMPLETED the final state is FAILED
    - If all of the states are COMPLETED the final state is COMPLETED
    - The states will be placed in the final state `data` attribute

    The aggregate rule is applied to _single_ futures to distinguish from returning a
    _single_ state. This prevents a flow from assuming the state of a single returned
    task future.
    """
    # States returned directly are respected without applying a rule
    if is_state(result):
        return result

    # Ensure any futures are resolved
    result = await resolve_futures(result, resolve_fn=future_to_state)

    # If we resolved a task future or futures into states, we will determine a new state
    # from their aggregate
    if is_state(result) or is_state_iterable(result):
        states = StateSet(ensure_iterable(result))

        # Determine the new state type
        new_state_type = (
            StateType.COMPLETED if states.all_completed() else StateType.FAILED
        )

        # Generate a nice message for the aggregate
        if states.all_completed():
            message = "All states completed."
        elif states.any_failed():
            message = f"{states.fail_count}/{states.total_count} states failed."
        elif not states.all_final():
            message = (
                f"{states.not_final_count}/{states.total_count} states did not reach a "
                "final state."
            )
        else:
            message = "Given states: " + states.counts_message()

        # TODO: We may actually want to set the data to a `StateSet` object and just allow
        #       it to be unpacked into a tuple and such so users can interact with it
        return State(data=result, type=new_state_type, message=message)

    # Otherwise, they just gave data and this is a completed result
    return State(type=StateType.COMPLETED, data=result)
