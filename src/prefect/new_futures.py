import abc
import inspect
import uuid
from concurrent.futures import Future
from functools import partial
from typing import Any, Generic, Optional, Set, Union, cast

from typing_extensions import TypeVar

from prefect.client.orchestration import get_client
from prefect.client.schemas.objects import TaskRun
from prefect.exceptions import ObjectNotFound
from prefect.states import Pending, State
from prefect.utilities.annotations import quote
from prefect.utilities.asyncutils import run_sync
from prefect.utilities.collections import StopVisiting, visit_collection

R = TypeVar("R")


class PrefectFuture(abc.ABC, Generic[R]):
    def __init__(self, task_run_id: uuid.UUID, wrapped_future: Future):
        self._task_run_id = task_run_id
        self._wrapped_future = wrapped_future
        self._final_state = None

    @property
    def task_run_id(self) -> uuid.UUID:
        return self._task_run_id

    @property
    def wrapped_future(self) -> Future:
        return self._wrapped_future

    @property
    def state(self) -> State[R]:
        if self._final_state:
            return self._final_state
        client = get_client(sync_client=True)
        try:
            task_run = cast(TaskRun, client.read_task_run(task_run_id=self.task_run_id))
        except ObjectNotFound:
            # We'll be optimistic and assume this task will eventually start
            # TODO: Consider using task run events to wait for the task to start
            return Pending()
        return cast(State[R], task_run.state or Pending())

    @abc.abstractmethod
    def wait(self, timeout: Optional[float] = None) -> None:
        ...

    @abc.abstractmethod
    def result(
        self, raise_on_failure: bool = True, timeout: Optional[float] = None
    ) -> Any:
        ...


class PrefectConcurrentFuture(PrefectFuture):
    def wait(self, timeout: Optional[float] = None) -> None:
        result = self._wrapped_future.result(timeout=timeout)
        if isinstance(result, State):
            self._final_state = result

    def result(
        self, raise_on_failure: bool = True, timeout: Optional[float] = None
    ) -> Any:
        if not self._final_state:
            future_result = self._wrapped_future.result(timeout=timeout)
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
            _result = run_sync(_result)
        return _result


def _collect_futures(futures, expr, context):
    # Expressions inside quotes should not be traversed
    if isinstance(context.get("annotation"), quote):
        raise StopVisiting()

    if isinstance(expr, PrefectFuture):
        futures.add(expr)

    return expr


def resolve_futures_to_states(
    expr: Union[PrefectFuture[R], Any],
) -> Union[State[R], Any]:
    """
    Given a Python built-in collection, recursively find `PrefectFutures` and build a
    new collection with the same structure with futures resolved to their final states.
    Resolving futures to their final states may wait for execution to complete.

    Unsupported object types will be returned without modification.
    """
    futures: Set[PrefectFuture] = set()

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
