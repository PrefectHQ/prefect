import functools
import types
import uuid
import weakref
from typing import Callable, Any

from toolz import curry

from prefect.core.task import Task
from prefect.engine.result import Result


__all__ = ("resource",)


RESOURCES = weakref.WeakValueDictionary()


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
        return self

    def __reduce__(self):
        return (ResourceHandle, (self.key, self.func, self.args, self.kwargs))

    def __del__(self):
        self.reset()

    def get(self):
        if not hasattr(self, "value"):
            result = self.func(*self.args, **self.kwargs)
            if isinstance(result, types.GeneratorType):
                self.generator = result
                self.value = next(self.generator)
            else:
                self.value = result
        return self.value

    def reset(self):
        if hasattr(self, "value"):
            del self.value
            if self.generator is not None:
                try:
                    next(self.generator)
                except StopIteration:
                    pass
                del self.generator


class ResourceResult(Result):
    def __init__(self, **kwargs):
        if "serializer" in kwargs:
            raise ValueError("Can't pass a serializer to a ResourceResult.")
        self.handle = None
        super().__init__(**kwargs)

    def read(self, location: str) -> Result:
        return self.copy()

    @property
    def value(self):
        if self.handle is None:
            raise ValueError("No value found for this result")
        return self.handle.get()

    @value.setter
    def value(self, val):
        pass

    def from_value(self, value: Any) -> "Result":
        new = self.copy()
        new.location = None
        new.handle = value
        return new

    def write(self, value: Any, **kwargs: Any) -> Result:
        raise ValueError("ResourceResult cannot be written to.")


class Resource(Task):
    def __init__(self, resource_function: Callable, **kwargs: Any):
        @functools.wraps(resource_function)
        def run(*args, **kwargs):
            return ResourceHandle(uuid.uuid4().hex, resource_function, args, kwargs)

        self.run = run
        super().__init__(result=ResourceResult(), **kwargs)


@curry
def resource(fn: Callable, **task_init_kwargs: Any) -> Resource:
    return Resource(fn, **task_init_kwargs)
