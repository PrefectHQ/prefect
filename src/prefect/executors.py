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
import abc
from contextlib import asynccontextmanager
from typing import (
    Any,
    Callable,
    Dict,
    Optional,
    TypeVar,
    Awaitable,
    AsyncIterator,
    Union,
)
from uuid import UUID

# TODO: Once executors are split into separate files this should become an optional dependency
import distributed

from prefect.futures import PrefectFuture
from prefect.orion.schemas.states import State
from prefect.orion.schemas.core import TaskRun
from prefect.utilities.logging import get_logger
from prefect.utilities.asyncio import A
from prefect.utilities.importtools import import_object
from prefect.utilities.hashing import to_qualified_name

T = TypeVar("T", bound="BaseExecutor")
R = TypeVar("R")


class BaseExecutor(metaclass=abc.ABCMeta):
    def __init__(self) -> None:
        self.logger = get_logger("executor")
        self._started: bool = False

    @abc.abstractmethod
    async def submit(
        self,
        task_run: TaskRun,
        run_fn: Callable[..., Awaitable[State[R]]],
        run_kwargs: Dict[str, Any],
        asynchronous: A = True,
    ) -> PrefectFuture[R, A]:
        """
        Submit a call for execution and return a `PrefectFuture` that can be used to
        get the call result.

        Args:
            run_id: A unique id identifying the run being submitted
            run_fn: The function to be executed
            run_kwargs: A dict of keyword arguments to pass to `run_fn`

        Returns:
            A future representing the result of `run_fn` execution
        """
        raise NotImplementedError()

    @abc.abstractmethod
    async def wait(
        self, prefect_future: PrefectFuture, timeout: float = None
    ) -> Optional[State]:
        """
        Given a `PrefectFuture`, wait for its return state up to `timeout` seconds.
        If it is not finished after the timeout expires, `None` should be returned.
        """
        raise NotImplementedError()

    @asynccontextmanager
    async def start(
        self: T,
    ) -> AsyncIterator[T]:
        """Start the executor, preparing any resources necessary for task submission"""
        try:
            self.logger.info(f"Starting executor {self}...")
            await self.on_startup()
            self._started = True
            yield self
        finally:
            self.logger.info(f"Shutting down executor {self}...")
            await self.on_shutdown()
            self._started = False

    async def on_startup(self) -> None:
        """
        Create any resources required for this executor to submit work.
        """
        pass

    async def on_shutdown(self) -> None:
        """
        Clean up resources associated with the executor.

        Should block until submitted calls are completed.
        """
        # TODO: Consider adding a `wait` bool here for fast shutdown
        pass

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
        run_fn: Callable[..., Awaitable[State[R]]],
        run_kwargs: Dict[str, Any],
        asynchronous: A = True,
    ) -> PrefectFuture[R, A]:
        if not self._started:
            raise RuntimeError("The executor must be started before submitting work.")

        # Run the function immediately and store the result in memory
        self._results[task_run.id] = await run_fn(**run_kwargs)

        return PrefectFuture(
            task_run=task_run, executor=self, asynchronous=asynchronous
        )

    async def wait(
        self, prefect_future: PrefectFuture, timeout: float = None
    ) -> Optional[State]:
        return self._results[prefect_future.run_id]


class DaskExecutor(BaseExecutor):
    """
    A parallel executor that submits tasks to the `dask.distributed` scheduler.

    By default a temporary `distributed.LocalCluster` is created (and
    subsequently torn down) within the `start()` contextmanager. To use a
    different cluster class (e.g.
    [`dask_kubernetes.KubeCluster`](https://kubernetes.dask.org/)), you can
    specify `cluster_class`/`cluster_kwargs`.

    Alternatively, if you already have a dask cluster running, you can provide
    the address of the scheduler via the `address` kwarg.

    !!! warning "Multiprocessing safety"
        Please note that because the `DaskExecutor` uses multiprocessing, calls to flows
        in scripts must be guarded with `if __name__ == "__main__":` or warnings will
        be displayed.

    Args:
        - address (string, optional): address of a currently running dask
            scheduler; if one is not provided, a temporary cluster will be
            created in `executor.start()`.  Defaults to `None`.
        - cluster_class (string or callable, optional): the cluster class to use
            when creating a temporary dask cluster. Can be either the full
            class name (e.g. `"distributed.LocalCluster"`), or the class itself.
        - cluster_kwargs (dict, optional): addtional kwargs to pass to the
           `cluster_class` when creating a temporary dask cluster.
        - adapt_kwargs (dict, optional): additional kwargs to pass to `cluster.adapt`
            when creating a temporary dask cluster. Note that adaptive scaling
            is only enabled if `adapt_kwargs` are provided.
        - client_kwargs (dict, optional): additional kwargs to use when creating a
            [`dask.distributed.Client`](https://distributed.dask.org/en/latest/api.html#client).

    Examples:

        Using a temporary local dask cluster
        >>> from prefect import flow
        >>> from prefect.executors import DaskExecutor
        >>> @flow(executor=DaskExecutor)

        Using a temporary cluster running elsewhere. Any Dask cluster class should
        work, here we use [dask-cloudprovider](https://cloudprovider.dask.org)
        >>> DaskExecutor(
        >>>     cluster_class="dask_cloudprovider.FargateCluster",
        >>>     cluster_kwargs={
        >>>          "image": "prefecthq/prefect:latest",
        >>>          "n_workers": 5,
        >>>     },
        >>> )


        Connecting to an existing dask cluster
        >>> DaskExecutor(address="192.0.2.255:8786")
    """

    def __init__(
        self,
        address: str = None,
        cluster_class: Union[str, Callable] = None,
        cluster_kwargs: dict = None,
        adapt_kwargs: dict = None,
        client_kwargs: dict = None,
    ):

        # Validate settings and infer defaults
        if address:
            if cluster_class or cluster_kwargs or adapt_kwargs:
                raise ValueError(
                    "Cannot specify `address` and `cluster_class`/`cluster_kwargs`/`adapt_kwargs`"
                )
        else:
            if isinstance(cluster_class, str):
                cluster_class = import_object(cluster_class)
            else:
                cluster_class = cluster_class or distributed.LocalCluster

        # Create a copies of incoming kwargs since we may mutate them
        cluster_kwargs = cluster_kwargs.copy() if cluster_kwargs else {}
        adapt_kwargs = adapt_kwargs.copy() if adapt_kwargs else {}
        client_kwargs = client_kwargs.copy() if client_kwargs else {}

        # Update kwargs defaults
        client_kwargs.setdefault("set_as_default", False)

        # Ensure we're working with async client/cluster objects
        client_kwargs["asynchronous"] = True
        cluster_kwargs["asynchronous"] = True

        # Store settings
        self.address = address
        self.cluster_class = cluster_class
        self.cluster_kwargs = cluster_kwargs
        self.adapt_kwargs = adapt_kwargs
        self.client_kwargs = client_kwargs

        # Runtime attributes
        self._client: "distributed.Client" = None
        self._cluster: "distributed.deploy.Cluster" = None
        self._dask_futures: Dict[UUID, "distributed.Future"] = {}

        super().__init__()

    async def submit(
        self,
        task_run: TaskRun,
        run_fn: Callable[..., Awaitable[State[R]]],
        run_kwargs: Dict[str, Any],
        asynchronous: A = True,
    ) -> PrefectFuture[R, A]:
        if not self._started:
            raise RuntimeError("The executor must be started before submitting work.")

        self._dask_futures[task_run.id] = self._client.submit(run_fn, **run_kwargs)

        return PrefectFuture(
            task_run=task_run, executor=self, asynchronous=asynchronous
        )

    def _get_dask_future(self, prefect_future: PrefectFuture) -> "distributed.Future":
        """
        Retrieve the dask future corresponding to a prefect future

        The dask future is for the `run_fn` which should return a `State`
        """
        return self._dask_futures[prefect_future.run_id]

    async def wait(
        self,
        prefect_future: PrefectFuture,
        timeout: float = None,
    ) -> Optional[State]:
        future = self._get_dask_future(prefect_future)
        try:
            return await future.result(timeout=timeout)
        except distributed.TimeoutError:
            return None

    async def on_startup(self):
        if self.address:
            self.logger.info(
                f"Connecting to an existing Dask cluster at {self.address}"
            )
            connect_to = self.address
        else:
            self.logger.info(
                f"Creating a new Dask cluster with `{to_qualified_name(self.cluster_class)}`"
            )
            self._cluster = await self._create_cluster()
            connect_to = self._cluster

        self._client = await distributed.Client(connect_to, **self.client_kwargs)

        if self._client.dashboard_link:
            self.logger.info(
                f"The Dask dashboard is available at {self._client.dashboard_link}",
            )

    async def _create_cluster(self) -> "distributed.deploy.Cluster":
        """
        Create a new Dask cluster as specified by `cluster_class`, `cluster_kwargs`, and
        `adapt_kwargs`
        """
        cluster = self.cluster_class(**self.cluster_kwargs)
        await cluster._start()

        if self.adapt_kwargs:
            cluster.adapt(**self.adapt_kwargs)

        return cluster

    async def on_shutdown(self) -> None:
        # Attempt to wait for all futures to complete
        for future in self._dask_futures.values():
            try:
                await future.result()
            except Exception:
                pass
        # Close down the client and cluster
        if self._client:
            await self._client.close()
        if self._cluster:
            await self._cluster.close()

    def __getstate__(self):
        """
        Allow the `DaskExecutor` to be serialized by dropping the `distributed.Client`
        which contains locks. Must be deserialized on a dask worker.
        """
        data = self.__dict__.copy()
        data.update({k: None for k in {"_client", "_cluster"}})
        return data

    def __setstate__(self, data: dict):
        """
        Restore the `distributed.Client` by loading the client on a dask worker.
        """
        self.__dict__.update(data)
        self._client = distributed.get_client()
