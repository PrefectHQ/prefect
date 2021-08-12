import inspect
from functools import update_wrapper
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterable, Tuple
from contextlib import nullcontext
from pydantic import validate_arguments

from prefect.client import OrionClient
from prefect.executors import BaseExecutor, SynchronousExecutor
from prefect.futures import PrefectFuture, resolve_futures
from prefect.orion.schemas.states import State, StateType
from prefect.orion.utilities.functions import parameter_schema
from prefect.utilities.hashing import file_hash

if TYPE_CHECKING:
    from prefect.context import FlowRunContext


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
        self.executor = executor or SynchronousExecutor()

        self.description = description or inspect.getdoc(fn)
        update_wrapper(self, fn)
        self.fn = fn

        # Version defaults to a hash of the function's file
        flow_file = fn.__globals__.get("__file__")  # type: ignore
        self.version = version or (file_hash(flow_file) if flow_file else None)

        self.parameters = parameter_schema(self.fn)

    def _run(
        self,
        context: "FlowRunContext",
        call_args: Tuple[Any, ...],
        call_kwargs: Dict[str, Any],
    ) -> State:
        """
        TODO: Note that pydantic will now coerce parameter types into the correct type
              even if the user wants failure on inexact type matches. We may want to
              implement a strict runtime typecheck with a configuration flag
        TODO: `validate_arguments` can throw an error while wrapping `fn` if the
              signature is not pydantic-compatible. We'll want to confirm that it will
              work at Flow.__init__ so we can raise errors to users immediately
        TODO: Implement state orchestation logic using return values from the API
        """
        context.client.set_flow_run_state(
            context.flow_run_id, State(type=StateType.RUNNING)
        )

        try:
            result = validate_arguments(self.fn)(*call_args, **call_kwargs)
        except Exception as exc:
            state = State(
                type=StateType.FAILED,
                message="Flow run encountered an exception.",
                data=exc,
            )
        else:
            state = State(
                type=StateType.COMPLETED,
                message="Flow run completed.",
                data=result,
            )

        return state

    def __call__(self, *args: Any, **kwargs: Any) -> PrefectFuture:
        from prefect.context import FlowRunContext, TaskRunContext
        from prefect.tasks import Task

        flow_run_context = FlowRunContext.get()
        is_nested_run = flow_run_context is not None
        parent_flow_run_id = flow_run_context.flow_run_id if is_nested_run else None
        executor = flow_run_context.executor if is_nested_run else self.executor

        if TaskRunContext.get():
            raise RuntimeError(
                "Flows cannot be called from within tasks. Did you mean to call this "
                "flow in a flow?"
            )

        # Generate dict of passed parameters
        parameters = inspect.signature(self.fn).bind_partial(*args, **kwargs).arguments

        client = OrionClient()

        # Generate a fake task as a placeholder if this is a subflow
        parent_task_run_id = (
            client.create_task_run(
                task=Task(name=self.name, fn=lambda _: ...),
                flow_run_id=parent_flow_run_id,
            )
            if is_nested_run
            else None
        )

        flow_run_id = client.create_flow_run(
            self, parameters=parameters, parent_task_run_id=parent_task_run_id
        )

        client.set_flow_run_state(flow_run_id, State(type=StateType.PENDING))

        executor_context = (
            executor.start(flow_run_id=flow_run_id, orion_client=client)
            # The executor is already started if this is a subflow
            if not is_nested_run
            else nullcontext()
        )

        with executor_context:
            with FlowRunContext(
                flow_run_id=flow_run_id,
                flow=self,
                client=client,
                executor=executor,
            ) as context:
                terminal_state = self._run(
                    context=context, call_args=args, call_kwargs=kwargs
                )

        if is_nested_run and terminal_state.is_completed():
            # Since a subflow does not wait for all of its futures before exiting, we
            # wait for any returned futures to complete before setting the final state
            # of the flow
            terminal_state.data = resolve_futures(terminal_state.data)

        # Update the flow to the terminal state
        client.set_flow_run_state(
            context.flow_run_id,
            state=terminal_state,
        )

        # Return a fake future that is already resolved to `state`
        return PrefectFuture(
            flow_run_id=flow_run_id,
            client=client,
            executor=executor,
            _result=terminal_state,
        )


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
