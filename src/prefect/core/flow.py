import inspect

from functools import update_wrapper
from pydantic import validate_arguments
from typing import Any, Callable, Iterable, Awaitable, Union


from prefect.core.utilities import file_hash, sync
from prefect.core.orion.flow_runs import create_flow_run
from prefect.core.futures import PrefectFuture

from prefect.orion.utilities.functions import parameter_schema, ParameterSchema


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
        description: str = None,
        tags: Iterable[str] = None,
    ):
        if not fn:
            raise TypeError("__init__() missing 1 required argument: 'fn'")
        if not callable(fn):
            raise TypeError("'fn' must be callable")

        self.name = name or fn.__name__

        self.description = description or inspect.getdoc(fn)
        update_wrapper(self, fn)
        self.fn = fn

        # Version defaults to a hash of the function's file
        flow_file = fn.__globals__.get("__file__")  # type: ignore
        self.version = version or (file_hash(flow_file) if flow_file else None)
        self.executor = executor

        self.tags = set(tags if tags else [])

        # Generate a parameter schema from the function
        self.parameters = parameter_schema(self.fn)

    async def _run(self, *args, **kwargs):
        # TODO: Manage state
        # TODO: Note that pydantic will now coerce parameter types into the correct type
        #       even if the user wants failure on inexact type matches. We may want to
        #       implement a strict runtime typecheck with a configuration flag
        # TODO: `validate_arguments` can throw an error while wrapping `fn` if the
        #       signature is not pydantic-compatible. We'll want to confirm that it will
        #       work at Flow.__init__ so we can raise errors to users immediately
        call_result = validate_arguments(self.fn)(*args, **kwargs)
        if inspect.isawaitable(call_result):
            return await call_result
        return call_result

    async def _call_async(self, args, kwargs) -> PrefectFuture:
        parameters = inspect.signature(self.fn).bind_partial(*args, **kwargs).arguments
        flow_run_id = await create_flow_run(self, parameters=parameters)
        result = await self._run(*args, **kwargs)
        return PrefectFuture(run_id=flow_run_id, result=result)

    def __call__(
        self, *args, **kwargs
    ) -> Union[PrefectFuture, Awaitable[PrefectFuture]]:
        if inspect.iscoroutinefunction(self.fn):
            return self._call_async(args, kwargs)
        else:
            return sync(self._call_async)(args, kwargs)


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
