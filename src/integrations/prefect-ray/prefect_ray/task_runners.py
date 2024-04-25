"""
Interface and implementations of the Ray Task Runner.
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

    Switching to a `RayTaskRunner`:
    ```python
    import time

    from prefect import flow, task
    from prefect_ray import RayTaskRunner

    @task
    def shout(number):
        time.sleep(0.5)
        print(f"#{number}")

    @flow(task_runner=RayTaskRunner)
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

from contextlib import AsyncExitStack
from typing import Awaitable, Callable, Dict, Optional
from uuid import UUID

import anyio
import ray
from ray.exceptions import RayTaskError

from prefect.futures import PrefectFuture
from prefect.states import State, exception_to_crashed_state
from prefect.task_runners import BaseTaskRunner, R, TaskConcurrencyType
from prefect.utilities.asyncutils import sync_compatible
from prefect.utilities.collections import visit_collection
from prefect_ray.context import RemoteOptionsContext


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
        ```python
        from prefect import flow
        from prefect_ray.task_runners import RayTaskRunner

        @flow(task_runner=RayTaskRunner())
        def my_flow():
            ...
        ```
        Connecting to an existing ray instance:
        ```python
        RayTaskRunner(address="ray://192.0.2.255:8786")
        ```
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

        # Runtime attributes
        self._ray_refs: Dict[str, "ray.ObjectRef"] = {}

        super().__init__()

    def duplicate(self):
        """
        Return a new instance of with the same settings as this one.
        """
        return type(self)(address=self.address, init_kwargs=self.init_kwargs)

    def __eq__(self, other: object) -> bool:
        """
        Check if an instance has the same settings as this task runner.
        """
        if type(self) == type(other):
            return (
                self.address == other.address and self.init_kwargs == other.init_kwargs
            )
        else:
            return NotImplemented

    @property
    def concurrency_type(self) -> TaskConcurrencyType:
        return TaskConcurrencyType.PARALLEL

    async def submit(
        self,
        key: UUID,
        call: Callable[..., Awaitable[State[R]]],
    ) -> None:
        if not self._started:
            raise RuntimeError(
                "The task runner must be started before submitting work."
            )

        call_kwargs, upstream_ray_obj_refs = self._exchange_prefect_for_ray_futures(
            call.keywords
        )

        remote_options = RemoteOptionsContext.get().current_remote_options
        # Ray does not support the submission of async functions and we must create a
        # sync entrypoint
        if remote_options:
            ray_decorator = ray.remote(**remote_options)
        else:
            ray_decorator = ray.remote

        self._ray_refs[key] = (
            ray_decorator(self._run_prefect_task)
            .options(name=call.keywords["task_run"].name)
            .remote(sync_compatible(call.func), *upstream_ray_obj_refs, **call_kwargs)
        )

    def _exchange_prefect_for_ray_futures(self, kwargs_prefect_futures):
        """Exchanges Prefect futures for Ray futures."""

        upstream_ray_obj_refs = []

        def exchange_prefect_for_ray_future(expr):
            """Exchanges Prefect future for Ray future."""
            if isinstance(expr, PrefectFuture):
                ray_future = self._ray_refs.get(expr.key)
                if ray_future is not None:
                    upstream_ray_obj_refs.append(ray_future)
                    return ray_future
            return expr

        kwargs_ray_futures = visit_collection(
            kwargs_prefect_futures,
            visit_fn=exchange_prefect_for_ray_future,
            return_data=True,
        )

        return kwargs_ray_futures, upstream_ray_obj_refs

    @staticmethod
    def _run_prefect_task(func, *upstream_ray_obj_refs, **kwargs):
        """Resolves Ray futures before calling the actual Prefect task function.

        Passing upstream_ray_obj_refs directly as args enables Ray to wait for
        upstream tasks before running this remote function.
        This variable is otherwise unused as the ray object refs are also
        contained in kwargs.
        """

        def resolve_ray_future(expr):
            """Resolves Ray future."""
            if isinstance(expr, ray.ObjectRef):
                return ray.get(expr)
            return expr

        kwargs = visit_collection(kwargs, visit_fn=resolve_ray_future, return_data=True)

        return func(**kwargs)

    async def wait(self, key: UUID, timeout: float = None) -> Optional[State]:
        ref = self._get_ray_ref(key)

        result = None

        with anyio.move_on_after(timeout):
            # We await the reference directly instead of using `ray.get` so we can
            # avoid blocking the event loop
            try:
                result = await ref
            except RayTaskError as exc:
                # unwrap the original exception that caused task failure, except for
                # KeyboardInterrupt, which unwraps as TaskCancelledError
                result = await exception_to_crashed_state(exc.cause)
            except BaseException as exc:
                result = await exception_to_crashed_state(exc)

        return result

    async def _start(self, exit_stack: AsyncExitStack):
        """
        Start the task runner and prep for context exit.

        - Creates a cluster if an external address is not set.
        - Creates a client to connect to the cluster.
        - Pushes a call to wait for all running futures to complete on exit.
        """
        if self.address and self.address != "auto":
            self.logger.info(
                f"Connecting to an existing Ray instance at {self.address}"
            )
            init_args = (self.address,)
        elif ray.is_initialized():
            self.logger.info(
                "Local Ray instance is already initialized. "
                "Using existing local instance."
            )
            return
        else:
            self.logger.info("Creating a local Ray instance")
            init_args = ()

        context = ray.init(*init_args, **self.init_kwargs)
        dashboard_url = getattr(context, "dashboard_url", None)
        exit_stack.push(context)

        # Display some information about the cluster
        nodes = ray.nodes()
        living_nodes = [node for node in nodes if node.get("alive")]
        self.logger.info(f"Using Ray cluster with {len(living_nodes)} nodes.")

        if dashboard_url:
            self.logger.info(
                f"The Ray UI is available at {dashboard_url}",
            )

    async def _shutdown_ray(self):
        """
        Shuts down the cluster.
        """
        self.logger.debug("Shutting down Ray cluster...")
        ray.shutdown()

    def _get_ray_ref(self, key: UUID) -> "ray.ObjectRef":
        """
        Retrieve the ray object reference corresponding to a prefect future.
        """
        return self._ray_refs[key]
