import uuid
from functools import partial
from typing import Any, Dict, Iterable, Optional, Type, Union

import distributed
from distributed.deploy.cluster import Cluster

from prefect.context import FlowRunContext
from prefect.new_task_runners import PrefectFuture, TaskConcurrencyType, TaskRunner
from prefect.states import exception_to_crashed_state
from prefect.tasks import Task
from prefect.utilities.asyncutils import run_sync
from prefect.utilities.collections import visit_collection
from prefect.utilities.importtools import from_qualified_name, to_qualified_name


class DaskTaskRunner(TaskRunner):
    def __init__(
        self,
        cluster: Optional[Cluster] = None,
        address: Optional[str] = None,
        cluster_class: Union[str, Type[Cluster], None] = None,
        cluster_kwargs: Optional[Dict] = None,
        adapt_kwargs: Optional[Dict] = None,
        client_kwargs: Optional[Dict] = None,
    ):
        # Validate settings and infer defaults
        resolved_cluster_class: Optional[Type[Cluster]] = None
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
            if not cluster.asynchronous:
                raise ValueError(
                    "The cluster must have `asynchronous=True` to be "
                    "used with `DaskTaskRunner`."
                )
        else:
            if isinstance(cluster_class, str):
                resolved_cluster_class = from_qualified_name(cluster_class)
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
        self.address = address
        self.cluster_class = resolved_cluster_class
        self.cluster_kwargs = cluster_kwargs
        self.adapt_kwargs = adapt_kwargs
        self.client_kwargs = client_kwargs

        # Runtime attributes
        self._client: Optional[distributed.Client] = None
        self._cluster: Optional[Cluster] = cluster
        self._dask_futures: Dict[uuid.UUID, "distributed.Future"] = {}

        super().__init__()

    @property
    def concurrency_type(self) -> TaskConcurrencyType:
        return (
            TaskConcurrencyType.PARALLEL
            if self.cluster_kwargs.get("processes")
            else TaskConcurrencyType.CONCURRENT
        )

    def submit(
        self,
        task: "Task",
        parameters: Optional[Dict[str, Any]] = None,
        wait_for: Optional[Iterable[PrefectFuture]] = None,
    ) -> PrefectFuture:
        if not self._client:
            raise ValueError("Task runner must be used as a context manager.")
        from prefect.new_task_engine import run_task, run_task_sync

        task_run_id = uuid.uuid4()

        future = PrefectFuture(key=task_run_id, task_runner=self)

        # unpack the upstream call in order to cast Prefect futures to Dask futures
        # where possible to optimize Dask task scheduling
        parameters = self._optimize_futures(parameters)
        wait_for = self._optimize_futures(wait_for)

        dask_key = self._generate_dask_key(task, task_run_id, parameters)

        flow_run_context = FlowRunContext.get()
        flow_run = getattr(flow_run_context, "flow_run", None)

        if task.isasync:
            self._dask_futures[task_run_id] = self._client.submit(
                partial(
                    run_task,
                    task=task,
                    task_run_id=task_run_id,
                    flow_run_id=flow_run.id if flow_run else None,
                    parameters=parameters,
                    wait_for=wait_for,
                    return_type="state",
                ),
                key=dask_key,
                # Dask defaults to treating functions are pure, but we set this here for
                # explicit expectations. If this task run is submitted to Dask twice, the
                # result of the first run should be returned. Subsequent runs would return
                # `Abort` exceptions if they were submitted again.
                pure=True,
            )
        else:
            self._dask_futures[task_run_id] = self._client.submit(
                partial(
                    run_task_sync,
                    task=task,
                    task_run_id=task_run_id,
                    flow_run_id=flow_run.id if flow_run else None,
                    parameters=parameters,
                    wait_for=wait_for,
                    return_type="state",
                ),
                key=dask_key,
                pure=True,
            )

        return future

    def wait(self, key: uuid.UUID, timeout: Optional[float] = None):
        future = self._dask_futures[key]
        try:
            return future.result(timeout=timeout)
        except distributed.TimeoutError:
            return None
        except BaseException as exc:
            return run_sync(exception_to_crashed_state(exc))

    def _optimize_futures(self, expr):
        def visit_fn(expr):
            if isinstance(expr, PrefectFuture):
                dask_future = self._dask_futures.get(expr.key)
                if dask_future is not None:
                    return dask_future
            # Fallback to return the expression unaltered
            return expr

        return visit_collection(expr, visit_fn=visit_fn, return_data=True)

    def _generate_dask_key(
        self, task: "Task", task_run_id: uuid.UUID, parameters: Optional[Dict[str, Any]]
    ) -> str:
        flow_run_context = FlowRunContext.get()
        flow_run = getattr(flow_run_context, "flow_run", None)
        task_run_name, _ = task.generate_run_name(parameters or {})

        if not flow_run:
            return f"{task_run_name}-{task_run_id}"
        return f"{task_run_name}-{task_run_id}-{flow_run.run_count}"

    def __enter__(self):
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
            self._connect_to = self._cluster = self.cluster_class(
                **self.cluster_kwargs
            ).__enter__()

            if self.adapt_kwargs:
                self._cluster.adapt(**self.adapt_kwargs)

        self._client = distributed.Client(
            self._connect_to, **self.client_kwargs
        ).__enter__()

        if self._client.dashboard_link:
            self.logger.info(
                f"The Dask dashboard is available at {self._client.dashboard_link}",
            )
        return self

    def __exit__(self, *args):
        if self._cluster:
            self._cluster.__exit__(*args)
        if self._client:
            self._client.__exit__(*args)
