from typing import Any, Callable

from toolz import curry

import prefect
from prefect import Task, Flow


__all__ = ("resource_manager", "ResourceManager")


def setup_resource(mgr):
    return mgr.setup()


def cleanup_resource(mgr, resource):
    return mgr.cleanup(resource)


class ResourceContext:
    """A context managed by a `ResourceManager`.

    These objects usually are created by calling a `ResourceManager` object,
    not manually. See the docstrings for `ResourceManager` or
    `resource_manager` for more information.
    """

    def __init__(
        self, init_task: Task, setup_task: Task, cleanup_task: Task, flow: Flow,
    ):
        self.init_task = init_task
        self.setup_task = setup_task
        self.cleanup_task = cleanup_task
        self._flow = flow
        self._tasks = set()

    def add_task(self, task: Task, flow: Flow) -> None:
        """Add a new task under the resource manager block.

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


class ResourceManager:
    """An object for managing temporary resources.

    ResourceManager objects are used for creating tasks using temporary objects that
    need to cleaned up after usage. Examples might include temporary Dask/Spark
    clusters, Docker containers, etc...

    Args:
        - resource_class (Callable): A callable (usually the class itself) for
            creating an object that follows the `ResourceManager` protocol.
        - name (str, optional): The resource name - defaults to the name of the
            decorated class.
        - init_task_kwargs (dict, optional): keyword arguments that will be
            passed to the `Task` constructor for the `init` task.
        - setup_task_kwargs (dict, optional): keyword arguments that will be
            passed to the `Task` constructor for the `setup` task.
        - cleanup_task_kwargs (dict, optional): keyword arguments that will be
            passed to the `Task` constructor for the `cleanup` task.
    """

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
            name = getattr(resource_class, "__name__", "resource")
        self.name = name
        self.init_task_kwargs.setdefault("name", name)
        self.setup_task_kwargs.setdefault("name", f"{name}.setup")
        self.cleanup_task_kwargs.setdefault("name", f"{name}.cleanup")
        self.cleanup_task_kwargs.setdefault("trigger", prefect.triggers.always_run)
        self.cleanup_task_kwargs.setdefault("reference_task_candidate", False)

    def __call__(self, *args: Any, flow: Flow = None, **kwargs: Any) -> ResourceContext:
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

        return ResourceContext(init_task, setup_task, cleanup_task, flow)


@curry
def resource_manager(
    resource_class: Callable,
    name: str = None,
    init_task_kwargs: dict = None,
    setup_task_kwargs: dict = None,
    cleanup_task_kwargs: dict = None,
) -> ResourceManager:
    """A decorator for creating a `ResourceManager` object.

    ResourceManager objects are used for creating tasks using temporary objects that
    need to cleaned up after usage. Examples might include temporary Dask/Spark
    clusters, Docker containers, etc...

    Through usage a ResourceManager object adds three tasks to the graph:
        - A `init` task, which returns an object that meets the `ResourceManager`
          protocol. This protocol requires two methods:
            * `setup(self) -> resource`: A method for creating the resource.
                The return value from this will available to user tasks.
            * `cleanup(self, resource) -> None`: A method for cleaning up the
                resource.  This takes the return value from `setup` and
                shouldn't return anything.
        - A `setup` task, which calls the `setup` method on the `ResourceManager`
        - A `cleanup` task, which calls the `cleanup` method on the `ResourceManager`.

    Args:
        - resource_class (Callable): The decorated class.
        - name (str, optional): The resource name - defaults to the name of the
            decorated class.
        - init_task_kwargs (dict, optional): keyword arguments that will be
            passed to the `Task` constructor for the `init` task.
        - setup_task_kwargs (dict, optional): keyword arguments that will be
            passed to the `Task` constructor for the `setup` task.
        - cleanup_task_kwargs (dict, optional): keyword arguments that will be
            passed to the `Task` constructor for the `cleanup` task.

    Returns:
        - ResourceManager: the created `ResourceManager` object.

    Example:

    Here's an example resource manager for creating a local temporary local
    dask cluster as part of the flow.

    ```
    from prefect import resource_manager
    from dask.distributed import Client

    @resource_manager
    class DaskCluster:
        def __init__(self, n_workers):
            self.n_workers = n_workers

        def setup(self):
            "Create a local dask cluster"
            return Client(n_workers=self.n_workers)

        def cleanup(self, client):
            "Cleanup the local dask cluster"
            client.close()
    ```

    To use the `DaskCluster` resource manager as part of your Flow, you can use
    `DaskCluster` as a context manager:

    ```
    with Flow("example") as flow:
        n_workers = Parameter("n_workers")

        with DaskCluster(n_workers=n_workers) as client:
            some_task(client)
            some_other_task(client)
    ```

    The `Task` returned by entering the `DaskCluster` context (i.e. the
    `client` part of  `as client`) is the output of the `setup` method on the
    `ResourceManager` class. A `Task` is automatically added to call the
    `cleanup` method (closing the Dask cluster) after all tasks under the
    context have completed. By default this `cleanup` task is configured with
    an `always_run` trigger, and won't be set as a reference task.
    """
    return ResourceManager(
        resource_class,
        init_task_kwargs=init_task_kwargs,
        setup_task_kwargs=setup_task_kwargs,
        cleanup_task_kwargs=cleanup_task_kwargs,
    )
