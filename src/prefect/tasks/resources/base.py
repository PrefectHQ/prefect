from typing import Any, Callable

from toolz import curry

import prefect
from prefect import Task, Flow


def setup_resource(resource):
    return resource.setup()


def cleanup_resource(resource, obj):
    return resource.cleanup(obj)


class Resource:
    def __init__(
        self,
        resource_class: Callable,
        name: str = None,
        init_task_kwargs: dict = None,
        setup_task_kwargs: dict = None,
        cleanup_task_kwargs: dict = None,
    ):
        self.resource_class = resource_class
        self.init_task_kwargs = (init_task_kwargs or {}).copy()
        self.setup_task_kwargs = (setup_task_kwargs or {}).copy()
        self.cleanup_task_kwargs = (cleanup_task_kwargs or {}).copy()

        if name is None:
            name = getattr(resource_class, "__name__", "Resource")
        self.name = name
        self.init_task_kwargs.setdefault("name", name)
        self.setup_task_kwargs.setdefault("name", f"{name}.setup")
        self.cleanup_task_kwargs.setdefault("name", f"{name}.cleanup")
        self.cleanup_task_kwargs.setdefault("trigger", prefect.triggers.always_run)
        self.cleanup_task_kwargs.setdefault("reference_task_candidate", False)

    def __call__(self, *args: Any, flow: Flow = None, **kwargs: Any):
        if flow is None:
            flow = prefect.context.get("flow")
            if flow is None:
                raise ValueError("Could not infer an active Flow context.")

        init_task = prefect.task(self.resource_class, **self.init_task_kwargs)(
            *args, flow=flow, **kwargs
        )

        setup_task = prefect.task(setup_resource, **self.setup_task_kwargs)(
            init_task, flow=flow
        )

        cleanup_task = prefect.task(cleanup_resource, **self.cleanup_task_kwargs)(
            init_task, setup_task, flow=flow
        )

        cleanup_task.set_upstream(setup_task, flow=flow)

        return ResourceInstance(init_task, setup_task, cleanup_task, flow)


class ResourceInstance:
    def __init__(
        self, init_task: Task, setup_task: Task, cleanup_task: Task, flow: Flow,
    ):
        self.init_task = init_task
        self.setup_task = setup_task
        self.cleanup_task = cleanup_task
        self._flow = flow
        self._tasks = set()

    def add_task(self, task: Task, flow: Flow) -> None:
        """Add a new task under the resource block.

        Args:
            - task (Task): the task to add
            - flow (Flow): the flow to use
        """
        if self._flow is not flow:
            raise ValueError(
                "Multiple flows cannot be used with the same resource block"
            )
        self._tasks.add(task)

    def __enter__(self):
        self.__prev_resource = prefect.context.get("resource")
        prefect.context.update(resource=self)
        return self.setup_task

    def __exit__(self, *args):
        if self.__prev_resource is None:
            prefect.context.pop("resource", None)
        else:
            prefect.context.update(resource=self.__prev_resource)

        if self._tasks:
            for child in self._tasks:
                # If a task has no upstream tasks created in this resource block,
                # the resource setup should be set as an upstream task.
                # Likewise, if a task has no downstream tasks created in this resource block,
                # the resource cleanup should be set as a downstream task.
                upstream = self._flow.upstream_tasks(child)
                if (
                    not self._tasks.intersection(upstream)
                    and self.setup_task not in upstream
                ):
                    child.set_upstream(self.setup_task, flow=self._flow)
                downstream = self._flow.downstream_tasks(child)
                if (
                    not self._tasks.intersection(downstream)
                    and self.cleanup_task not in downstream
                ):
                    child.set_downstream(self.cleanup_task, flow=self._flow)


@curry
def resource(
    resource_class: Callable,
    init_task_kwargs: dict = None,
    setup_task_kwargs: dict = None,
    cleanup_task_kwargs: dict = None,
) -> Resource:
    return Resource(
        resource_class,
        init_task_kwargs=init_task_kwargs,
        setup_task_kwargs=setup_task_kwargs,
        cleanup_task_kwargs=cleanup_task_kwargs,
    )
