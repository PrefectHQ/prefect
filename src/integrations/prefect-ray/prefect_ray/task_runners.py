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

import asyncio
import inspect
from typing import Any, Dict, Iterable, Optional, Set
from uuid import UUID, uuid4

import ray
from ray.exceptions import GetTimeoutError

from prefect.client.schemas.objects import TaskRunInput
from prefect.context import serialize_context
from prefect.exceptions import MappingLengthMismatch, MappingMissingIterable
from prefect.new_futures import PrefectFuture
from prefect.new_task_engine import run_task_async
from prefect.new_task_runners import TaskRunner
from prefect.states import State, exception_to_crashed_state
from prefect.tasks import Task
from prefect.utilities.annotations import allow_failure, quote, unmapped
from prefect.utilities.asyncutils import run_sync
from prefect.utilities.callables import (
    collapse_variadic_parameters,
    explode_variadic_parameter,
    get_parameter_defaults,
)
from prefect.utilities.collections import isiterable, visit_collection
from prefect_ray.context import RemoteOptionsContext


class PrefectRayFuture(PrefectFuture[ray.ObjectRef]):
    def wait(self, timeout: Optional[float] = None) -> None:
        try:
            result = ray.get(self.wrapped_future, timeout=timeout)
        except GetTimeoutError:
            return
        except Exception as exc:
            result = run_sync(exception_to_crashed_state(exc))
        if isinstance(result, State):
            self._final_state = result

    def result(
        self,
        timeout: Optional[float] = None,
        raise_on_failure: bool = True,
    ) -> Any:
        if not self._final_state:
            try:
                object_ref_result = ray.get(self.wrapped_future, timeout=timeout)
            except GetTimeoutError as exc:
                raise TimeoutError(
                    f"Task run {self.task_run_id} did not complete within {timeout} seconds"
                ) from exc

            if isinstance(object_ref_result, State):
                self._final_state = object_ref_result
            else:
                return object_ref_result

        _result = self._final_state.result(
            raise_on_failure=raise_on_failure, fetch=True
        )
        # state.result is a `sync_compatible` function that may or may not return an awaitable
        # depending on whether the parent frame is sync or not
        if inspect.isawaitable(_result):
            _result = run_sync(_result)
        return _result


class RayTaskRunner(TaskRunner):
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
        self._ray_context = None

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

    # @property
    # def concurrency_type(self) -> TaskConcurrencyType:
    #     return TaskConcurrencyType.PARALLEL

    def submit(
        self,
        task: Task,
        parameters: Dict[str, Any],
        wait_for: Optional[Iterable[PrefectFuture]] = None,
        dependencies: Optional[Dict[str, Set[TaskRunInput]]] = None,
    ) -> PrefectRayFuture:
        if not self._started:
            raise RuntimeError(
                "The task runner must be started before submitting work."
            )

        parameters, upstream_ray_obj_refs = self._exchange_prefect_for_ray_futures(
            parameters
        )
        task_run_id = uuid4()
        context = serialize_context()

        remote_options = RemoteOptionsContext.get().current_remote_options
        if remote_options:
            ray_decorator = ray.remote(**remote_options)
        else:
            ray_decorator = ray.remote

        object_ref = (
            ray_decorator(self._run_prefect_task)
            .options(name=task.name)
            .remote(
                *upstream_ray_obj_refs,
                task=task,
                task_run_id=task_run_id,
                parameters=parameters,
                wait_for=wait_for,
                dependencies=dependencies,
                context=context,
            )
        )
        return PrefectRayFuture(task_run_id=task_run_id, wrapped_future=object_ref)

    def map(
        self,
        task: Task,
        parameters: Dict[str, Any],
        wait_for: Optional[Iterable[PrefectFuture]] = None,
    ) -> Iterable[PrefectRayFuture]:
        if not self._started:
            raise RuntimeError(
                "The task runner must be started before submitting work."
            )

        from prefect.utilities.engine import (
            collect_task_run_inputs_sync,
            resolve_inputs_sync,
        )

        # We need to resolve some futures to map over their data, collect the upstream
        # links beforehand to retain relationship tracking.
        task_inputs = {
            k: collect_task_run_inputs_sync(v, max_depth=0)
            for k, v in parameters.items()
        }

        # Resolve the top-level parameters in order to get mappable data of a known length.
        # Nested parameters will be resolved in each mapped child where their relationships
        # will also be tracked.
        parameters = resolve_inputs_sync(parameters, max_depth=0)

        # Ensure that any parameters in kwargs are expanded before this check
        parameters = explode_variadic_parameter(task.fn, parameters)

        iterable_parameters = {}
        static_parameters = {}
        annotated_parameters = {}
        for key, val in parameters.items():
            if isinstance(val, (allow_failure, quote)):
                # Unwrap annotated parameters to determine if they are iterable
                annotated_parameters[key] = val
                val = val.unwrap()

            if isinstance(val, unmapped):
                static_parameters[key] = val.value
            elif isiterable(val):
                iterable_parameters[key] = list(val)
            else:
                static_parameters[key] = val

        if not len(iterable_parameters):
            raise MappingMissingIterable(
                "No iterable parameters were received. Parameters for map must "
                f"include at least one iterable. Parameters: {parameters}"
            )

        iterable_parameter_lengths = {
            key: len(val) for key, val in iterable_parameters.items()
        }
        lengths = set(iterable_parameter_lengths.values())
        if len(lengths) > 1:
            raise MappingLengthMismatch(
                "Received iterable parameters with different lengths. Parameters for map"
                f" must all be the same length. Got lengths: {iterable_parameter_lengths}"
            )

        map_length = list(lengths)[0]

        futures = []
        for i in range(map_length):
            call_parameters = {
                key: value[i] for key, value in iterable_parameters.items()
            }
            call_parameters.update(
                {key: value for key, value in static_parameters.items()}
            )

            # Add default values for parameters; these are skipped earlier since they should
            # not be mapped over
            for key, value in get_parameter_defaults(task.fn).items():
                call_parameters.setdefault(key, value)

            # Re-apply annotations to each key again
            for key, annotation in annotated_parameters.items():
                call_parameters[key] = annotation.rewrap(call_parameters[key])

            # Collapse any previously exploded kwargs
            call_parameters = collapse_variadic_parameters(task.fn, call_parameters)

            futures.append(
                self.submit(
                    task=task,
                    parameters=call_parameters,
                    wait_for=wait_for,
                    dependencies=task_inputs,
                )
            )

        return futures

    def _exchange_prefect_for_ray_futures(self, kwargs_prefect_futures):
        """Exchanges Prefect futures for Ray futures."""

        upstream_ray_obj_refs = []

        def exchange_prefect_for_ray_future(expr):
            """Exchanges Prefect future for Ray future."""
            if isinstance(expr, PrefectRayFuture):
                ray_future = expr.wrapped_future
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
    def _run_prefect_task(
        *upstream_ray_obj_refs,
        task: Task,
        task_run_id: UUID,
        context: Dict[str, Any],
        parameters: Dict[str, Any],
        wait_for: Optional[Iterable[PrefectFuture]] = None,
        dependencies: Optional[Dict[str, Set[TaskRunInput]]] = None,
    ):
        """Resolves Ray futures before calling the actual Prefect task function.

        Passing upstream_ray_obj_refs directly as args enables Ray to wait for
        upstream tasks before running this remote function.
        This variable is otherwise unused as the ray object refs are also
        contained in parameters.
        """

        # Resolve Ray futures to ensure that the task function receives the actual values
        def resolve_ray_future(expr):
            """Resolves Ray future."""
            if isinstance(expr, ray.ObjectRef):
                return ray.get(expr)
            return expr

        parameters = visit_collection(
            parameters, visit_fn=resolve_ray_future, return_data=True
        )

        run_task_kwargs = {
            "task": task,
            "task_run_id": task_run_id,
            "parameters": parameters,
            "wait_for": wait_for,
            "dependencies": dependencies,
            "context": context,
            "return_type": "state",
        }

        # Ray does not support the submission of async functions and we must create a
        # sync entrypoint
        if task.isasync:
            return asyncio.run(run_task_async(**run_task_kwargs))
        else:
            return run_task_async(**run_task_kwargs)

    def __enter__(self):
        super().__enter__()

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
            return self
        else:
            self.logger.info("Creating a local Ray instance")
            init_args = ()

        self._ray_context = ray.init(*init_args, **self.init_kwargs)
        dashboard_url = getattr(self._ray_context, "dashboard_url", None)

        # Display some information about the cluster
        nodes = ray.nodes()
        living_nodes = [node for node in nodes if node.get("alive")]
        self.logger.info(f"Using Ray cluster with {len(living_nodes)} nodes.")

        if dashboard_url:
            self.logger.info(
                f"The Ray UI is available at {dashboard_url}",
            )

        return self

    def __exit__(self, *exc_info):
        """
        Shuts down the cluster.
        """
        self.logger.debug("Shutting down Ray cluster...")
        ray.shutdown()
        super().__exit__(*exc_info)
