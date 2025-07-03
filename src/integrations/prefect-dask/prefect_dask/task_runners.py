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

from __future__ import annotations

import asyncio
from contextlib import ExitStack
from typing import (
    Any,
    Callable,
    Coroutine,
    Iterable,
    Optional,
    Set,
    TypeVar,
    Union,
    overload,
)

import distributed
import distributed.deploy
import distributed.deploy.cluster
from typing_extensions import ParamSpec

from prefect.client.schemas.objects import RunInput, State
from prefect.futures import PrefectFuture, PrefectFutureList, PrefectWrappedFuture
from prefect.logging.loggers import get_logger
from prefect.task_runners import TaskRunner
from prefect.tasks import Task
from prefect.utilities.asyncutils import run_coro_as_sync
from prefect.utilities.collections import visit_collection
from prefect.utilities.importtools import from_qualified_name, to_qualified_name
from prefect_dask.client import PrefectDaskClient

logger = get_logger(__name__)

P = ParamSpec("P")
T = TypeVar("T")
F = TypeVar("F", bound=PrefectFuture[Any])
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

        return self._final_state.result(raise_on_failure=raise_on_failure, _sync=True)


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
        performance_report_path (str, optional): Path where the Dask performance report
            will be saved. If not provided, no performance report will be generated.

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
        cluster: Optional[distributed.deploy.cluster.Cluster] = None,
        address: Optional[str] = None,
        cluster_class: Union[
            str, Callable[[], distributed.deploy.cluster.Cluster], None
        ] = None,
        cluster_kwargs: Optional[dict[str, Any]] = None,
        adapt_kwargs: Optional[dict[str, Any]] = None,
        client_kwargs: Optional[dict[str, Any]] = None,
        performance_report_path: Optional[str] = None,
    ):
        # Validate settings and infer defaults
        resolved_cluster_class: distributed.deploy.cluster.Cluster | None = None
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
                resolved_cluster_class = from_qualified_name(cluster_class)
            elif isinstance(cluster_class, Callable):
                # Store the callable itself, don't instantiate here
                resolved_cluster_class = cluster_class
            else:
                resolved_cluster_class = cluster_class

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
        self.address: str | None = address
        self.cluster_class: (
            str | Callable[[], distributed.deploy.cluster.Cluster] | None
        ) = cluster_class

        self.resolved_cluster_class: distributed.deploy.cluster.Cluster | None = (
            resolved_cluster_class
        )
        self.cluster_kwargs: dict[str, Any] = cluster_kwargs
        self.adapt_kwargs: dict[str, Any] = adapt_kwargs
        self.client_kwargs: dict[str, Any] = client_kwargs
        self.performance_report_path: str | None = performance_report_path

        # Runtime attributes
        self._client: PrefectDaskClient | None = None
        self._cluster: distributed.deploy.cluster.Cluster | None = cluster

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

    @property
    def client(self) -> PrefectDaskClient:
        """
        Get the Dask client for the task runner.

        The client is created on first access. If a remote cluster is not
        provided, the client will attempt to create/connect to a local cluster.
        """
        if not self._client:
            in_dask = False
            try:
                client = distributed.get_client()
                if client.cluster is not None:
                    self._cluster = client.cluster
                elif client.scheduler is not None:
                    self.address = client.scheduler.address
                else:
                    raise RuntimeError("No global client found and no address provided")
                in_dask = True
            except ValueError:
                pass

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
                # Determine the cluster class to use
                if self.resolved_cluster_class:
                    # Use the resolved class if a string was provided
                    class_to_instantiate = self.resolved_cluster_class
                elif callable(self.cluster_class):
                    # Use the provided class object if it's callable
                    class_to_instantiate = self.cluster_class
                else:
                    # Default to LocalCluster only if no specific class was provided or resolved
                    class_to_instantiate = distributed.LocalCluster

                cluster_name = to_qualified_name(class_to_instantiate)
                self.logger.info(f"Creating a new Dask cluster with `{cluster_name}`")

                try:
                    self._connect_to = self._cluster = self._exit_stack.enter_context(
                        class_to_instantiate(**self.cluster_kwargs)
                    )
                except Exception:
                    self.logger.error(
                        f"Failed to create {cluster_name} cluster: ", exc_info=True
                    )
                    raise

                if self.adapt_kwargs:
                    # self._cluster should be non-None here after instantiation
                    if self._cluster:
                        maybe_coro = self._cluster.adapt(**self.adapt_kwargs)
                        if asyncio.iscoroutine(maybe_coro):
                            run_coro_as_sync(maybe_coro)
                    else:
                        # This case should ideally not happen if instantiation succeeded
                        self.logger.warning(
                            "Cluster object not found after instantiation, cannot apply adapt_kwargs."
                        )

            self._client = self._exit_stack.enter_context(
                PrefectDaskClient(self._connect_to, **self.client_kwargs)
            )

            if self.performance_report_path:
                # Register our client as current so that it's found by distributed.get_client()
                self._exit_stack.enter_context(
                    distributed.Client.as_current(self._client)
                )
                self._exit_stack.enter_context(
                    distributed.performance_report(self.performance_report_path)
                )

            if self._client.dashboard_link and not in_dask:
                self.logger.info(
                    f"The Dask dashboard is available at {self._client.dashboard_link}",
                )

        return self._client

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
            performance_report_path=self.performance_report_path,
        )

    @overload
    def submit(
        self,
        task: "Task[P, Coroutine[Any, Any, R]]",
        parameters: dict[str, Any],
        wait_for: Iterable[PrefectDaskFuture[R]] | None = None,
        dependencies: dict[str, Set[RunInput]] | None = None,
    ) -> PrefectDaskFuture[R]: ...

    @overload
    def submit(
        self,
        task: "Task[Any, R]",
        parameters: dict[str, Any],
        wait_for: Iterable[PrefectDaskFuture[R]] | None = None,
        dependencies: dict[str, Set[RunInput]] | None = None,
    ) -> PrefectDaskFuture[R]: ...

    def submit(
        self,
        task: "Union[Task[P, R], Task[P, Coroutine[Any, Any, R]]]",
        parameters: dict[str, Any],
        wait_for: Iterable[PrefectDaskFuture[R]] | None = None,
        dependencies: dict[str, Set[RunInput]] | None = None,
    ) -> PrefectDaskFuture[R]:
        if not self._started:
            raise RuntimeError(
                "The task runner must be started before submitting work."
            )

        # Convert both parameters and wait_for futures to Dask futures
        parameters = self._optimize_futures(parameters)
        wait_for = self._optimize_futures(wait_for) if wait_for else None

        future = self.client.submit(
            task,
            parameters=parameters,
            wait_for=wait_for,
            dependencies=dependencies,
            return_type="state",
        )
        return PrefectDaskFuture[R](
            wrapped_future=future, task_run_id=future.task_run_id
        )

    @overload
    def map(
        self,
        task: "Task[P, Coroutine[Any, Any, R]]",
        parameters: dict[str, Any],
        wait_for: Iterable[PrefectFuture[Any]] | None = None,
    ) -> PrefectFutureList[PrefectDaskFuture[R]]: ...

    @overload
    def map(
        self,
        task: "Task[P, R]",
        parameters: dict[str, Any],
        wait_for: Iterable[PrefectFuture[Any]] | None = None,
    ) -> PrefectFutureList[PrefectDaskFuture[R]]: ...

    def map(
        self,
        task: "Task[P, R]",
        parameters: dict[str, Any],
        wait_for: Iterable[PrefectFuture[Any]] | None = None,
    ):
        return super().map(task, parameters, wait_for)

    def _optimize_futures(self, expr: PrefectDaskFuture[Any] | Any) -> Any:
        def visit_fn(expr: Any) -> Any:
            if isinstance(expr, PrefectDaskFuture):
                return expr.wrapped_future
            # Fallback to return the expression unaltered
            return expr

        return visit_collection(expr, visit_fn=visit_fn, return_data=True)

    def __enter__(self):
        """
        Start the task runner and create an exit stack to manage shutdown.
        """
        super().__enter__()
        self._exit_stack.__enter__()

        return self

    def __exit__(self, *args: Any) -> None:
        self._exit_stack.__exit__(*args)
        super().__exit__(*args)
