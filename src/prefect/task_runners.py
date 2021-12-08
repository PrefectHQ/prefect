"""
Interface and implementations of various task runners.

**TaskRunners** in Prefect are responsible for managing the execution of Prefect task runs. Generally speaking, users are not expected to interact with task runners outside of configuring and initializing them for a flow.

Example:

    >>> from prefect import flow, task, task_runners
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
    >>> @flow(task_runner=task_runners.SequentialTaskRunner())
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

    Switching to a `DaskTaskRunner`:
    >>> flow.task_runner = task_runners.DaskTaskRunner()
    >>> greetings(["arthur", "trillian", "ford", "marvin"])
    hello arthur
    goodbye arthur
    hello trillian
    hello ford
    goodbye marvin
    hello marvin
    goodbye ford
    goodbye trillian

The following task runners are currently supported:

- `SequentialTaskRunner`: the simplest runner and the default; submits each task run sequentially as they are called and blocks until completion
- `DaskTaskRunner`: creates a `LocalCluster` that task runs are submitted to; allows for parallelism with a flow run
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
from contextlib import AsyncExitStack

# TODO: Once task runners are split into separate files this should become an optional dependency
import distributed

from prefect.futures import PrefectFuture
from prefect.orion.schemas.states import State
from prefect.orion.schemas.core import TaskRun
from prefect.utilities.logging import get_logger
from prefect.utilities.asyncio import A
from prefect.utilities.importtools import import_object
from prefect.utilities.hashing import to_qualified_name

T = TypeVar("T", bound="BaseTaskRunner")
R = TypeVar("R")


class BaseTaskRunner(metaclass=abc.ABCMeta):
    def __init__(self) -> None:
        self.logger = get_logger("task_runner")
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
        """
        Start the task runner, preparing any resources necessary for task submission.

        Children should implement `_start` to prepare and clean up resources.

        Yields:
            The prepared task runner
        """
        if self._started:
            raise RuntimeError("The task runner is already started!")

        async with AsyncExitStack() as exit_stack:
            self.logger.info(f"Starting task runner `{self}`...")
            try:
                await self._start(exit_stack)
                self._started = True
                yield self
            finally:
                self.logger.info(f"Shutting down task runner `{self}`...")
                self._started = False

    async def _start(self, exit_stack: AsyncExitStack) -> None:
        """
        Create any resources required for this task runner to submit work.

        Cleanup of resources should be submitted to the `exit_stack`.
        """
        pass

    def __str__(self) -> str:
        return type(self).__name__


class SequentialTaskRunner(BaseTaskRunner):
    """
    A simple task runner that executes calls as they are submitted.

    If writing synchronous tasks, this runner will always execute tasks sequentially.
    If writing async tasks, this runner will execute tasks sequentially unless grouped
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
            raise RuntimeError(
                "The task runner must be started before submitting work."
            )

        # Run the function immediately and store the result in memory
        self._results[task_run.id] = await run_fn(**run_kwargs)

        return PrefectFuture(
            task_run=task_run, task_runner=self, asynchronous=asynchronous
        )

    async def wait(
        self, prefect_future: PrefectFuture, timeout: float = None
    ) -> Optional[State]:
        return self._results[prefect_future.run_id]


class DaskTaskRunner(BaseTaskRunner):
    """
    A parallel task_runner that submits tasks to the `dask.distributed` scheduler.

    By default a temporary `distributed.LocalCluster` is created (and
    subsequently torn down) within the `start()` contextmanager. To use a
    different cluster class (e.g.
    [`dask_kubernetes.KubeCluster`](https://kubernetes.dask.org/)), you can
    specify `cluster_class`/`cluster_kwargs`.

    Alternatively, if you already have a dask cluster running, you can provide
    the address of the scheduler via the `address` kwarg.

    !!! warning "Multiprocessing safety"
        Please note that because the `DaskTaskRunner` uses multiprocessing, calls to flows
        in scripts must be guarded with `if __name__ == "__main__":` or warnings will
        be displayed.

    Args:
        address (string, optional): address of a currently running dask
            scheduler; if one is not provided, a temporary cluster will be
            created in `DaskTaskRunner.start()`.  Defaults to `None`.
        cluster_class (string or callable, optional): the cluster class to use
            when creating a temporary dask cluster. Can be either the full
            class name (e.g. `"distributed.LocalCluster"`), or the class itself.
        cluster_kwargs (dict, optional): addtional kwargs to pass to the
            `cluster_class` when creating a temporary dask cluster.
        adapt_kwargs (dict, optional): additional kwargs to pass to `cluster.adapt`
            when creating a temporary dask cluster. Note that adaptive scaling
            is only enabled if `adapt_kwargs` are provided.
        client_kwargs (dict, optional): additional kwargs to use when creating a
            [`dask.distributed.Client`](https://distributed.dask.org/en/latest/api.html#client).

    Examples:

        Using a temporary local dask cluster
        >>> from prefect import flow
        >>> from prefect.task_runners import DaskTaskRunner
        >>> @flow(task_runner=DaskTaskRunner)

        Using a temporary cluster running elsewhere. Any Dask cluster class should
        work, here we use [dask-cloudprovider](https://cloudprovider.dask.org)
        >>> DaskTaskRunner(
        >>>     cluster_class="dask_cloudprovider.FargateCluster",
        >>>     cluster_kwargs={
        >>>          "image": "prefecthq/prefect:latest",
        >>>          "n_workers": 5,
        >>>     },
        >>> )


        Connecting to an existing dask cluster
        >>> DaskTaskRunner(address="192.0.2.255:8786")
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

        # The user cannot specify async/sync themselves
        if "asynchronous" in client_kwargs:
            raise ValueError(
                "`client_kwargs` cannot set `asynchronous`. "
                "This option is managed by Prefect."
            )
        if "asynchronous" in cluster_kwargs:
            raise ValueError(
                "`cluster_kwargs` cannot set `asynchronous`. "
                "This option is managed by Prefect."
            )

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
            raise RuntimeError(
                "The task runner must be started before submitting work."
            )

        self._dask_futures[task_run.id] = self._client.submit(run_fn, **run_kwargs)

        return PrefectFuture(
            task_run=task_run, task_runner=self, asynchronous=asynchronous
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

    async def _start(self, exit_stack: AsyncExitStack):
        """
        Start the task runner and prep for context exit

        - Creates a cluster if an external address is not set
        - Creates a client to connect to the cluster
        - Pushes a call to wait for all running futures to complete on exit
        """
        if self.address:
            self.logger.info(
                f"Connecting to an existing Dask cluster at {self.address}"
            )
            connect_to = self.address
        else:
            self.logger.info(
                f"Creating a new Dask cluster with `{to_qualified_name(self.cluster_class)}`"
            )
            connect_to = self._cluster = await exit_stack.enter_async_context(
                self.cluster_class(asynchronous=True, **self.cluster_kwargs)
            )
            if self.adapt_kwargs:
                self._cluster.adapt(**self.adapt_kwargs)

        self._client = await exit_stack.enter_async_context(
            distributed.Client(connect_to, asynchronous=True, **self.client_kwargs)
        )

        # Wait for all futures before tearing down the client / cluster on exit
        exit_stack.push_async_callback(self._wait_for_all_futures)

        if self._client.dashboard_link:
            self.logger.info(
                f"The Dask dashboard is available at {self._client.dashboard_link}",
            )

    async def _wait_for_all_futures(self):
        """
        Waits for all futures to complete without timeout, ignoring any exceptions.
        """
        # Attempt to wait for all futures to complete
        for future in self._dask_futures.values():
            try:
                await future.result()
            except Exception:
                pass

    def __getstate__(self):
        """
        Allow the `DaskTaskRunner` to be serialized by dropping the `distributed.Client`
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
