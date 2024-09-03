import abc
import collections
import concurrent.futures
import inspect
import threading
import uuid
from collections.abc import Generator, Iterator
from functools import partial
from typing import Any, Callable, Generic, List, Optional, Set, Union, cast

from typing_extensions import TypeVar

from prefect.client.orchestration import get_client
from prefect.client.schemas.objects import TaskRun
from prefect.exceptions import ObjectNotFound
from prefect.logging.loggers import get_logger, get_run_logger
from prefect.states import Pending, State
from prefect.task_runs import TaskRunWaiter
from prefect.utilities.annotations import quote
from prefect.utilities.asyncutils import run_coro_as_sync
from prefect.utilities.collections import StopVisiting, visit_collection
from prefect.utilities.timeout import timeout as timeout_context

F = TypeVar("F")
R = TypeVar("R")

logger = get_logger(__name__)


class PrefectFuture(abc.ABC, Generic[R]):
    """
    Abstract base class for Prefect futures. A Prefect future is a handle to the
    asynchronous execution of a task run. It provides methods to wait for the task
    to complete and to retrieve the result of the task run.
    """

    def __init__(self, task_run_id: uuid.UUID):
        self._task_run_id = task_run_id
        self._final_state: Optional[State[R]] = None

    @property
    def task_run_id(self) -> uuid.UUID:
        """The ID of the task run associated with this future"""
        return self._task_run_id

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
            timeout: The maximum number of seconds to wait for the task run to complete.
              If the task run has not completed after the timeout has elapsed, this method will return.
        """

    @abc.abstractmethod
    def result(
        self,
        timeout: Optional[float] = None,
        raise_on_failure: bool = True,
    ) -> R:
        ...
        """
        Get the result of the task run associated with this future.

        If the task run has not completed, this method will wait for the task run to complete.

        Args:
            timeout: The maximum number of seconds to wait for the task run to complete.
            If the task run has not completed after the timeout has elapsed, this method will return.
            raise_on_failure: If `True`, an exception will be raised if the task run fails.

        Returns:
            The result of the task run.
        """

    @abc.abstractmethod
    def add_done_callback(self, fn):
        """
        Add a callback to be run when the future completes or is cancelled.

        Args:
            fn: A callable that will be called with this future as its only argument when the future completes or is cancelled.
        """
        ...


class PrefectWrappedFuture(PrefectFuture, abc.ABC, Generic[R, F]):
    """
    A Prefect future that wraps another future object.
    """

    def __init__(self, task_run_id: uuid.UUID, wrapped_future: F):
        self._wrapped_future = wrapped_future
        super().__init__(task_run_id)

    @property
    def wrapped_future(self) -> F:
        """The underlying future object wrapped by this Prefect future"""
        return self._wrapped_future

    def add_done_callback(self, fn: Callable[[PrefectFuture], None]):
        if not self._final_state:

            def call_with_self(future):
                """Call the callback with self as the argument, this is necessary to ensure we remove the future from the pending set"""
                fn(self)

            self._wrapped_future.add_done_callback(call_with_self)
            return
        fn(self)


class PrefectConcurrentFuture(PrefectWrappedFuture[R, concurrent.futures.Future]):
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
    ) -> R:
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

    def __del__(self):
        if self._final_state or self._wrapped_future.done():
            return
        try:
            local_logger = get_run_logger()
        except Exception:
            local_logger = logger
        local_logger.warning(
            "A future was garbage collected before it resolved."
            " Please call `.wait()` or `.result()` on futures to ensure they resolve."
            "\nSee https://docs.prefect.io/latest/develop/task-runners for more details.",
        )


class PrefectDistributedFuture(PrefectFuture[R]):
    """
    Represents the result of a computation happening anywhere.

    This class is typically used to interact with the result of a task run
    scheduled to run in a Prefect task worker but can be used to interact with
    any task run scheduled in Prefect's API.
    """

    done_callbacks: List[Callable[[PrefectFuture], None]] = []
    waiter = None

    def wait(self, timeout: Optional[float] = None) -> None:
        return run_coro_as_sync(self.wait_async(timeout=timeout))

    async def wait_async(self, timeout: Optional[float] = None):
        if self._final_state:
            logger.debug(
                "Final state already set for %s. Returning...", self.task_run_id
            )
            return

        # Ask for the instance of TaskRunWaiter _now_ so that it's already running and
        # can catch the completion event if it happens before we start listening for it.
        TaskRunWaiter.instance()

        # Read task run to see if it is still running
        async with get_client() as client:
            task_run = await client.read_task_run(task_run_id=self._task_run_id)
            if task_run.state.is_final():
                logger.debug(
                    "Task run %s already finished. Returning...",
                    self.task_run_id,
                )
                self._final_state = task_run.state
                return

            # If still running, wait for a completed event from the server
            logger.debug(
                "Waiting for completed event for task run %s...",
                self.task_run_id,
            )
            await TaskRunWaiter.wait_for_task_run(self._task_run_id, timeout=timeout)
            task_run = await client.read_task_run(task_run_id=self._task_run_id)
            if task_run.state.is_final():
                self._final_state = task_run.state
            return

    def result(
        self,
        timeout: Optional[float] = None,
        raise_on_failure: bool = True,
    ) -> R:
        return run_coro_as_sync(
            self.result_async(timeout=timeout, raise_on_failure=raise_on_failure)
        )

    async def result_async(
        self,
        timeout: Optional[float] = None,
        raise_on_failure: bool = True,
    ) -> R:
        if not self._final_state:
            await self.wait_async(timeout=timeout)
            if not self._final_state:
                raise TimeoutError(
                    f"Task run {self.task_run_id} did not complete within {timeout} seconds"
                )

        return await self._final_state.result(
            raise_on_failure=raise_on_failure, fetch=True
        )

    def add_done_callback(self, fn: Callable[[PrefectFuture], None]):
        if self._final_state:
            fn(self)
            return
        TaskRunWaiter.instance()
        with get_client(sync_client=True) as client:
            task_run = client.read_task_run(task_run_id=self._task_run_id)
            if task_run.state.is_final():
                self._final_state = task_run.state
                fn(self)
                return
            TaskRunWaiter.add_done_callback(self._task_run_id, partial(fn, self))

    def __eq__(self, other):
        if not isinstance(other, PrefectDistributedFuture):
            return False
        return self.task_run_id == other.task_run_id

    def __hash__(self):
        return hash(self.task_run_id)


class PrefectFutureList(list, Iterator, Generic[F]):
    """
    A list of Prefect futures.

    This class provides methods to wait for all futures
    in the list to complete and to retrieve the results of all task runs.
    """

    def wait(self, timeout: Optional[float] = None) -> None:
        """
        Wait for all futures in the list to complete.

        Args:
            timeout: The maximum number of seconds to wait for all futures to
                complete. This method will not raise if the timeout is reached.
        """
        wait(self, timeout=timeout)

    def result(
        self,
        timeout: Optional[float] = None,
        raise_on_failure: bool = True,
    ) -> List:
        """
        Get the results of all task runs associated with the futures in the list.

        Args:
            timeout: The maximum number of seconds to wait for all futures to
                complete.
            raise_on_failure: If `True`, an exception will be raised if any task run fails.

        Returns:
            A list of results of the task runs.

        Raises:
            TimeoutError: If the timeout is reached before all futures complete.
        """
        try:
            with timeout_context(timeout):
                return [
                    future.result(raise_on_failure=raise_on_failure) for future in self
                ]
        except TimeoutError as exc:
            # timeout came from inside the task
            if "Scope timed out after {timeout} second(s)." not in str(exc):
                raise
            raise TimeoutError(
                f"Timed out waiting for all futures to complete within {timeout} seconds"
            ) from exc


def as_completed(
    futures: List[PrefectFuture], timeout: Optional[float] = None
) -> Generator[PrefectFuture, None]:
    unique_futures: Set[PrefectFuture] = set(futures)
    total_futures = len(unique_futures)
    try:
        with timeout_context(timeout):
            done = {f for f in unique_futures if f._final_state}
            pending = unique_futures - done
            yield from done

            finished_event = threading.Event()
            finished_lock = threading.Lock()
            finished_futures = []

            def add_to_done(future):
                with finished_lock:
                    finished_futures.append(future)
                    finished_event.set()

            for future in pending:
                future.add_done_callback(add_to_done)

            while pending:
                finished_event.wait()
                with finished_lock:
                    done = finished_futures
                    finished_futures = []
                    finished_event.clear()

                for future in done:
                    pending.remove(future)
                    yield future

    except TimeoutError:
        raise TimeoutError(
            "%d (of %d) futures unfinished" % (len(pending), total_futures)
        )


DoneAndNotDoneFutures = collections.namedtuple("DoneAndNotDoneFutures", "done not_done")


def wait(futures: List[PrefectFuture], timeout=None) -> DoneAndNotDoneFutures:
    """
    Wait for the futures in the given sequence to complete.

    Args:
        futures: The sequence of Futures to wait upon.
        timeout: The maximum number of seconds to wait. If None, then there
            is no limit on the wait time.

    Returns:
        A named 2-tuple of sets. The first set, named 'done', contains the
        futures that completed (is finished or cancelled) before the wait
        completed. The second set, named 'not_done', contains uncompleted
        futures. Duplicate futures given to *futures* are removed and will be
        returned only once.

    Examples:
        ```python
        @task
        def sleep_task(seconds):
            sleep(seconds)
            return 42

        @flow
        def flow():
            futures = random_task.map(range(10))
            done, not_done = wait(futures, timeout=5)
            print(f"Done: {len(done)}")
            print(f"Not Done: {len(not_done)}")
        ```
    """
    futures = set(futures)
    done = {f for f in futures if f._final_state}
    not_done = futures - done
    if len(done) == len(futures):
        return DoneAndNotDoneFutures(done, not_done)
    try:
        with timeout_context(timeout):
            for future in not_done.copy():
                future.wait()
                done.add(future)
                not_done.remove(future)
            return DoneAndNotDoneFutures(done, not_done)
    except TimeoutError:
        logger.debug("Timed out waiting for all futures to complete.")
        return DoneAndNotDoneFutures(done, not_done)


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

    # if no futures were found, return the original expression
    if not futures:
        return expr

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
