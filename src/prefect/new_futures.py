import abc
import concurrent.futures
import inspect
import uuid
from functools import partial
from typing import Any, Generic, Optional, Set, Union, cast

from typing_extensions import TypeVar

from prefect.client.orchestration import get_client
from prefect.client.schemas.objects import TaskRun
from prefect.exceptions import ObjectNotFound
from prefect.states import Pending, State
from prefect.utilities.annotations import quote
from prefect.utilities.asyncutils import run_coro_as_sync
from prefect.utilities.collections import StopVisiting, visit_collection

F = TypeVar("F")


class PrefectFuture(abc.ABC, Generic[F]):
    """
    Abstract base class for Prefect futures. A Prefect future is a handle to the
    asynchronous execution of a task run. It provides methods to wait for the task
    to complete and to retrieve the result of the task run.
    """

    def __init__(self, task_run_id: uuid.UUID, wrapped_future: F):
        self._task_run_id = task_run_id
        self._wrapped_future = wrapped_future
        self._final_state = None

    @property
    def task_run_id(self) -> uuid.UUID:
        """The ID of the task run associated with this future"""
        return self._task_run_id

    @property
    def wrapped_future(self) -> F:
        """The underlying future object wrapped by this Prefect future"""
        return self._wrapped_future

    @property
    def state(self) -> State:
        """The current state of the task run associated with this future"""
        if self._final_state:
            return self._final_state
        client = get_client(sync_client=True)
        try:
            task_run = cast(TaskRun, client.read_task_run(task_run_id=self.task_run_id))
        except ObjectNotFound:
            # We'll be optimistic and assume this task will eventually start
            # TODO: Consider using task run events to wait for the task to start
            return Pending()
        return task_run.state or Pending()

    @abc.abstractmethod
    def wait(self, timeout: Optional[float] = None) -> None:
        ...
        """
        Wait for the task run to complete. 
        
        If the task run has already completed, this method will return immediately.

        Args:
            - timeout: The maximum number of seconds to wait for the task run to complete.
              If the task run has not completed after the timeout has elapsed, this method will return.
        """

    @abc.abstractmethod
    def result(
        self,
        timeout: Optional[float] = None,
        raise_on_failure: bool = True,
    ) -> Any:
        ...
        """
        Get the result of the task run associated with this future.

        If the task run has not completed, this method will wait for the task run to complete.

        Args:
            - timeout: The maximum number of seconds to wait for the task run to complete.
            If the task run has not completed after the timeout has elapsed, this method will return.
            - raise_on_failure: If `True`, an exception will be raised if the task run fails.

        Returns:
            The result of the task run.
        """


class PrefectConcurrentFuture(PrefectFuture[concurrent.futures.Future]):
    """
    A Prefect future that wraps a concurrent.futures.Future. This future is used
    when the task run is submitted to a ThreadPoolExecutor.
    """

    def wait(self, timeout: Optional[float] = None) -> None:
        try:
            result = self._wrapped_future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            return
        if isinstance(result, State):
            self._final_state = result

    def result(
        self,
        timeout: Optional[float] = None,
        raise_on_failure: bool = True,
    ) -> Any:
        if not self._final_state:
            try:
                future_result = self._wrapped_future.result(timeout=timeout)
            except concurrent.futures.TimeoutError as exc:
                raise TimeoutError(
                    f"Task run {self.task_run_id} did not complete within {timeout} seconds"
                ) from exc

            if isinstance(future_result, State):
                self._final_state = future_result
            else:
                return future_result

        _result = self._final_state.result(
            raise_on_failure=raise_on_failure, fetch=True
        )
        # state.result is a `sync_compatible` function that may or may not return an awaitable
        # depending on whether the parent frame is sync or not
        if inspect.isawaitable(_result):
            _result = run_coro_as_sync(_result)
        return _result


def resolve_futures_to_states(
    expr: Union[PrefectFuture, Any],
) -> Union[State, Any]:
    """
    Given a Python built-in collection, recursively find `PrefectFutures` and build a
    new collection with the same structure with futures resolved to their final states.
    Resolving futures to their final states may wait for execution to complete.

    Unsupported object types will be returned without modification.
    """
    futures: Set[PrefectFuture] = set()

    def _collect_futures(futures, expr, context):
        # Expressions inside quotes should not be traversed
        if isinstance(context.get("annotation"), quote):
            raise StopVisiting()

        if isinstance(expr, PrefectFuture):
            futures.add(expr)

        return expr

    visit_collection(
        expr,
        visit_fn=partial(_collect_futures, futures),
        return_data=False,
        context={},
    )

    # Get final states for each future
    states = []
    for future in futures:
        future.wait()
        states.append(future.state)

    states_by_future = dict(zip(futures, states))

    def replace_futures_with_states(expr, context):
        # Expressions inside quotes should not be modified
        if isinstance(context.get("annotation"), quote):
            raise StopVisiting()

        if isinstance(expr, PrefectFuture):
            return states_by_future[expr]
        else:
            return expr

    return visit_collection(
        expr,
        visit_fn=replace_futures_with_states,
        return_data=True,
        context={},
    )
