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
        name: str = None,
        fn: Callable = None,
        version: str = None,
        executor=None,
        decsription: str = None,
    ):
        if not fn:
            raise TypeError("__init__() missing 1 required argument: 'fn'")
        if not callable(fn):
            raise TypeError("'fn' must be callable")

        self.name = name or fn.__name__

        self.description = decsription or inspect.getdoc(fn)

        # TODO: Note that pydantic will now coerce parameter types into the correct type
        #       even if the user wants failure on inexact type matches. We may want to
        #       implement a strict runtime typecheck with a configuration flag
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


def flow(_fn: Callable = None, *, name: str = None, **flow_init_kwargs: Any):
    # TOOD: Using `**flow_init_kwargs` here hides possible settings from the user
    #       and it may be worth enumerating possible arguments explicitly for user
    #       friendlyness
    # TODO: For mypy type checks, @overload will have to be used to clarify return
    #       types for @flow and @flow(...)
    #       https://mypy.readthedocs.io/en/stable/generics.html?highlight=decorator#decorator-factories
    if _fn is None:
        return lambda _fn: Flow(fn=_fn, name=name, **flow_init_kwargs)
    return Flow(fn=_fn, name=name, **flow_init_kwargs)
