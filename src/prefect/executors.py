"""
Interface and implementations of various task run executors.

**Executors** in Prefect are responsible for managing the execution of Prefect task runs. Generally speaking, users are not expected to interact with executors outside of configuring and initializing them for a flow.

Example:

    >>> from prefect import flow, task, executors
    >>> from typing import List
    >>>
    >>> @task
    >>> def say_hello(name):
    ...     print(f"hello {name}")
    >>>
    >>> @task
    >>> def say_goodbye(name):
    ...     print(f"goodbye {name}")
    >>>
    >>> @flow(executor=executors.SequentialExecutor())
    >>> def greetings(names: List[str]):
    ...     for name in names:
    ...         say_hello(name)
    ...         say_goodbye(name)
    >>>
    >>> greetings(["arthur", "trillian", "ford", "marvin"])
    hello arthur
    goodbye arthur
    hello trillian
    goodbye trillian
    hello ford
    goodbye ford
    hello marvin
    goodbye marvin

    Switching to a `DaskExecutor`:
    >>> flow.executor = executors.DaskExecutor()
    >>> greetings(["arthur", "trillian", "ford", "marvin"])
    hello arthur
    goodbye arthur
    hello trillian
    hello ford
    goodbye marvin
    hello marvin
    goodbye ford
    goodbye trillian

The following executors are currently supported:

- `SequentialExecutor`: the simplest executor and the default; submits each task run sequentially as they are called and blocks until completion
- `DaskExecutor`: creates a `LocalCluster` that task runs are submitted to; allows for parallelism with a flow run

"""
from contextlib import contextmanager
from typing import Any, Callable, Dict, Optional, TypeVar
from uuid import UUID

# TODO: Once executors are split into separate files this should become an optional dependency
import distributed

from prefect.futures import PrefectFuture, resolve_futures_to_data
from prefect.orion.schemas.states import State
from prefect.orion.schemas.core import TaskRun
from prefect.utilities.logging import get_logger

T = TypeVar("T", bound="BaseExecutor")


class BaseExecutor:
    def __init__(self) -> None:
        self.logger = get_logger("executor")
        self._started: bool = False

    async def submit(
        self,
        task_run: TaskRun,
        run_fn: Callable[..., State],
        run_kwargs: Dict[str, Any],
    ) -> PrefectFuture:
        """
        Submit a call for execution and return a `PrefectFuture` that can be used to
        get the call result. This method is responsible for resolving `PrefectFutures`
        in args and kwargs into a type supported by the underlying execution method.

        Args:
            run_id: A unique id identifying the run being submitted
            run_fn: The function to be executed
            *args: Arguments to pass to `run_fn`
            **kwargs: Keyword arguments to pass to `run_fn`

        Returns:
            A future representing the result of `run_fn` execution
        """
        raise NotImplementedError()

    @contextmanager
    def start(
        self: T,
    ) -> T:
        """Start the executor, preparing any resources necessary for task submission"""
        try:
            self._started = True
            yield self
        finally:
            self.logger.info("Shutting down executor...")
            self.shutdown()
            self._started = False

    def shutdown(self) -> None:
        """
        Clean up resources associated with the executor.

        Should block until submitted calls are completed.
        """
        # TODO: Consider adding a `wait` bool here for fast shutdown
        pass

    async def wait(
        self, prefect_future: PrefectFuture, timeout: float = None
    ) -> Optional[State]:
        """
        Given a `PrefectFuture`, wait for its return state up to `timeout` seconds.
        If it is not finished after the timeout expires, `None` should be returned.
        """
        raise NotImplementedError()

    def __str__(self) -> str:
        return type(self).__name__


class SequentialExecutor(BaseExecutor):
    """
    A simple executor that executes calls as they are submitted.

    If writing synchronous tasks, this executor will always run tasks sequentially.
    If writing async tasks, this executor will run tasks sequentially unless grouped
    using `anyio.create_task_group` or `asyncio.gather`.
    """

    def __init__(self) -> None:
        super().__init__()
        self._results: Dict[UUID, State] = {}

    async def submit(
        self,
        task_run: TaskRun,
        run_fn: Callable[..., State],
        run_kwargs: Dict[str, Any],
    ) -> PrefectFuture:
        if not self._started:
            raise RuntimeError("The executor must be started before submitting work.")

        # Run the function immediately and store the result in memory
        self._results[task_run.id] = await run_fn(**run_kwargs)

        return PrefectFuture(
            task_run=task_run,
            executor=self,
        )

    async def wait(
        self, prefect_future: PrefectFuture, timeout: float = None
    ) -> Optional[State]:
        return self._results[prefect_future.run_id]


class DaskExecutor(BaseExecutor):
    """
    A parallel executor that submits calls to a dask cluster.

    A local dask distributed cluster is created on use.
    """

    # TODO: __init__ should support cluster setup kwargs as well as existing cluster
    #      connection args

    def __init__(self) -> None:
        super().__init__()
        self._client: "distributed.Client" = None
        self._futures: Dict[UUID, "distributed.Future"] = {}

    async def submit(
        self,
        task_run: TaskRun,
        run_fn: Callable[..., State],
        run_kwargs: Dict[str, Any],
    ) -> PrefectFuture:
        if not self._started:
            raise RuntimeError("The executor must be started before submitting work.")

        self._futures[task_run.id] = self._client.submit(run_fn, **run_kwargs)

        return PrefectFuture(
            task_run=task_run,
            executor=self,
        )

    def _get_dask_future(self, prefect_future: PrefectFuture) -> "distributed.Future":
        """
        Retrieve the dask future corresponding to a prefect future

        The dask future is for the `run_fn` which should return a `State`
        """
        return self._futures[prefect_future.run_id]

    async def wait(
        self,
        prefect_future: PrefectFuture,
        timeout: float = None,
    ) -> Optional[State]:
        future = self._get_dask_future(prefect_future)
        try:
            result = future.result(timeout=timeout)
            # The client may be async on a dask worker
            # TODO: Set `Client(asynchronous=True)` on startup and just always use the
            #       async client
            if self._client.asynchronous:
                return await result
            else:
                return result
        except distributed.TimeoutError:
            return None

    @contextmanager
    def start(self: T) -> T:
        with super().start():
            self._client = distributed.Client()
            self.logger.info(
                f"Dask dashboard available at {self._client.dashboard_link}"
            )
            yield self

    def shutdown(self) -> None:
        # Attempt to wait for all futures to complete
        for future in self._futures.values():
            try:
                future.result()
            except Exception:
                pass
        self._client.close()

    def __getstate__(self):
        """
        Allow the `DaskExecutor` to be serialized by dropping the `distributed.Client`
        which contains locks.

        Must be deserialized on a dask worker.
        """
        data = self.__dict__.copy()
        data["_client"] = None
        return data

    def __setstate__(self, data):
        """
        Restore the `distributed.Client` by loading the client on a dask worker.
        """
        self.__dict__ = data
        self._client = distributed.get_client()
