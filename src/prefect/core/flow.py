import inspect

from functools import update_wrapper
from pydantic import validate_arguments
from typing import Any, Callable
from uuid import uuid4


class Flow:
    """
    Base class representing Prefect workflows.
    """

    # no docstring until we have a standard and the classes
    # are more polished
    def __init__(
        self,
        name: str,
        fn: Callable = None,
        version: str = None,
        executor=None,
        decsription: str = None,
    ):
        self.name = name

        if not fn:
            raise TypeError("__init__() missing 1 required argument: 'fn'")
        if not callable(fn):
            raise TypeError("'fn' must be callable")

        self.description = inspect.getdoc(fn)
        self.fn = validate_arguments(fn)
        update_wrapper(self, fn)
        self.version = version
        self.executor = executor

    def _run(self, *args, **kwargs):
        # placeholder method that will eventually manage state
        result = self.fn(*args, **kwargs)
        return result

    def __call__(self, *args, **kwargs):
        # this method will always retrieve a run ID from the backend
        result = self._run(*args, **kwargs)
        return result


def flow(name: str, fn: Callable = None, **flow_init_kwargs: Any):
    if fn is None:
        return lambda fn: Flow(fn=fn, name=name, **flow_init_kwargs)
    return Flow(fn=fn, name=name, **flow_init_kwargs)
