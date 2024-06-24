"""
Interface and implementations of the Dask Task Runner.
[Task Runners](https://docs.prefect.io/api-ref/prefect/task-runners/)
in Prefect are responsible for managing the execution of Prefect task runs.
Generally speaking, users are not expected to interact with
task runners outside of configuring and initializing them for a flow.

Example:
    ```python
    import time

    from prefect import flow, task

    @task
    def shout(number):
        time.sleep(0.5)
        print(f"#{number}")

    @flow
    def count_to(highest_number):
        for number in range(highest_number):
            shout.submit(number)

    if __name__ == "__main__":
        count_to(10)

    # outputs
    #0
    #1
    #2
    #3
    #4
    #5
    #6
    #7
    #8
    #9
    ```

    Switching to a `DaskTaskRunner`:
    ```python
    import time

    from prefect import flow, task
    from prefect_dask import DaskTaskRunner

    @task
    def shout(number):
        time.sleep(0.5)
        print(f"#{number}")

    @flow(task_runner=DaskTaskRunner)
    def count_to(highest_number):
        for number in range(highest_number):
            shout.submit(number)

    if __name__ == "__main__":
        count_to(10)

    # outputs
    #3
    #7
    #2
    #6
    #4
    #0
    #1
    #5
    #8
    #9
    ```
"""

import inspect
from contextlib import ExitStack
from typing import (
    Any,
    Callable,
    Coroutine,
    Dict,
    Iterable,
    Optional,
    Set,
    TypeVar,
    Union,
    overload,
)

import distributed
from typing_extensions import ParamSpec

from prefect.client.schemas.objects import State, TaskRunInput
from prefect.futures import PrefectFuture, PrefectFutureList, PrefectWrappedFuture
from prefect.logging.loggers import get_logger, get_run_logger
from prefect.task_runners import TaskRunner
from prefect.tasks import Task
from prefect.utilities.asyncutils import run_coro_as_sync
from prefect.utilities.collections import visit_collection
from prefect.utilities.importtools import from_qualified_name, to_qualified_name
from prefect_dask.client import PrefectDaskClient

logger = get_logger(__name__)

P = ParamSpec("P")
T = TypeVar("T")
F = TypeVar("F", bound=PrefectFuture)
R = TypeVar("R")


class PrefectDaskFuture(PrefectWrappedFuture[R, distributed.Future]):
    """
    A Prefect future that wraps a distributed.Future. This future is used
    when the task run is submitted to a DaskTaskRunner.
    """

    def wait(self, timeout: Optional[float] = None) -> None:
        try:
            result = self._wrapped_future.result(timeout=timeout)
        except Exception:
            # either the task failed or the timeout was reached
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
            except distributed.TimeoutError as exc:
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
            " Please call `.wait()` or `.result()` on futures to ensure they resolve.",
        )


class DaskTaskRunner(TaskRunner):
    """
    A parallel task_runner that submits tasks to the `dask.distributed` scheduler.
    By default a temporary `distributed.LocalCluster` is created (and
    subsequently torn down) within the `start()` contextmanager. To use a
    different cluster class (e.g.
    [`dask_kubernetes.KubeCluster`](https://kubernetes.dask.org/)), you can
    specify `cluster_class`/`cluster_kwargs`.

    Alternatively, if you already have a dask cluster running, you can provide
    the cluster object via the `cluster` kwarg or the address of the scheduler
    via the `address` kwarg.
    !!! warning "Multiprocessing safety"
        Note that, because the `DaskTaskRunner` uses multiprocessing, calls to flows
        in scripts must be guarded with `if __name__ == "__main__":` or warnings will
        be displayed.

    Args:
        cluster (distributed.deploy.Cluster, optional): Currently running dask cluster;
            if one is not provider (or specified via `address` kwarg), a temporary
            cluster will be created in `DaskTaskRunner.start()`. Defaults to `None`.
        address (string, optional): Address of a currently running dask
            scheduler. Defaults to `None`.
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
        ```python
        from prefect import flow
        from prefect_dask.task_runners import DaskTaskRunner

        @flow(task_runner=DaskTaskRunner)
        def my_flow():
            ...
        ```

        Using a temporary cluster running elsewhere. Any Dask cluster class should
        work, here we use [dask-cloudprovider](https://cloudprovider.dask.org):
        ```python
        DaskTaskRunner(
            cluster_class="dask_cloudprovider.FargateCluster",
            cluster_kwargs={
                "image": "prefecthq/prefect:latest",
                "n_workers": 5,
            },
        )
        ```

        Connecting to an existing dask cluster:
        ```python
        DaskTaskRunner(address="192.0.2.255:8786")
        ```
    """

    def __init__(
        self,
        cluster: Optional[distributed.deploy.Cluster] = None,
        address: Optional[str] = None,
        cluster_class: Union[str, Callable, None] = None,
        cluster_kwargs: Optional[Dict] = None,
        adapt_kwargs: Optional[Dict] = None,
        client_kwargs: Optional[Dict] = None,
    ):
        # Validate settings and infer defaults
        if address:
            if cluster or cluster_class or cluster_kwargs or adapt_kwargs:
                raise ValueError(
                    "Cannot specify `address` and "
                    "`cluster`/`cluster_class`/`cluster_kwargs`/`adapt_kwargs`"
                )
        elif cluster:
            if cluster_class or cluster_kwargs:
                raise ValueError(
                    "Cannot specify `cluster` and `cluster_class`/`cluster_kwargs`"
                )
        else:
            if isinstance(cluster_class, str):
                cluster_class = from_qualified_name(cluster_class)
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
        self._client: PrefectDaskClient = None
        self._cluster: "distributed.deploy.Cluster" = cluster

        self._exit_stack = ExitStack()

        super().__init__()

    def __eq__(self, other: object) -> bool:
        """
        Check if an instance has the same settings as this task runner.
        """
        if isinstance(other, DaskTaskRunner):
            return (
                self.address == other.address
                and self.cluster_class == other.cluster_class
                and self.cluster_kwargs == other.cluster_kwargs
                and self.adapt_kwargs == other.adapt_kwargs
                and self.client_kwargs == other.client_kwargs
            )
        else:
            return False

    def duplicate(self):
        """
        Create a new instance of the task runner with the same settings.
        """
        return type(self)(
            address=self.address,
            cluster_class=self.cluster_class,
            cluster_kwargs=self.cluster_kwargs,
            adapt_kwargs=self.adapt_kwargs,
            client_kwargs=self.client_kwargs,
        )

    @overload
    def submit(
        self,
        task: "Task[P, Coroutine[Any, Any, R]]",
        parameters: Dict[str, Any],
        wait_for: Optional[Iterable[PrefectFuture]] = None,
        dependencies: Optional[Dict[str, Set[TaskRunInput]]] = None,
    ) -> PrefectDaskFuture[R]:
        ...

    @overload
    def submit(
        self,
        task: "Task[Any, R]",
        parameters: Dict[str, Any],
        wait_for: Optional[Iterable[PrefectFuture]] = None,
        dependencies: Optional[Dict[str, Set[TaskRunInput]]] = None,
    ) -> PrefectDaskFuture[R]:
        ...

    def submit(
        self,
        task: Task,
        parameters: Dict[str, Any],
        wait_for: Optional[Iterable[PrefectFuture]] = None,
        dependencies: Optional[Dict[str, Set[TaskRunInput]]] = None,
    ) -> PrefectDaskFuture:
        if not self._started:
            raise RuntimeError(
                "The task runner must be started before submitting work."
            )

        # unpack the upstream call in order to cast Prefect futures to Dask futures
        # where possible to optimize Dask task scheduling
        parameters = self._optimize_futures(parameters)

        future = self._client.submit(
            task,
            parameters=parameters,
            wait_for=wait_for,
            dependencies=dependencies,
            return_type="state",
        )
        return PrefectDaskFuture(wrapped_future=future, task_run_id=future.task_run_id)

    @overload
    def map(
        self,
        task: "Task[P, Coroutine[Any, Any, R]]",
        parameters: Dict[str, Any],
        wait_for: Optional[Iterable[PrefectFuture]] = None,
    ) -> PrefectFutureList[PrefectDaskFuture[R]]:
        ...

    @overload
    def map(
        self,
        task: "Task[Any, R]",
        parameters: Dict[str, Any],
        wait_for: Optional[Iterable[PrefectFuture]] = None,
    ) -> PrefectFutureList[PrefectDaskFuture[R]]:
        ...

    def map(
        self,
        task: "Task",
        parameters: Dict[str, Any],
        wait_for: Optional[Iterable[PrefectFuture]] = None,
    ):
        return super().map(task, parameters, wait_for)

    def _optimize_futures(self, expr):
        def visit_fn(expr):
            if isinstance(expr, PrefectDaskFuture):
                dask_future = expr.wrapped_future
                if dask_future is not None:
                    return dask_future
            # Fallback to return the expression unaltered
            return expr

        return visit_collection(expr, visit_fn=visit_fn, return_data=True)

    def __enter__(self):
        """
        Start the task runner and prep for context exit.
        - Creates a cluster if an external address is not set.
        - Creates a client to connect to the cluster.
        """
        super().__enter__()
        exit_stack = self._exit_stack.__enter__()
        if self._cluster:
            self.logger.info(f"Connecting to existing Dask cluster {self._cluster}")
            self._connect_to = self._cluster
            if self.adapt_kwargs:
                self._cluster.adapt(**self.adapt_kwargs)
        elif self.address:
            self.logger.info(
                f"Connecting to an existing Dask cluster at {self.address}"
            )
            self._connect_to = self.address
        else:
            self.cluster_class = self.cluster_class or distributed.LocalCluster

            self.logger.info(
                f"Creating a new Dask cluster with "
                f"`{to_qualified_name(self.cluster_class)}`"
            )
            self._connect_to = self._cluster = exit_stack.enter_context(
                self.cluster_class(**self.cluster_kwargs)
            )

            if self.adapt_kwargs:
                maybe_coro = self._cluster.adapt(**self.adapt_kwargs)
                if inspect.isawaitable(maybe_coro):
                    run_coro_as_sync(maybe_coro)

        self._client = exit_stack.enter_context(
            PrefectDaskClient(self._connect_to, **self.client_kwargs)
        )

        if self._client.dashboard_link:
            self.logger.info(
                f"The Dask dashboard is available at {self._client.dashboard_link}",
            )

        return self

    def __exit__(self, *args):
        self._exit_stack.__exit__(*args)
        super().__exit__(*args)
