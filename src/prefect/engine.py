"""
Client-side execution of flows and tasks
"""
import time
from contextlib import nullcontext
from functools import partial
from typing import Any, Awaitable, Dict, Union
from uuid import UUID

import pendulum
from anyio import start_blocking_portal
from anyio.abc import BlockingPortal
from anyio.from_thread import BlockingPortal
from pydantic import validate_arguments

from prefect.client import OrionClient, inject_client
from prefect.context import FlowRunContext, TaskRunContext
from prefect.executors import BaseExecutor
from prefect.flows import Flow
from prefect.futures import PrefectFuture, resolve_futures, return_val_to_state
from prefect.orion.schemas.responses import SetStateStatus
from prefect.orion.schemas.states import State, StateDetails, StateType
from prefect.tasks import Task
from prefect.utilities.asyncio import (
    run_async_from_worker_thread,
    run_sync_in_worker_thread,
)


def enter_flow_run_engine(
    flow: Flow, parameters: Dict[str, Any]
) -> Union[PrefectFuture, Awaitable[PrefectFuture]]:
    if TaskRunContext.get():
        raise RuntimeError(
            "Flows cannot be called from within tasks. Did you mean to call this "
            "flow in a flow?"
        )

    parent_flow_run_context = FlowRunContext.get()
    is_subflow_run = parent_flow_run_context is not None

    begin_run = partial(
        begin_subflow_run if is_subflow_run else begin_flow_run,
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


@inject_client
async def begin_flow_run(
    flow: Flow,
    parameters: Dict[str, Any],
    client: OrionClient,
) -> State:
    """
    Async entrypoint for flow calls

    When flows are called, they
    - create a flow run
    - start an executor
    - orchestrate the flow run (run the user-function and generate tasks)
    - wait for tasks to complete / shutdown the executor
    - set a terminal state for the flow run

    This function then returns a fake future containing the terminal state.
    # TODO: Flow calls should not return futures since they block.
    """
    flow_run_id = await client.create_flow_run(
        flow,
        parameters=parameters,
        state=State(type=StateType.PENDING),
    )

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
    await client.set_flow_run_state(
        flow_run_id,
        state=terminal_state,
    )

    return terminal_state


@inject_client
async def begin_subflow_run(
    flow: Flow,
    parameters: Dict[str, Any],
    client: OrionClient,
) -> State:
    """
    Async entrypoint for flows calls within a flow run

    Subflows differ from parent flows in that they
    - use the existing parent flow executor
    - create a dummy task for representation in the parent flow

    This function then returns a fake future containing the terminal state.
    # TODO: Flow calls should not return futures since they block.
    """
    parent_flow_run_context = FlowRunContext.get()

    # Generate a task in the parent flow run to represent the result of the subflow run
    parent_task_run_id = await client.create_task_run(
        task=Task(name=flow.name, fn=lambda _: ...),
        flow_run_id=parent_flow_run_context.flow_run_id,
    )

    flow_run_id = await client.create_flow_run(
        flow,
        parameters=parameters,
        parent_task_run_id=parent_task_run_id,
        state=State(type=StateType.PENDING),
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
    await client.set_flow_run_state(
        flow_run_id,
        state=terminal_state,
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
    TODO: Note that pydantic will now coerce parameter types into the correct type
          even if the user wants failure on inexact type matches. We may want to
          implement a strict runtime typecheck with a configuration flag
    TODO: `validate_arguments` can throw an error while wrapping `fn` if the
          signature is not pydantic-compatible. We'll want to confirm that it will
          work at Flow.__init__ so we can raise errors to users immediately
    TODO: Implement state orchestation logic using return values from the API
    """
    await client.set_flow_run_state(flow_run_id, State(type=StateType.RUNNING))

    try:
        with FlowRunContext(
            flow_run_id=flow_run_id,
            flow=flow,
            client=client,
            executor=executor,
            sync_portal=sync_portal,
        ):
            flow_call = partial(validate_arguments(flow.fn), **parameters)
            if flow.isasync:
                result = await flow_call()
            else:
                result = await run_sync_in_worker_thread(flow_call)

    except Exception as exc:
        state = State(
            type=StateType.FAILED,
            message="Flow run encountered an exception.",
            data=exc,
        )
    else:
        state = await return_val_to_state(result)

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

    task_run_id = await flow_run_context.client.create_task_run(
        task=task,
        flow_run_id=flow_run_context.flow_run_id,
        state=State(type=StateType.PENDING),
    )

    future = await flow_run_context.executor.submit(
        task_run_id,
        orchestrate_task_run,
        task=task,
        task_run_id=task_run_id,
        flow_run_id=flow_run_context.flow_run_id,
        parameters=parameters,
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
    state = await propose_state(
        client,
        task_run_id,
        State(
            type=StateType.RUNNING,
            state_details=StateDetails(
                cache_key=cache_key,
            ),
        ),
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
                result = task.fn(**parameters)
                if task.isasync:
                    result = await result
        except Exception as exc:
            terminal_state = State(
                type=StateType.FAILED,
                message="Task run encountered an exception.",
                data=exc,
            )
        else:
            terminal_state = await return_val_to_state(result)

            # for COMPLETED tasks, add the cache key and expiration
            if terminal_state.is_completed():
                terminal_state.state_details.cache_expiration = (
                    (pendulum.now("utc") + task.cache_expiration)
                    if task.cache_expiration
                    else None
                )
                terminal_state.state_details.cache_key = cache_key

        state = await propose_state(client, task_run_id, terminal_state)

        if state.is_scheduled():  # Received a retry from the backend
            start_time = pendulum.instance(state.state_details.scheduled_time)
            wait_time = start_time.diff(abs=False).in_seconds() * -1
            print(f"Task is scheduled to run again {start_time.diff_for_humans()}")
            if wait_time > 0:
                print(f"Sleeping for {wait_time}s...")
                time.sleep(wait_time)

            state = await propose_state(
                client, task_run_id, State(type=StateType.RUNNING)
            )

    return state


async def propose_state(client: OrionClient, task_run_id: UUID, state: State) -> State:
    """
    TODO: Consider rolling this behavior into the `Client` state update method once we
          understand how we want to handle ABORT cases
    """
    response = await client.set_task_run_state(
        task_run_id,
        state=state,
    )
    if response.status == SetStateStatus.ACCEPT:
        if response.details.state_details:
            state.state_details = response.details.state_details
        return state

    if response.status == SetStateStatus.ABORT:
        raise RuntimeError("ABORT is not yet handled")

    server_state = response.details.state

    return server_state
