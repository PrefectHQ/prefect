import functools
import inspect
import logging
import threading
import types
import uuid
import weakref
from typing import Callable, Any

from toolz import curry

import prefect
from prefect.core.task import Task


__all__ = ("Resource", "resource")


# A weak dictionary of all resources created in this process. They're keyed by
# their uuid. The purpose of this is to ensure that serializing the same
# `ResourceHandle` object twice to the same process results in only one
# instance created. This is not a thread local, since we want only one instance
# of the resource per *process*, not per thread.
_RESOURCES = weakref.WeakValueDictionary()

# A threadlocal to hold the current active resource pool. This is local to the
# `FlowRunner` thread only, and is only used to ensure that any
# `ResourceHandle` objects in the result state are cleared before returning
# from `FlowRunner.run`. We don't store this in the `context`, since we don't want to
# serialize it to other worker processes.
_RESOURCE_POOL = threading.local()


class ResourceHandle:
    """A handle on a created resource.

    A `ResourceHandle` is an internal proxy object that holds or recreates the
    actual resource value. When serialized, the resource value will not be
    serialized - instead it will be recreated on the other end.
    """

    def __new__(
        cls,
        func: Callable,
        func_args: tuple = None,
        func_kwargs: dict = None,
        name: str = None,
        logger: logging.Logger = None,
        key: str = None,
    ) -> "ResourceHandle":
        if func_args is None:
            func_args = ()
        if func_kwargs is None:
            func_kwargs = {}
        if key is None:
            key = uuid.uuid4().hex

        self = _RESOURCES.get(key)
        if self is not None:
            return self

        self = _RESOURCES[key] = object.__new__(cls)
        self.key = key
        self.func = func
        self.args = func_args
        self.kwargs = func_kwargs
        self._generator = None
        self.name = name
        self.logger = logger

        pool = getattr(_RESOURCE_POOL, "current", None)
        if pool is not None:
            pool.add(self)

        return self

    def __del__(self):
        self.clear()

    def __reduce__(self):
        return (
            ResourceHandle,
            (self.func, self.args, self.kwargs, self.name, self.logger, self.key),
        )

    def get(self) -> Any:
        """Get or recreate the wrapped resource"""
        if self.func is None:
            raise ValueError(
                "Cannot access value of `Resource` tasks outside of a flow run"
            )
        elif not hasattr(self, "_value"):
            result = self.func(*self.args, **self.kwargs)
            if isinstance(result, types.GeneratorType):
                self._generator = result
                self._value = next(self._generator)
            else:
                self._value = result
        return self._value

    def clear(self) -> None:
        """Clear all state on the `ResourceHandle`.

        If the resource was already created, this cleans up the resource, then
        drops all additional state used for recreating it.
        """
        if hasattr(self, "_value"):
            del self._value
            if self._generator is not None:
                try:
                    next(self._generator)
                except StopIteration:
                    pass
                except Exception as exc:
                    if self.logger is not None:
                        self.logger.warning(
                            "Error during cleanup of resource {}",
                            self.name,
                            exc_info=exc,
                        )
        self.func = None
        self.args = None
        self.kwargs = None
        self._generator = None


class ResourcePool:
    """A pool of `ResourceHandle` objects.

    This holds references to resource objects created during a flow run. The
    purpose of this is to ensure that before `FlowRunner.run` returns, all
    created `ResourceHandle` objects have been cleared in the _flow runner_
    process. This ensures that resources don't end up attached to the end
    result `State` object. Resources created in other processes (say due to
    pickling and sending to a dask worker) are cleaned up by their `__del__`
    method - the resource pool only applies to the flow runner process.
    """

    def __init__(self):
        self.resources = weakref.WeakSet()

    def add(self, handle: ResourceHandle) -> None:
        """Add a `ResourceHandle` to the pool"""
        self.resources.add(handle)

    def __enter__(self) -> None:
        self.__prev_pool = getattr(_RESOURCE_POOL, "current", None)
        _RESOURCE_POOL.current = self
        return self

    def __exit__(self, *args) -> None:
        for r in self.resources:
            r.clear()
        _RESOURCE_POOL.current = self.__prev_pool


class Resource(Task):
    """
    A `Resource` is a task whose result represents some resource to be used by
    other tasks (e.g., a database connection, an S3 client, etc...).

    The result of a resource task is _never_ serialized been `Executor`
    processes - if needed in a different process the resource will be recreated
    in that process instead of serialized. As such, the resource task may be
    run multiple times during the course of a flow run.

    Args:
        - fn (Callable): the wrapped function. May either `return` the
            resource, or `yield` it. If `yield` is used, the code block after
            yield statement will be run as a cleanup step when the resource is
            no longer (only one `yield` statement is permitted).
        - **kwargs (Any): additional keyword arguments that will be passed to
            the `Task` constructor on initialization.
    """

    def __init__(self, fn: Callable, **kwargs: Any):
        from prefect.engine.results import ResourceResult

        @functools.wraps(fn)
        def run(*args, **kwargs):
            name = prefect.context.get("task_full_name")
            logger = prefect.context.get("logger")
            return ResourceHandle(fn, args, kwargs, name=name, logger=logger)

        # Fix the return type in the `run` signature
        sig = inspect.Signature.from_callable(fn)
        run.__signature__ = sig.replace(return_annotation=ResourceHandle)

        kwargs.setdefault("name", getattr(fn, "__name__", type(self).__name__))

        self.run = run
        super().__init__(result=ResourceResult(), **kwargs)


@curry
def resource(fn: Callable, **task_init_kwargs: Any) -> Resource:
    """
    A decorator for creating resource tasks from functions.

    A `Resource` is a task whose result represents some resource to be used by
    other tasks (e.g., a database connection, an S3 client, etc...). The result
    of a resource task is _never_ serialized been `Executor` processes - if
    needed in a different process the resource will be recreated in that
    process instead of serialized. As such, the resource task may be run
    multiple times during the course of a flow run.

    Resources can optionally define a cleanup action to be run when they are no
    longer needed. Cleanup is done on a best-effort basis, and shouldn't be
    relied on for things where failure to cleanup must be dealt with. If a
    resource fails to cleanup the failure will be logged, but the resource task
    will still be marked as successful.

    Args:
        - fn (Callable): the decorated function. May either `return` the
            resource, or `yield` it. If `yield` is used, the code block after
            yield statement will be run as a cleanup step when the resource is
            no longer (only one `yield` statement is permitted).
        - **task_init_kwargs (Any): keyword arguments that will be passed to the `Task`
            constructor on initialization.

    Returns:
        - Resource: the created Resource task

    Raises:
        - ValueError: if the provided function violates signature requirements
            for Task run methods

    Example:

    If a resource doesn't need to be cleaned up after completion, you can wrap
    a function that creates and returns the resource, just like you would with
    the `task` decorator.

    ```
    @resource(name='my-client')
    def my_client(password):
        return MyClient(password)

    with Flow("My Flow") as flow:
        password = PrefectSecret("password")
        client = my_client(password)

        # use the client in downstream tasks
        some_task(client)
        some_other_task(client)
    ```

    If the resource does need to be explicitly cleaned up after use (e.g. close
    the connection), you can `yield` the result instead of `return` it - once
    the resource is no longer needed, the code block after the yield will be
    run to clean the resource up. A wrapped function may only yield once.

    ```
    @resource(name='my-client')
    def my_client(password):
        # Code before the `yield` runs to setup the resource
        client = MyClient(password)

        yield client

        # Code after the `yield` runs to cleanup the resource
        client.close()
    ```
    """
    return Resource(fn, **task_init_kwargs)
