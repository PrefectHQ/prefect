import inspect
from functools import update_wrapper
from typing import Any, Callable, Iterable

from anyio import start_blocking_portal

from prefect.executors import BaseExecutor, LocalExecutor
from prefect.futures import PrefectFuture
from prefect.orion.utilities.functions import parameter_schema
from prefect.utilities.hashing import file_hash
from prefect.utilities.callables import get_call_parameters
from prefect.utilities.hashing import file_hash


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
        executor: BaseExecutor = None,
        description: str = None,
        tags: Iterable[str] = None,
    ):
        if not fn:
            raise TypeError("__init__() missing 1 required argument: 'fn'")
        if not callable(fn):
            raise TypeError("'fn' must be callable")

        self.name = name or fn.__name__

        self.tags = set(tags if tags else [])
        self.executor = executor or LocalExecutor()

        self.description = description or inspect.getdoc(fn)
        update_wrapper(self, fn)
        self.fn = fn
        self.isasync = inspect.iscoroutinefunction(self.fn)

        # Version defaults to a hash of the function's file
        flow_file = fn.__globals__.get("__file__")  # type: ignore
        self.version = version or (file_hash(flow_file) if flow_file else None)

        self.parameters = parameter_schema(self.fn)

    def __call__(self, *args: Any, **kwargs: Any) -> PrefectFuture:
        from prefect.context import FlowRunContext, TaskRunContext
        from prefect.engine import begin_flow_run, begin_subflow_run

        if TaskRunContext.get():
            raise RuntimeError(
                "Flows cannot be called from within tasks. Did you mean to call this "
                "flow in a flow?"
            )

        is_subflow_run = FlowRunContext.get() is not None

        # Convert the call args/kwargs to a parameter dict
        parameters = get_call_parameters(self.fn, args, kwargs)

        begin_fn = begin_subflow_run if is_subflow_run else begin_flow_run
        begin_coro = begin_fn(self, parameters)

        if self.isasync:
            return begin_coro
        else:
            with start_blocking_portal() as portal:
                return portal.call(lambda: begin_coro)


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
