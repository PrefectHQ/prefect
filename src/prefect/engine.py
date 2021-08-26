"""
Client-side execution of flows and tasks
"""
from contextlib import nullcontext
from typing import Any, Dict, Optional, Tuple, Callable
from uuid import UUID

from pydantic import validate_arguments

from prefect.client import OrionClient
from prefect.futures import PrefectFuture, resolve_futures, return_val_to_state
from prefect.orion.schemas.states import State, StateType
from prefect.utilities.callables import get_call_parameters
from prefect.context import FlowRunContext, TaskRunContext
from prefect.tasks import Task


async def run_flow(flow, *args, **kwargs):
    flow_run_context = FlowRunContext.get()
    is_subflow_run = flow_run_context is not None
    parent_flow_run_id = flow_run_context.flow_run_id if is_subflow_run else None
    executor = flow_run_context.executor if is_subflow_run else flow.executor

    if TaskRunContext.get():
        raise RuntimeError(
            "Flows cannot be called from within tasks. Did you mean to call this "
            "flow in a flow?"
        )

    # Generate dict of passed parameters
    parameters = get_call_parameters(flow.fn, args, kwargs)

    client = OrionClient()

    parent_task_run_id: Optional[UUID] = None
    if is_subflow_run:
        # Generate a task in the parent flow run to represent the result of the subflow run
        parent_task_run_id = client.create_task_run(
            task=Task(name=flow.name, fn=lambda _: ...),
            flow_run_id=parent_flow_run_id,
        )

    flow_run_id = client.create_flow_run(
        flow,
        parameters=parameters,
        parent_task_run_id=parent_task_run_id,
        state=State(type=StateType.PENDING),
    )

    executor_context = (
        executor.start(flow_run_id=flow_run_id, orion_client=client)
        # The executor is already started if this is a subflow run
        if not is_subflow_run
        else nullcontext()
    )

    with executor_context:
        with FlowRunContext(
            flow_run_id=flow_run_id,
            flow=flow,
            client=client,
            executor=executor,
        ) as context:
            terminal_state = await orchestrate_flow_function(
                flow.fn, context=context, call_args=args, call_kwargs=kwargs
            )

    if is_subflow_run and terminal_state.is_completed():
        # Since a subflow run does not wait for all of its futures before exiting, we
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


async def orchestrate_flow_function(
    flow_fn: Callable,
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
        result = validate_arguments(flow_fn)(*call_args, **call_kwargs)
    except Exception as exc:
        state = State(
            type=StateType.FAILED,
            message="Flow run encountered an exception.",
            data=exc,
        )
    else:
        state = return_val_to_state(result)

    return state
