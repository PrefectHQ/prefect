"""
Task run futures.
"""
from typing import (
    TYPE_CHECKING,
    Any,
    Union,
    Optional,
    overload,
    TypeVar,
    Generic,
)
from uuid import UUID

import prefect
from prefect.client import OrionClient
from prefect.orion.schemas.states import State
from prefect.utilities.asyncio import sync_compatible
from prefect.utilities.collections import visit_collection

if TYPE_CHECKING:
    from prefect.executors import BaseExecutor


R = TypeVar("R")


class PrefectFuture(Generic[R]):
    """
    Represents the result of a computation happening in an executor.

    When tasks are called, they are submitted to an executor which creates a future for
    access to the state and result of the task.

    Examples:
        Define a task that returns a string

        >>> from prefect import flow, task
        >>> @task
        >>> def my_task() -> str:
        >>>     return "hello"

        Calls of this task in a flow will return a future

        >>> @flow
        >>> def my_flow():
        >>>     future = my_task()  # PrefectFuture[str] includes result type
        >>>     future.run_id  # UUID for the task run

        Wait for the task to complete

        >>> @flow
        >>> def my_flow():
        >>>     future = my_task()
        >>>     final_state = future.wait()

        Wait for a task to complete and retrieve its result

        >>> @flow
        >>> def my_flow():
        >>>     future = my_task()
        >>>     state = future.wait()
        >>>     result = state.result()
        >>>     assert result == "hello"

        Retrieve the state of a task without waiting for completion

        >>> @flow
        >>> def my_flow():
        >>>     future = my_task()
        >>>     state = future.get_state()
    """

    def __init__(
        self,
        run_id: UUID,
        client: OrionClient,
        executor: "BaseExecutor",
        _final_state: State[R] = None,  # Exposed for testing
    ) -> None:
        self.run_id = run_id
        self._client = client
        self._final_state = _final_state
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

        self._final_state = await self._executor.wait(self, timeout)
        return self._final_state

    @sync_compatible
    async def get_state(self) -> State[R]:
        task_run = await self._client.read_task_run(self.run_id)

        if not task_run:
            raise RuntimeError("Future has no associated task run in the server.")

        return task_run.state

    def __hash__(self) -> int:
        return hash(self.run_id)


async def resolve_futures_to_data(expr: Union[PrefectFuture[R], Any]) -> Union[R, Any]:
    """
    Given a Python built-in collection, recursively find `PrefectFutures` and build a
    new collection with the same structure with futures resolved to their results.
    Resolving futures to their results may wait for execution to complete and require
    communication with the API.

    Unsupported object types will be returned without modification.
    """

    async def visit_fn(expr):
        if isinstance(expr, prefect.futures.PrefectFuture):
            return (await expr.wait()).result(raise_on_failure=False)
        else:
            return expr

    return await visit_collection(expr, visit_fn=visit_fn, return_data=True)


async def resolve_futures_to_states(
    expr: Union[PrefectFuture[R], Any]
) -> Union[State, Any]:
    """
    Given a Python built-in collection, recursively find `PrefectFutures` and build a
    new collection with the same structure with futures resolved to their final states.
    Resolving futures to their final states may wait for execution to complete.

    Unsupported object types will be returned without modification.
    """

    async def visit_fn(expr):
        if isinstance(expr, prefect.futures.PrefectFuture):
            return await expr.wait()
        else:
            return expr

    return await visit_collection(expr, visit_fn=visit_fn, return_data=True)
