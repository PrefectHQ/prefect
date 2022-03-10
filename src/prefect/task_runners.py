"""
Interface and implementations of various task runners.

[Task Runners](/concepts/task-runners/) in Prefect are responsible for managing the execution of Prefect task runs. Generally speaking, users are not expected to interact with task runners outside of configuring and initializing them for a flow.

Example:

    >>> from prefect import flow, task
    >>> from prefect.task_runners import SequentialTaskRunner
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
    >>> @flow(task_runner=SequentialTaskRunner())
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
    >>> from prefect.task_runners import DaskTaskRunner
    >>> flow.task_runner = DaskTaskRunner()
    >>> greetings(["arthur", "trillian", "ford", "marvin"])
    hello arthur
    goodbye arthur
    hello trillian
    hello ford
    goodbye marvin
    hello marvin
    goodbye ford
    goodbye trillian

For usage details, see the [Task Runners](/concepts/task-runners/) documentation.
"""
import abc
from contextlib import AsyncExitStack, asynccontextmanager
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterator,
    Awaitable,
    Callable,
    Dict,
    Optional,
    Set,
    TypeVar,
    Union,
)
from uuid import UUID

import anyio

if TYPE_CHECKING:
    import distributed
    import ray
    from anyio.abc import TaskGroup
else:
    distributed = None
    ray = None


from prefect.futures import PrefectFuture
from prefect.logging import get_logger
from prefect.orion.schemas.core import TaskRun
from prefect.orion.schemas.states import State
from prefect.states import exception_to_crashed_state
from prefect.utilities.asyncio import A, sync_compatible
from prefect.utilities.hashing import to_qualified_name
from prefect.utilities.importtools import import_object

T = TypeVar("T", bound="BaseTaskRunner")
R = TypeVar("R")


class BaseTaskRunner(metaclass=abc.ABCMeta):
    def __init__(self) -> None:
        self.logger = get_logger(f"task_runner.{self.name}")
        self._started: bool = False

    @property
    def name(self):
        return type(self).__name__.lower().replace("taskrunner", "")

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

        Implementers should be careful to ensure that this function never returns or
        raises an exception.
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
            self.logger.debug(f"Starting task runner...")
            try:
                await self._start(exit_stack)
                self._started = True
                yield self
            finally:
                self.logger.debug(f"Shutting down task runner...")
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
        try:
            result = await run_fn(**run_kwargs)
        except BaseException as exc:
            result = exception_to_crashed_state(exc)

        self._results[task_run.id] = result

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
        Note that, because the `DaskTaskRunner` uses multiprocessing, calls to flows
        in scripts must be guarded with `if __name__ == "__main__":` or warnings will
        be displayed.

    Args:
        address (string, optional): Address of a currently running dask
            scheduler; if one is not provided, a temporary cluster will be
            created in `DaskTaskRunner.start()`.  Defaults to `None`.
        cluster_class (string or callable, optional): The cluster class to use
            when creating a temporary dask cluster. Can be either the full
            class name (e.g. `"distributed.LocalCluster"`), or the class itself.
        cluster_kwargs (dict, optional): Additional kwargs to pass to the
            `cluster_class` when creating a temporary dask cluster.
        adapt_kwargs (dict, optional): Additional kwargs to pass to `cluster.adapt`
            when creating a temporary dask cluster. Note that adaptive scaling
            is only enabled if `adapt_kwargs` are provided.
        client_kwargs (dict, optional): Additional kwargs to use when creating a
            [`dask.distributed.Client`](https://distributed.dask.org/en/latest/api.html#client).

    Examples:

        Using a temporary local dask cluster:
        >>> from prefect import flow
        >>> from prefect.task_runners import DaskTaskRunner
        >>> @flow(task_runner=DaskTaskRunner)
        >>> def my_flow():
        >>>     ...

        Using a temporary cluster running elsewhere. Any Dask cluster class should
        work, here we use [dask-cloudprovider](https://cloudprovider.dask.org):
        >>> DaskTaskRunner(
        >>>     cluster_class="dask_cloudprovider.FargateCluster",
        >>>     cluster_kwargs={
        >>>          "image": "prefecthq/prefect:latest",
        >>>          "n_workers": 5,
        >>>     },
        >>> )


        Connecting to an existing dask cluster:
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
                cluster_class = cluster_class

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
        Retrieve the dask future corresponding to a Prefect future.

        The Dask future is for the `run_fn`, which should return a `State`.
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
        except self._distributed.TimeoutError:
            return None
        except BaseException as exc:
            return exception_to_crashed_state(exc)

    @property
    def _distributed(self) -> "distributed":
        """
        Delayed import of `distributed` allowing configuration of the task runner
        without the extra installed and improves `prefect` import times.
        """
        global distributed

        if distributed is None:
            try:
                import distributed
            except ImportError as exc:
                raise RuntimeError(
                    "Using the `DaskTaskRunner` requires `distributed` to be installed."
                ) from exc

        return distributed

    async def _start(self, exit_stack: AsyncExitStack):
        """
        Start the task runner and prep for context exit.

        - Creates a cluster if an external address is not set.
        - Creates a client to connect to the cluster.
        - Pushes a call to wait for all running futures to complete on exit.
        """
        if self.address:
            self.logger.info(
                f"Connecting to an existing Dask cluster at {self.address}"
            )
            connect_to = self.address
        else:
            self.cluster_class = self.cluster_class or self._distributed.LocalCluster

            self.logger.info(
                f"Creating a new Dask cluster with `{to_qualified_name(self.cluster_class)}`"
            )
            connect_to = self._cluster = await exit_stack.enter_async_context(
                self.cluster_class(asynchronous=True, **self.cluster_kwargs)
            )
            if self.adapt_kwargs:
                self._cluster.adapt(**self.adapt_kwargs)

        self._client = await exit_stack.enter_async_context(
            self._distributed.Client(
                connect_to, asynchronous=True, **self.client_kwargs
            )
        )

        if self._client.dashboard_link:
            self.logger.info(
                f"The Dask dashboard is available at {self._client.dashboard_link}",
            )

    def __getstate__(self):
        """
        Allow the `DaskTaskRunner` to be serialized by dropping the `distributed.Client`,
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
        self._client = self._distributed.get_client()


class ConcurrentTaskRunner(BaseTaskRunner):
    """
    A concurrent task runner that allows tasks to switch when blocking on IO.
    Synchronous tasks will be submitted to a thread pool maintained by `anyio`.

    Examples:

        Using a thread for concurrency:
        >>> from prefect import flow
        >>> from prefect.task_runners import ConcurrentTaskRunner
        >>> @flow(task_runner=ConcurrentTaskRunner)
        >>> def my_flow():
        >>>     ...
    """

    def __init__(self):
        # TODO: Consider adding `max_workers` support using anyio capacity limiters

        # Runtime attributes
        self._task_group: TaskGroup = None
        self._results: Dict[UUID, Any] = {}
        self._task_run_ids: Set[UUID] = set()
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

        if not self._task_group:
            raise RuntimeError(
                "The concurrent task runner cannot be used to submit work after "
                "serialization."
            )

        # Rely on the event loop for concurrency
        self._task_group.start_soon(
            self._run_and_store_result, task_run.id, run_fn, run_kwargs
        )

        # Track the task run id so we can ensure to gather it later
        self._task_run_ids.add(task_run.id)

        return PrefectFuture(
            task_run=task_run, task_runner=self, asynchronous=asynchronous
        )

    async def wait(
        self,
        prefect_future: PrefectFuture,
        timeout: float = None,
    ) -> Optional[State]:
        if not self._task_group:
            raise RuntimeError(
                "The concurrent task runner cannot be used to wait for work after "
                "serialization."
            )

        return await self._get_run_result(prefect_future.task_run.id, timeout)

    async def _run_and_store_result(self, task_run_id: UUID, run_fn, run_kwargs):
        """
        Simple utility to store the orchestration result in memory on completion

        Since this run is occuring on the main thread, we capture exceptions to prevent
        task crashes from crashing the flow run.
        """
        try:
            self._results[task_run_id] = await run_fn(**run_kwargs)
        except BaseException as exc:
            self._results[task_run_id] = exception_to_crashed_state(exc)

    async def _get_run_result(self, task_run_id: UUID, timeout: float = None):
        """
        Block until the run result has been populated.
        """
        with anyio.move_on_after(timeout):
            result = self._results.get(task_run_id)
            while not result:
                await anyio.sleep(0)  # yield to other tasks
                result = self._results.get(task_run_id)
        return result

    async def _start(self, exit_stack: AsyncExitStack):
        """
        Start the process pool
        """
        self._task_group = await exit_stack.enter_async_context(
            anyio.create_task_group()
        )

    def __getstate__(self):
        """
        Allow the `ConcurrentTaskRunner` to be serialized by dropping the task group.
        """
        data = self.__dict__.copy()
        data.update({k: None for k in {"_task_group"}})
        return data

    def __setstate__(self, data: dict):
        """
        When deserialized, we will no longer have a reference to the task group.
        """
        self.__dict__.update(data)
        self._task_group = None


class RayTaskRunner(BaseTaskRunner):
    """
    A parallel task_runner that submits tasks to `ray`.

    By default, a temporary Ray cluster is created for the duration of the flow run.

    Alternatively, if you already have a `ray` instance running, you can provide
    the connection URL via the `address` kwarg.

    Args:
        address (string, optional): Address of a currently running `ray` instance; if
            one is not provided, a temporary instance will be created.
        init_kwargs (dict, optional): Additional kwargs to use when calling `ray.init`.

    Examples:

        Using a temporary local ray cluster:
        >>> from prefect import flow
        >>> from prefect.task_runners import RayTaskRunner
        >>> @flow(task_runner=RayTaskRunner)

        Connecting to an existing ray instance:
        >>> RayTaskRunner(address="ray://192.0.2.255:8786")
    """

    def __init__(
        self,
        address: str = None,
        init_kwargs: dict = None,
    ):
        # Store settings
        self.address = address
        self.init_kwargs = init_kwargs.copy() if init_kwargs else {}

        self.init_kwargs.setdefault("namespace", "prefect")
        self.init_kwargs

        # Runtime attributes
        self._ray_refs: Dict[UUID, "ray.ObjectRef"] = {}

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

        # Ray does not support the submission of async functions and we must create a
        # sync entrypoint
        self._ray_refs[task_run.id] = ray.remote(sync_compatible(run_fn)).remote(
            **run_kwargs
        )
        return PrefectFuture(
            task_run=task_run, task_runner=self, asynchronous=asynchronous
        )

    async def wait(
        self,
        prefect_future: PrefectFuture,
        timeout: float = None,
    ) -> Optional[State]:
        ref = self._get_ray_ref(prefect_future)

        result = None

        with anyio.move_on_after(timeout):
            # We await the reference directly instead of using `ray.get` so we can
            # avoid blocking the event loop
            try:
                result = await ref
            except BaseException as exc:
                result = exception_to_crashed_state(exc)

        return result

    @property
    def _ray(self) -> "ray":
        """
        Delayed import of `ray` allowing configuration of the task runner
        without the extra installed and improves `prefect` import times.
        """
        global ray

        if ray is None:
            try:
                import ray
            except ImportError as exc:
                raise RuntimeError(
                    "Using the `RayTaskRunner` requires `ray` to be installed."
                ) from exc

        return ray

    async def _start(self, exit_stack: AsyncExitStack):
        """
        Start the task runner and prep for context exit.

        - Creates a cluster if an external address is not set.
        - Creates a client to connect to the cluster.
        - Pushes a call to wait for all running futures to complete on exit.
        """
        if self.address:
            self.logger.info(
                f"Connecting to an existing Ray instance at {self.address}"
            )
            init_args = (self.address,)
        else:
            self.logger.info("Creating a local Ray instance")
            init_args = ()

        # When connecting to an out-of-process cluster (e.g. ray://ip) this returns a
        # `ClientContext` otherwise it returns a `dict`.
        context_or_metadata = self._ray.init(*init_args, **self.init_kwargs)
        if isinstance(context_or_metadata, dict):
            metadata = context_or_metadata
            context = None
        else:
            metadata = None  # TODO: Some of this may be retrievable from the client ctx
            context = context_or_metadata

        # Shutdown differs depending on the connection type
        if context:
            # Just disconnect the client
            exit_stack.push(context)
        else:
            # Shutdown ray
            exit_stack.push_async_callback(self._shutdown_ray)

        # Display some information about the cluster
        nodes = ray.nodes()
        living_nodes = [node for node in nodes if node.get("alive")]
        self.logger.info(f"Using Ray cluster with {len(living_nodes)} nodes.")

        if metadata and metadata.get("webui_url"):
            self.logger.info(
                f"The Ray UI is available at {metadata['webui_url']}",
            )

    async def _shutdown_ray(self):
        self.logger.debug("Shutting down Ray cluster...")
        self._ray.shutdown()

    def _get_ray_ref(self, prefect_future: PrefectFuture) -> "ray.ObjectRef":
        """
        Retrieve the ray object reference corresponding to a prefect future.
        """
        return self._ray_refs[prefect_future.run_id]
