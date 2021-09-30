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

from prefect.client import OrionClient
from prefect.futures import PrefectFuture, resolve_futures_to_data
from prefect.orion.schemas.states import State

T = TypeVar("T", bound="BaseExecutor")


class BaseExecutor:
    def __init__(self) -> None:
        # Set on `start`
        self.flow_run_id: UUID = None
        self.orion_client: OrionClient = None

    async def submit(
        self,
        run_id: UUID,
        run_fn: Callable[..., State],
        *args: Any,
        **kwargs: Dict[str, Any],
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
        flow_run_id: UUID,
    ) -> T:
        """Start the executor, preparing any resources necessary for task submission"""
        self.flow_run_id = flow_run_id
        try:
            yield self
        finally:
            self.shutdown()
            self.flow_run_id = None

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
        run_id: UUID,
        run_fn: Callable[..., State],
        *args: Any,
        **kwargs: Dict[str, Any],
    ) -> PrefectFuture:
        if not self.flow_run_id:
            raise RuntimeError("The executor must be started before submitting work.")

        # Run the function immediately and store the result in memory
        self._results[run_id] = await run_fn(*args, **kwargs)

        return PrefectFuture(
            run_id=run_id,
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
        run_id: UUID,
        run_fn: Callable[..., State],
        *args: Any,
        **kwargs: Dict[str, Any],
    ) -> PrefectFuture:
        if not self._client:
            raise RuntimeError("The executor must be started before submitting work.")

        self._futures[run_id] = self._client.submit(run_fn, *args, **kwargs)

        return PrefectFuture(
            run_id=run_id,
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
    def start(self: T, flow_run_id: UUID) -> T:
        with super().start(flow_run_id=flow_run_id):
            self._client = distributed.Client()
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
