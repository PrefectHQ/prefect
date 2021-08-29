import inspect
from functools import update_wrapper
from typing import Any, Callable, Iterable

from prefect.executors import BaseExecutor, LocalExecutor
from prefect.futures import PrefectFuture
from prefect.orion.utilities.functions import parameter_schema
from prefect.utilities.asyncio import get_prefect_event_loop
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
        from prefect.engine import begin_flow_run

        if TaskRunContext.get():
            raise RuntimeError(
                "Flows cannot be called from within tasks. Did you mean to call this "
                "flow in a flow?"
            )

        flow_run_context = FlowRunContext.get()
        is_subflow_run = flow_run_context is not None
        parent_flow_run_id = flow_run_context.flow_run_id if is_subflow_run else None
        executor = flow_run_context.executor if is_subflow_run else self.executor

        # Convert the call args/kwargs to a parameter dict
        parameters = get_call_parameters(self.fn, args, kwargs)

        coro = begin_flow_run(
            flow=self,
            parameters=parameters,
            parent_flow_run_id=parent_flow_run_id,
            executor=executor,
        )

        if self.isasync:
            return coro
        else:
            # Create an event loop with the `parent_flow_run_id` as the key which
            # ensures that we have a new event loop _per_ level of flow run nesting
            # If flow calls are not nested, i.e. one flow calls several flows, they can
            # safely share an event loop.
            loop = get_prefect_event_loop(("flows", parent_flow_run_id))
            return loop.run_coro(coro)


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
