"""
Futures represent the execution of a task and allow retrieval of the task run's state.

This module contains the definition for futures as well as utilities for resolving
futures in nested data structures.
"""
import asyncio
import warnings
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Generic,
    Optional,
    TypeVar,
    Union,
    cast,
    overload,
)
from uuid import UUID

import anyio

from prefect.client.orion import OrionClient
from prefect.client.utilities import inject_client
from prefect.states import State
from prefect.utilities.asyncutils import (
    A,
    Async,
    Sync,
    run_async_from_worker_thread,
    run_sync_in_worker_thread,
    sync,
)
from prefect.utilities.collections import visit_collection

if TYPE_CHECKING:
    from prefect.task_runners import BaseTaskRunner


R = TypeVar("R")


class PrefectFuture(Generic[R, A]):
    """
    Represents the result of a computation happening in a task runner.

    When tasks are called, they are submitted to a task runner which creates a future
    for access to the state and result of the task.

    Examples:
        Define a task that returns a string

        >>> from prefect import flow, task
        >>> @task
        >>> def my_task() -> str:
        >>>     return "hello"

        Calls of this task in a flow will return a future

        >>> @flow
        >>> def my_flow():
        >>>     future = my_task()  # PrefectFuture[str, Sync] includes result type
        >>>     future.task_run.id  # UUID for the task run

        Wait for the task to complete

        >>> @flow
        >>> def my_flow():
        >>>     future = my_task()
        >>>     final_state = future.wait()

        Wait N sconds for the task to complete

        >>> @flow
        >>> def my_flow():
        >>>     future = my_task()
        >>>     final_state = future.wait(0.1)
        >>>     if final_state:
        >>>         ... # Task done
        >>>     else:
        >>>         ... # Task not done yet

        Wait for a task to complete and retrieve its result

        >>> @flow
        >>> def my_flow():
        >>>     future = my_task()
        >>>     result = future.result()
        >>>     assert result == "hello"

        Wait N seconds for a task to complete and retrieve its result

        >>> @flow
        >>> def my_flow():
        >>>     future = my_task()
        >>>     result = future.result(timeout=5)
        >>>     assert result == "hello"

        Retrieve the state of a task without waiting for completion

        >>> @flow
        >>> def my_flow():
        >>>     future = my_task()
        >>>     state = future.get_state()
    """

    def __init__(
        self,
        name: str,
        key: UUID,
        task_runner: "BaseTaskRunner",
        asynchronous: A = True,
        _final_state: State[R] = None,  # Exposed for testing
    ) -> None:
        self.key = key
        self.name = name
        self.asynchronous = asynchronous
        self.task_run = None
        self._final_state = _final_state
        self._exception: Optional[Exception] = None
        self._task_runner = task_runner
        self._submitted = anyio.Event()

        self._loop = asyncio.get_running_loop()

    @overload
    def wait(
        self: "PrefectFuture[R, Async]", timeout: None = None
    ) -> Awaitable[State[R]]:
        ...

    @overload
    def wait(self: "PrefectFuture[R, Sync]", timeout: None = None) -> State[R]:
        ...

    @overload
    def wait(
        self: "PrefectFuture[R, Async]", timeout: float
    ) -> Awaitable[Optional[State[R]]]:
        ...

    @overload
    def wait(self: "PrefectFuture[R, Sync]", timeout: float) -> Optional[State[R]]:
        ...

    def wait(self, timeout=None):
        """
        Wait for the run to finish and return the final state

        If the timeout is reached before the run reaches a final state,
        `None` is returned.
        """
        if self.asynchronous:
            return self._wait(timeout=timeout)
        else:
            # type checking cannot handle the overloaded timeout passing
            return sync(self._wait, timeout=timeout)  # type: ignore

    @overload
    async def _wait(self, timeout: None = None) -> State[R]:
        ...

    @overload
    async def _wait(self, timeout: float) -> Optional[State[R]]:
        ...

    async def _wait(self, timeout=None):
        """
        Async implementation for `wait`
        """
        await self._wait_for_submission()

        if self._final_state:
            return self._final_state

        self._final_state = await self._task_runner.wait(self.key, timeout)
        return self._final_state

    @overload
    def result(
        self: "PrefectFuture[R, Sync]",
        timeout: float = None,
        raise_on_failure: bool = True,
    ) -> R:
        ...

    @overload
    def result(
        self: "PrefectFuture[R, Sync]",
        timeout: float = None,
        raise_on_failure: bool = False,
    ) -> Union[R, Exception]:
        ...

    @overload
    def result(
        self: "PrefectFuture[R, Async]",
        timeout: float = None,
        raise_on_failure: bool = True,
    ) -> Awaitable[R]:
        ...

    @overload
    def result(
        self: "PrefectFuture[R, Async]",
        timeout: float = None,
        raise_on_failure: bool = False,
    ) -> Awaitable[Union[R, Exception]]:
        ...

    def result(self, timeout: float = None, raise_on_failure: bool = True):
        """
        Wait for the run to finish and return the final state.

        If the timeout is reached before the run reaches a final state, a `TimeoutError`
        will be raised.

        If `raise_on_failure` is `True` and the task run failed, the task run's
        exception will be raised.
        """
        if self.asynchronous:
            return self._result(timeout=timeout, raise_on_failure=raise_on_failure)
        else:
            return sync(
                self._result, timeout=timeout, raise_on_failure=raise_on_failure
            )

    async def _result(self, timeout: float = None, raise_on_failure: bool = True):
        """
        Async implementation of `result`
        """
        final_state = await self._wait(timeout=timeout)
        if not final_state:
            raise TimeoutError("Call timed out before task finished.")
        return await final_state.result(raise_on_failure=raise_on_failure, fetch=True)

    @overload
    def get_state(
        self: "PrefectFuture[R, Async]", client: OrionClient = None
    ) -> Awaitable[State[R]]:
        ...

    @overload
    def get_state(
        self: "PrefectFuture[R, Sync]", client: OrionClient = None
    ) -> State[R]:
        ...

    def get_state(self, client: OrionClient = None):
        """
        Get the current state of the task run.
        """
        if self.asynchronous:
            return cast(Awaitable[State[R]], self._get_state(client=client))
        else:
            return cast(State[R], sync(self._get_state, client=client))

    @inject_client
    async def _get_state(self, client: OrionClient = None) -> State[R]:
        assert client is not None  # always injected

        # We must wait for the task run id to be populated
        await self._wait_for_submission()

        task_run = await client.read_task_run(self.task_run.id)

        if not task_run:
            raise RuntimeError("Future has no associated task run in the server.")

        # Update the task run reference
        self.task_run = task_run
        return task_run.state

    async def _wait_for_submission(self):
        import asyncio

        # TODO: This spin lock is not performant but is necessary for cases where a
        #       future is created in a separate event loop i.e. when a sync task is
        #       called in an async flow
        if not asyncio.get_running_loop() == self._loop:
            while not self.task_run:
                await anyio.sleep(0)
        else:
            await self._submitted.wait()

    def __hash__(self) -> int:
        return hash(self.key)

    def __repr__(self) -> str:
        return f"PrefectFuture({self.name!r})"

    def __bool__(self) -> bool:
        warnings.warn(
            "A 'PrefectFuture' from a task call was cast to a boolean; "
            "did you mean to check the result of the task instead? "
            "e.g. `if my_task().result(): ...`",
            stacklevel=2,
        )
        return True


async def resolve_futures_to_data(
    expr: Union[PrefectFuture[R, Any], Any]
) -> Union[R, Any]:
    """
    Given a Python built-in collection, recursively find `PrefectFutures` and build a
    new collection with the same structure with futures resolved to their results.
    Resolving futures to their results may wait for execution to complete and require
    communication with the API.

    Unsupported object types will be returned without modification.
    """

    def resolve_future(expr):
        if isinstance(expr, PrefectFuture):
            return run_async_from_worker_thread(expr._result)
        else:
            return expr

    return await run_sync_in_worker_thread(
        visit_collection, expr, visit_fn=resolve_future, return_data=True
    )


async def resolve_futures_to_states(
    expr: Union[PrefectFuture[R, Any], Any]
) -> Union[State[R], Any]:
    """
    Given a Python built-in collection, recursively find `PrefectFutures` and build a
    new collection with the same structure with futures resolved to their final states.
    Resolving futures to their final states may wait for execution to complete.

    Unsupported object types will be returned without modification.
    """

    def resolve_future(expr):
        if isinstance(expr, PrefectFuture):
            return run_async_from_worker_thread(expr._wait)
        else:
            return expr

    return await run_sync_in_worker_thread(
        visit_collection, expr, visit_fn=resolve_future, return_data=True
    )


def call_repr(__fn: Callable, *args: Any, **kwargs: Any) -> str:
    """
    Generate a repr for a function call as "fn_name(arg_value, kwarg_name=kwarg_value)"
    """

    name = __fn.__name__

    # TODO: If this computation is concerningly expensive, we can iterate checking the
    #       length at each arg or avoid calling `repr` on args with large amounts of
    #       data
    call_args = ", ".join(
        [repr(arg) for arg in args]
        + [f"{key}={repr(val)}" for key, val in kwargs.items()]
    )

    # Enforce a maximum length
    if len(call_args) > 100:
        call_args = call_args[:100] + "..."

    return f"{name}({call_args})"
