import functools
import types
import uuid
import weakref
from typing import Callable, Any

from toolz import curry

import prefect
from prefect.core.task import Task


__all__ = ("resource",)


RESOURCES = weakref.WeakValueDictionary()


class ResourcePool:
    def __init__(self):
        self.resources = weakref.WeakSet()

    def add(self, handle):
        self.resources.add(handle)

    def __enter__(self):
        self.__prev_pool = prefect.context.get("resource_pool")
        prefect.context.update(resource_pool=self)

    def __exit__(self, *args):
        for r in self.resources:
            r.clear()
        if self.__prev_pool is None:
            prefect.context.pop("resource_pool", None)
        else:
            prefect.context.update(resource_pool=self.__prev_pool)


class ResourceHandle:
    def __new__(cls, key, func, func_args, func_kwargs):
        self = RESOURCES.get(key)
        if self is not None:
            return self

        self = RESOURCES[key] = object.__new__(cls)
        self.key = key
        self.func = func
        self.args = func_args
        self.kwargs = func_kwargs
        self.generator = None

        pool = prefect.context.get("resource_pool")
        if pool is not None:
            pool.add(self)

        return self

    def __reduce__(self):
        return (ResourceHandle, (self.key, self.func, self.args, self.kwargs))

    def __del__(self):
        self.drop()

    def get(self):
        if self.func is None:
            raise ValueError(
                "Cannot access value of `Resource` tasks outside of a flow run"
            )
        elif not hasattr(self, "value"):
            result = self.func(*self.args, **self.kwargs)
            if isinstance(result, types.GeneratorType):
                self.generator = result
                self.value = next(self.generator)
            else:
                self.value = result
        return self.value

    def drop(self):
        if hasattr(self, "value"):
            del self.value
            if self.generator is not None:
                try:
                    next(self.generator)
                except StopIteration:
                    pass
                del self.generator

    def clear(self):
        self.drop()
        self.args = None
        self.kwargs = None
        self.func = None


class Resource(Task):
    def __init__(self, resource_function: Callable, **kwargs: Any):
        from prefect.engine.results import ResourceResult

        @functools.wraps(resource_function)
        def run(*args, **kwargs):
            return ResourceHandle(uuid.uuid4().hex, resource_function, args, kwargs)

        self.run = run
        super().__init__(result=ResourceResult(), **kwargs)


@curry
def resource(fn: Callable, **task_init_kwargs: Any) -> Resource:
    return Resource(fn, **task_init_kwargs)
