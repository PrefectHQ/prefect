"""
Client-side execution of flows and tasks
"""
from contextlib import contextmanager, nullcontext
from functools import partial
from typing import Any, Awaitable, Dict, TypeVar, Union, overload, Set
from uuid import UUID

import pendulum
import logging
import anyio
from anyio import start_blocking_portal
from anyio.abc import BlockingPortal
from anyio.from_thread import BlockingPortal

from prefect.client import OrionClient, inject_client
from prefect.context import FlowRunContext, TaskRunContext, TagsContext
from prefect.deployments import load_flow_from_deployment
from prefect.executors import BaseExecutor
from prefect.flows import Flow
from prefect.futures import PrefectFuture, future_to_state, resolve_futures
from prefect.orion.schemas.data import DataDocument
from prefect.orion.schemas.states import (
    Completed,
    Failed,
    Pending,
    Running,
    State,
    StateDetails,
    StateType,
)
from prefect.orion.states import StateSet, is_state, is_state_iterable
from prefect.tasks import Task
from prefect.utilities.asyncio import (
    run_async_from_worker_thread,
    run_sync_in_worker_thread,
    sync_compatible,
)
from prefect.utilities.callables import (
    call_with_parameters,
    parameters_to_args_kwargs,
)
from prefect.utilities.collections import ensure_iterable
from prefect.serializers import resolve_datadoc
from prefect.utilities.logging import get_logger, call_repr, prefect_repr

R = TypeVar("R")


logger = get_logger("engine")


def enter_flow_run_engine_from_flow_call(
    flow: Flow, parameters: Dict[str, Any]
) -> Union[State, Awaitable[State]]:
    """
    Sync entrypoint for flow calls

    This function does the heavy lifting of ensuring we can get into an async context
    for flow run execution with minimal overhead.
    """
    if TaskRunContext.get():
        raise RuntimeError(
            "Flows cannot be called from within tasks. Did you mean to call this "
            "flow in a flow?"
        )

    parent_flow_run_context = FlowRunContext.get()
    is_subflow_run = parent_flow_run_context is not None

    begin_run = partial(
        create_and_begin_subflow_run if is_subflow_run else create_then_begin_flow_run,
        flow=flow,
        parameters=parameters,
    )

    # Async flow run
    if flow.isasync:
        return begin_run()  # Return a coroutine for the user to await

    # Sync flow run
    if not is_subflow_run:
        with start_blocking_portal() as portal:
            return portal.call(begin_run)

    # Sync subflow run
    if not parent_flow_run_context.flow.isasync:
        return run_async_from_worker_thread(begin_run)
    else:
        return parent_flow_run_context.sync_portal.call(begin_run)


def enter_flow_run_engine_from_deployed_run(flow_run_id: UUID) -> State:
    """
    Sync entrypoint for flow runs that have been submitted for execution by an agent

    Differs from `enter_flow_run_engine_from_flow_call` in that we have a flow run id
    but not a flow object. The flow must be retrieved before execution can begin.
    Additionally, this assumes that the caller is always in a context without an event
    loop as this should be called from a fresh process.
    """
    return anyio.run(retrieve_flow_then_begin_flow_run, flow_run_id)


@inject_client
async def create_then_begin_flow_run(
    flow: Flow, parameters: Dict[str, Any], client: OrionClient
) -> State:
    """
    Async entrypoint for flow calls

    Creates the flow run in the backend then enters the main flow rum engine
    """
    logger.info(f"Creating run for flow {flow.name!r}...")
    flow_run_id = await client.create_flow_run(
        flow,
        parameters=parameters,
        state=Pending(),
        tags=TagsContext.get().current_tags,
    )
    return await begin_flow_run(
        flow=flow, parameters=parameters, flow_run_id=flow_run_id, client=client
    )


@inject_client
async def retrieve_flow_then_begin_flow_run(
    flow_run_id: UUID, client: OrionClient
) -> State:
    """
    Async entrypoint for flow runs that have been submitted for execution by an agent

    - Retrieves the deployment information
    - Loads the flow object using deployment information
    - Updates the flow run version
    """
    flow_run = await client.read_flow_run(flow_run_id)
    deployment = await client.read_deployment(flow_run.deployment_id)
    flow = await load_flow_from_deployment(deployment, client=client)

    await client.update_flow_run(
        flow_run_id=flow_run_id,
        flow_version=flow.version,
        parameters=flow_run.parameters,
    )
    await client.propose_state(Pending(), flow_run_id=flow_run_id)

    return await begin_flow_run(
        flow=flow,
        parameters=flow_run.parameters,
        flow_run_id=flow_run_id,
        client=client,
    )


async def begin_flow_run(
    flow_run_id: UUID,
    flow: Flow,
    parameters: Dict[str, Any],
    client: OrionClient,
) -> State:
    """
    Begins execution of a flow run; blocks until completion of the flow run

    - Starts an executor
    - Orchestrates the flow run (runs the user-function and generates tasks)
    - Waits for tasks to complete / shutsdown the executor
    - Sets a terminal state for the flow run

    Returns the terminal state
    """
    logger.info(f"Beginning flow run for flow {flow.name!r}...")
    # If the flow is async, we need to provide a portal so sync tasks can run
    portal_context = start_blocking_portal() if flow.isasync else nullcontext()

    with flow.executor.start(flow_run_id=flow_run_id, orion_client=client) as executor:
        with portal_context as sync_portal:
            terminal_state = await orchestrate_flow_run(
                flow,
                flow_run_id=flow_run_id,
                parameters=parameters,
                executor=executor,
                client=client,
                sync_portal=sync_portal,
            )

    # Update the flow to the terminal state _after_ the executor has shut down
    await client.propose_state(
        state=terminal_state,
        flow_run_id=flow_run_id,
    )

    logger.log(
        level=logging.INFO if terminal_state.is_completed() else logging.ERROR,
        msg=f"Flow run finished with state {prefect_repr(terminal_state)}",
    )

    return terminal_state


@inject_client
async def create_and_begin_subflow_run(
    flow: Flow,
    parameters: Dict[str, Any],
    client: OrionClient,
) -> State:
    """
    Async entrypoint for flows calls within a flow run

    Subflows differ from parent flows in that they
    - Use the existing parent flow executor
    - Resolve futures in passed parameters into values
    - Create a dummy task for representation in the parent flow

    Returns the terminal state
    """
    parent_flow_run_context = FlowRunContext.get()

    args, kwargs = parameters_to_args_kwargs(flow.fn, parameters)
    logger.info(
        f"Beginning subflow run for flow {flow.name!r} within {parent_flow_run_context.flow.name!r} with graph {call_repr(flow.fn, *args, **kwargs)}..."
    )

    # Generate a task in the parent flow run to represent the result of the subflow run
    parent_task_run_id = await client.create_task_run(
        task=Task(name=flow.name, fn=lambda _: ...),
        flow_run_id=parent_flow_run_context.flow_run_id,
    )

    # Resolve any task futures in the input
    parameters = await resolve_futures(parameters)

    flow_run_id = await client.create_flow_run(
        flow,
        parameters=parameters,
        parent_task_run_id=parent_task_run_id,
        state=Pending(),
        tags=TagsContext.get().current_tags,
    )

    terminal_state = await orchestrate_flow_run(
        flow,
        flow_run_id=flow_run_id,
        parameters=parameters,
        executor=parent_flow_run_context.executor,
        client=client,
        sync_portal=parent_flow_run_context.sync_portal,
    )

    if terminal_state.is_completed():
        # Since a subflow run does not wait for all of its futures before exiting, we
        # wait for any returned futures to complete before setting the final state
        # of the flow
        terminal_state.data = await resolve_futures(terminal_state.data)

    # Update the flow to the terminal state _after_ the executor has shut down
    await client.propose_state(
        state=terminal_state,
        flow_run_id=flow_run_id,
    )

    logger.log(
        level=logging.INFO if terminal_state.is_completed() else logging.ERROR,
        msg=f"Subflow run finished with state {prefect_repr(terminal_state)}",
    )

    return terminal_state


@inject_client
async def orchestrate_flow_run(
    flow: Flow,
    flow_run_id: UUID,
    parameters: Dict[str, Any],
    executor: BaseExecutor,
    client: OrionClient,
    sync_portal: BlockingPortal,
) -> State:
    """
    TODO: Implement state orchestation logic using return values from the API
    """
    await client.propose_state(Running(), flow_run_id=flow_run_id)

    try:
        with FlowRunContext(
            flow_run_id=flow_run_id,
            flow=flow,
            client=client,
            executor=executor,
            sync_portal=sync_portal,
        ):
            # Validate the parameters before the call; raises an exception if invalid
            if flow.should_validate_parameters:
                parameters = flow.validate_parameters(parameters)

            args, kwargs = parameters_to_args_kwargs(flow.fn, parameters)
            logger.info(
                f"Executing flow {flow.name!r} with call {call_repr(flow.fn, *args, **kwargs)}..."
            )
            flow_call = partial(flow.fn, *args, **kwargs)
            if flow.isasync:
                result = await flow_call()
            else:
                result = await run_sync_in_worker_thread(flow_call)

    except Exception as exc:
        state = Failed(
            message="Flow run encountered an exception.",
            data=DataDocument.encode("cloudpickle", exc),
        )
    else:
        state = await user_return_value_to_state(result, serializer="cloudpickle")

    return state


def enter_task_run_engine(
    task: Task, parameters: Dict[str, Any]
) -> Union[PrefectFuture, Awaitable[PrefectFuture]]:
    flow_run_context = FlowRunContext.get()
    if not flow_run_context:
        raise RuntimeError("Tasks cannot be called outside of a flow.")

    if TaskRunContext.get():
        raise RuntimeError(
            "Tasks cannot be called from within tasks. Did you mean to call this "
            "task in a flow?"
        )

    # Provide a helpful error if there is a async task in a sync flow; this would not
    # error normally since it would just be an unawaited coroutine
    if task.isasync and not flow_run_context.flow.isasync:
        raise RuntimeError(
            f"Your task is async, but your flow is synchronous. Async tasks may "
            "only be called from async flows."
        )

    begin_run = partial(
        begin_task_run,
        task=task,
        flow_run_context=flow_run_context,
        parameters=parameters,
    )

    # Async task run
    if task.isasync:
        return begin_run()  # Return a coroutine for the user to await

    # Sync task run in sync flow run
    if not flow_run_context.flow.isasync:
        return run_async_from_worker_thread(begin_run)

    # Sync task run in async flow run
    else:
        # Call out to the sync portal since we are not in a worker thread
        return flow_run_context.sync_portal.call(begin_run)


async def begin_task_run(
    task: Task, flow_run_context: FlowRunContext, parameters: Dict[str, Any]
) -> PrefectFuture:
    """
    Async entrypoint for task calls

    Tasks must be called within a flow. When tasks are called, they create a task run
    and submit orchestration of the run to the flow run's executor. The executor returns
    a future that is returned immediately.
    """
    task_run_name = f"{task.name}-{task.dynamic_key}"
    task_run_id = await flow_run_context.client.create_task_run(
        task=task,
        flow_run_id=flow_run_context.flow_run_id,
        state=Pending(),
        extra_tags=TagsContext.get().current_tags,
    )

    args, kwargs = parameters_to_args_kwargs(task.fn, parameters)
    task_call_repr = call_repr(task.fn, *args, **kwargs)
    logger.info(
        f"Submitting task run {task_run_name!r} to executor with graph {task_call_repr}..."
    )

    future = await flow_run_context.executor.submit(
        task_run_id,
        task_call_repr,
        orchestrate_task_run,
        task=task,
        task_run_id=task_run_id,
        flow_run_id=flow_run_context.flow_run_id,
        parameters=parameters,
        task_run_name=task_run_name,
    )

    # Update the dynamic key so future task calls are distinguishable from this task run
    task.update_dynamic_key()

    return future


@inject_client
async def orchestrate_task_run(
    task: Task,
    task_run_id: UUID,
    flow_run_id: UUID,
    parameters: Dict[str, Any],
    task_run_name: str,
    client: OrionClient,
) -> State:
    context = TaskRunContext(
        task_run_id=task_run_id,
        flow_run_id=flow_run_id,
        task=task,
        client=client,
    )

    cache_key = task.cache_key_fn(context, parameters) if task.cache_key_fn else None

    # Transition from `PENDING` -> `RUNNING`
    state = await client.propose_state(
        Running(state_details=StateDetails(cache_key=cache_key)),
        task_run_id=task_run_id,
    )

    # Only run the task if we enter a `RUNNING` state
    while state.is_running():

        try:
            with TaskRunContext(
                task_run_id=task_run_id,
                flow_run_id=flow_run_id,
                task=task,
                client=client,
            ):
                args, kwargs = parameters_to_args_kwargs(task.fn, parameters)
                logger.info(
                    f"Executing task {task_run_name!r} with call {call_repr(task.fn, *args, **kwargs)}..."
                )
                result = call_with_parameters(task.fn, parameters)
                if task.isasync:
                    result = await result
        except Exception as exc:
            terminal_state = Failed(
                message="Task run encountered an exception.",
                data=DataDocument.encode("cloudpickle", exc),
            )
        else:
            terminal_state = await user_return_value_to_state(
                result, serializer="cloudpickle"
            )

            # for COMPLETED tasks, add the cache key and expiration
            if terminal_state.is_completed():
                terminal_state.state_details.cache_expiration = (
                    (pendulum.now("utc") + task.cache_expiration)
                    if task.cache_expiration
                    else None
                )
                terminal_state.state_details.cache_key = cache_key

        state = await client.propose_state(terminal_state, task_run_id=task_run_id)

        if not state.is_final():
            logger.info(
                f"Task {task_run_name!r} received state {prefect_repr(state)} when proposing state {prefect_repr(terminal_state)} and will attempt to run again..."
            )
            # Attempt to enter a running state again
            state = await client.propose_state(Running(), task_run_id=task_run_id)

    logger.info(
        f"Task run {task_run_name!r} finished with state {prefect_repr(terminal_state)}"
    )
    return state


async def user_return_value_to_state(
    result: Any, serializer: str = "cloudpickle"
) -> State:
    """
    Given a return value from a user-function, create a `State` the run should
    be placed in.

    - If data is returned, we create a 'COMPLETED' state with the data
    - If a single state is returned and is not wrapped in a future, we use that state
    - If an iterable of states are returned, we apply the aggregate rule
    - If a future or iterable of futures is returned, we resolve it into states then
        apply the aggregate rule

    The aggregate rule says that given multiple states we will determine the final state
    such that:

    - If any states are not COMPLETED the final state is FAILED
    - If all of the states are COMPLETED the final state is COMPLETED
    - The states will be placed in the final state `data` attribute

    The aggregate rule is applied to _single_ futures to distinguish from returning a
    _single_ state. This prevents a flow from assuming the state of a single returned
    task future.
    """

    # States returned directly are respected without applying a rule
    if is_state(result):
        return result

    # Ensure any futures are resolved
    result = await resolve_futures(result, resolve_fn=future_to_state)

    # If we resolved a task future or futures into states, we will determine a new state
    # from their aggregate
    if is_state(result) or is_state_iterable(result):
        states = StateSet(ensure_iterable(result))

        # Determine the new state type
        new_state_type = (
            StateType.COMPLETED if states.all_completed() else StateType.FAILED
        )

        # Generate a nice message for the aggregate
        if states.all_completed():
            message = "All states completed."
        elif states.any_failed():
            message = f"{states.fail_count}/{states.total_count} states failed."
        elif not states.all_final():
            message = (
                f"{states.not_final_count}/{states.total_count} states are not final."
            )
        else:
            message = "Given states: " + states.counts_message()

        # TODO: We may actually want to set the data to a `StateSet` object and just allow
        #       it to be unpacked into a tuple and such so users can interact with it
        return State(
            type=new_state_type,
            message=message,
            data=DataDocument.encode(serializer, result),
        )

    # Otherwise, they just gave data and this is a completed result
    return Completed(data=DataDocument.encode(serializer, result))


@overload
async def get_result(
    state_or_future: Union[PrefectFuture[R], State[R]], raise_failures: bool = True
) -> R:
    ...


@overload
async def get_result(
    state_or_future: Union[PrefectFuture[R], State[R]], raise_failures: bool = False
) -> Union[R, Exception]:
    ...


@sync_compatible
async def get_result(state_or_future, raise_failures: bool = True):
    if isinstance(state_or_future, PrefectFuture):
        state = await state_or_future.wait()
    elif isinstance(state_or_future, State):
        state = state_or_future
    else:
        raise TypeError(
            f"Unexpected type {type(state_or_future).__name__!r} for `get_result`. "
            "Expected `State` or `PrefectFuture`"
        )

    if state.is_failed() and raise_failures:

        # Determine the state run type
        if state.state_details and state.state_details.task_run_id:
            run_type = "task run"
        elif state.state_details and state.state_details.flow_run_id:
            run_type = "flow run"
        else:
            run_type = "run"

        logger.info(
            f"Found failed state while retrieving result from {run_type}. Reraising the exception..."
        )
        return await raise_failed_state(state)

    return await resolve_datadoc(state.data)


@sync_compatible
async def raise_failed_state(state: State) -> None:
    if not state.is_failed():
        return

    result = await resolve_datadoc(state.data)

    if isinstance(result, BaseException):
        raise result

    elif isinstance(result, State):
        # Raise the failure in the inner state
        await raise_failed_state(result)

    elif is_state_iterable(result):
        # Raise the first failure
        for state in result:
            await raise_failed_state(state)

    else:
        raise TypeError(
            f"Unexpected result for failure state: {result!r} —— "
            f"{type(result).__name__} cannot be resolved into an exception"
        )


@contextmanager
def tags(*new_tags: str) -> Set[str]:
    current_tags = TagsContext.get().current_tags
    new_tags = current_tags.union(new_tags)
    with TagsContext(current_tags=new_tags):
        yield new_tags
