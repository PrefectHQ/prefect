"""
Client-side execution and orchestration of flows and tasks.

Engine process overview

- The flow or task is called by the user.
    See `Flow.__call__`, `Task.__call__`

- A synchronous engine function acts as an entrypoint to the async engine.
    See `enter_flow_run_engine`, `enter_task_run_engine`

- The async engine creates a run via the API and prepares for execution of user-code.
    See `begin_flow_run`, `begin_task_run`

- The run is orchestrated through states, calling the user's function as necessary.
    See `orchestrate_flow_run`, `orchestrate_task_run`
"""
import pendulum
from contextlib import contextmanager, nullcontext
from functools import partial
from typing import Any, Awaitable, Dict, Set, TypeVar, Union, Iterable, Optional
from uuid import UUID, uuid4

import pendulum
import logging
import anyio
from anyio import start_blocking_portal
from anyio.abc import BlockingPortal
from prefect.exceptions import UpstreamTaskError

from prefect.utilities.collections import visit_collection
from prefect.client import OrionClient, inject_client
from prefect.context import FlowRunContext, TagsContext, TaskRunContext
from prefect.deployments import load_flow_from_deployment
from prefect.executors import BaseExecutor
from prefect.flows import Flow
from prefect.futures import (
    PrefectFuture,
    resolve_futures_to_data,
    resolve_futures_to_states,
    call_repr,
)
from prefect.orion.schemas import core
from prefect.orion.schemas.data import DataDocument
from prefect.orion.schemas.states import (
    Completed,
    Failed,
    Pending,
    Cancelled,
    Running,
    State,
    StateDetails,
    StateType,
)
from prefect.orion.schemas.core import TaskRun, FlowRun
from prefect.orion.states import StateSet, is_state, is_state_iterable
from prefect.serializers import resolve_datadoc
from prefect.tasks import Task
from prefect.utilities.asyncio import (
    run_async_from_worker_thread,
    run_sync_in_worker_thread,
    sync_compatible,
)
from prefect.utilities.callables import (
    assert_parameters_are_serializable,
    parameters_to_args_kwargs,
)
from prefect.utilities.collections import ensure_iterable
from prefect.serializers import resolve_datadoc
from prefect.utilities.logging import get_logger

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


def enter_flow_run_engine_from_subprocess(flow_run_id: UUID) -> State:
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

    assert_parameters_are_serializable(parameters)

    flow_run = await client.create_flow_run(
        flow,
        parameters=parameters,
        state=Pending(),
        tags=TagsContext.get().current_tags,
    )
    return await begin_flow_run(
        flow=flow, flow_run=flow_run, parameters=parameters, client=client
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
        flow_run=flow_run,
        parameters=flow_run.parameters,
        client=client,
    )


async def begin_flow_run(
    flow: Flow,
    flow_run: FlowRun,
    parameters: Dict[str, Any],
    client: OrionClient,
) -> State:
    """
    Begins execution of a flow run; blocks until completion of the flow run

    - Starts an executor
    - Orchestrates the flow run (runs the user-function and generates tasks)
    - Waits for tasks to complete / shutsdown the executor
    - Sets a terminal state for the flow run

    Returns:
        The final state of the run
    """
    logger.info(
        f"Beginning flow run {flow_run.name!r} for flow {flow.name!r} with parameters {parameters}..."
    )
    # If the flow is async, we need to provide a portal so sync tasks can run
    portal_context = start_blocking_portal() if flow.isasync else nullcontext()

    with flow.executor.start() as executor:
        with portal_context as sync_portal:
            terminal_state = await orchestrate_flow_run(
                flow,
                flow_run=flow_run,
                parameters=parameters,
                executor=executor,
                client=client,
                sync_portal=sync_portal,
            )

    # Update the flow to the terminal state _after_ the executor has shut down
    await client.propose_state(
        state=terminal_state,
        flow_run_id=flow_run.id,
    )

    logger.log(
        level=logging.INFO if terminal_state.is_completed() else logging.ERROR,
        msg=f"Flow run finished with state {terminal_state}",
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

    Returns:
        The final state of the run
    """
    parent_flow_run_context = FlowRunContext.get()

    logger.info(
        f"Creating subflow run for flow {flow.name!r} within {parent_flow_run_context.flow.name!r}..."
    )

    # Generate a task in the parent flow run to represent the result of the subflow run
    parent_task_run = await client.create_task_run(
        task=Task(name=flow.name, fn=lambda _: ...),
        flow_run_id=parent_flow_run_context.flow_run_id,
        dynamic_key=uuid4().hex,  # TODO: We can use a more friendly key here if needed
    )

    # Resolve any task futures in the input
    parameters = await resolve_futures_to_data(parameters)

    # Then validate that the parameters are serializable
    assert_parameters_are_serializable(parameters)

    flow_run = await client.create_flow_run(
        flow,
        parameters=parameters,
        parent_task_run_id=parent_task_run.id,
        state=Pending(),
        tags=TagsContext.get().current_tags,
    )

    logger.info(
        f"Beginning subflow run {flow_run.name!r} for flow {flow.name!r} with parameters {parameters}..."
    )

    terminal_state = await orchestrate_flow_run(
        flow,
        flow_run=flow_run,
        parameters=parameters,
        executor=parent_flow_run_context.executor,
        client=client,
        sync_portal=parent_flow_run_context.sync_portal,
    )

    # Update the flow to the terminal state _after_ the executor has shut down
    terminal_state = await client.propose_state(
        state=terminal_state,
        flow_run_id=flow_run.id,
    )

    logger.log(
        level=logging.INFO if terminal_state.is_completed() else logging.ERROR,
        msg=f"Subflow run finished with state {terminal_state}",
    )

    # Track the subflow state so the parent flow can use it to determine its final state
    parent_flow_run_context.subflow_states.append(terminal_state)

    return terminal_state


@inject_client
async def orchestrate_flow_run(
    flow: Flow,
    flow_run: FlowRun,
    parameters: Dict[str, Any],
    executor: BaseExecutor,
    client: OrionClient,
    sync_portal: BlockingPortal,
) -> State:
    """
    Executes a flow run

    Note on flow timeouts:
        Since async flows are run directly in the main event loop, timeout behavior will
        match that described by anyio. If the flow is awaiting something, it will
        immediately return; otherwise, the next time it awaits it will exit. Sync flows
        are being executor in a worker thread, which cannot be interrupted. The worker
        thread will exit at the next task call. The worker thread also has access to the
        status of the cancellation scope at `FlowRunContext.timeout_scope.cancel_called`
        which allows it to raise a `TimeoutError` to respect the timeout.

    Returns:
        The final state of the run
    """
    # TODO: Implement state orchestation logic using return values from the API
    await client.propose_state(Running(), flow_run_id=flow_run.id)

    timeout_context = (
        anyio.fail_after(flow.timeout_seconds)
        if flow.timeout_seconds
        else nullcontext()
    )

    try:

        with timeout_context as timeout_scope:
            with FlowRunContext(
                flow_run_id=flow_run.id,
                flow=flow,
                client=client,
                executor=executor,
                sync_portal=sync_portal,
                timeout_scope=timeout_scope,
            ) as flow_run_context:
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

    except TimeoutError as exc:
        state = Failed(
            message=f"Flow run timed out after {flow.timeout_seconds} seconds"
        )
    except Exception as exc:
        state = Failed(
            message="Flow run encountered an exception.",
            data=DataDocument.encode("cloudpickle", exc),
        )
    else:
        if result is None:
            # All tasks and subflows are reference tasks if there is no return value
            # If there are no tasks, use `None` instead of an empty iterable
            result = (
                flow_run_context.task_run_futures + flow_run_context.subflow_states
            ) or None

        state = await user_return_value_to_state(result, serializer="cloudpickle")

    return state


def enter_task_run_engine(
    task: Task,
    parameters: Dict[str, Any],
    dynamic_key: str,
    wait_for: Optional[Iterable[PrefectFuture]],
) -> Union[PrefectFuture, Awaitable[PrefectFuture]]:
    """
    Sync entrypoint for task calls
    """
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

    if flow_run_context.timeout_scope and flow_run_context.timeout_scope.cancel_called:
        raise TimeoutError("Flow run timed out")

    begin_run = partial(
        begin_task_run,
        task=task,
        flow_run_context=flow_run_context,
        parameters=parameters,
        dynamic_key=dynamic_key,
        wait_for=wait_for,
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


async def collect_task_run_inputs(
    expr: Any, results: Set = None
) -> Set[Union[core.TaskRunResult, core.Parameter, core.Constant]]:
    """
    This function recurses through an expression to generate a set of any discernable
    task run inputs it finds in the data structure. It produces a set of all
    inputs found.
    """

    inputs = set()

    async def visit_fn(expr):
        if isinstance(expr, PrefectFuture):
            inputs.add(core.TaskRunResult(id=expr.run_id))

        if isinstance(expr, State):
            if expr.state_details.task_run_id:
                inputs.add(core.TaskRunResult(id=expr.state_details.task_run_id))

    await visit_collection(expr, visit_fn=visit_fn)
    return inputs


async def begin_task_run(
    task: Task,
    flow_run_context: FlowRunContext,
    parameters: Dict[str, Any],
    dynamic_key: str,
    wait_for: Optional[Iterable[PrefectFuture]],
) -> PrefectFuture:
    """
    Async entrypoint for task calls.

    Tasks must be called within a flow. When tasks are called, they create a task run
    and submit orchestration of the run to the flow run's executor. The executor returns
    a future that is returned immediately.
    """
    task_inputs = {k: await collect_task_run_inputs(v) for k, v in parameters.items()}
    if wait_for:
        task_inputs["wait_for"] = await collect_task_run_inputs(wait_for)

    task_run = await flow_run_context.client.create_task_run(
        task=task,
        flow_run_id=flow_run_context.flow_run_id,
        dynamic_key=dynamic_key,
        state=Pending(),
        extra_tags=TagsContext.get().current_tags,
        task_inputs=task_inputs,
    )

    logger.info(
        f"Submitting task run {task_run.name!r} to executor with parameters {parameters}..."
    )

    future = await flow_run_context.executor.submit(
        task_run,
        orchestrate_task_run,
        dict(
            task=task,
            task_run=task_run,
            parameters=parameters,
            wait_for=wait_for,
        )
    )

    # Track the task run future in the flow run context
    flow_run_context.task_run_futures.append(future)

    return future


@inject_client
async def orchestrate_task_run(
    task: Task,
    task_run: TaskRun,
    parameters: Dict[str, Any],
    wait_for: Optional[Iterable[PrefectFuture]],
    client: OrionClient,
) -> State:
    """
    Execute a task run

    This function should be submitted to an executor. We must construct the context here
    instead of receiving it already populated since we may be in a new environment.

    Proposes a RUNNING state, then
    - if accepted, the task user function will be run
    - if rejected, the received state will be returned

    When the user function is run, the result will be used to determine a final state
    - if an exception is encountered, it is trapped and stored in a FAILED state
    - otherwise, `user_return_value_to_state` is used to determine the state

    If the final state is COMPLETED, we generate a cache key as specified by the task

    The final state is then proposed
    - if accepted, this is the final state and will be returned
    - if rejected and a new final state is provided, it will be returned
    - if rejected and a non-final state is provided, we will attempt to enter a RUNNING
        state again

    Returns:
        The final state of the run
    """
    context = TaskRunContext(
        task_run_id=task_run.id,
        flow_run_id=task_run.flow_run_id,
        task=task,
        client=client,
    )

    cache_key = task.cache_key_fn(context, parameters) if task.cache_key_fn else None

    try:
        # Resolve futures in parameters into data
        resolved_parameters = await resolve_upstream_task_futures(parameters)
        # Resolve futures in any non-data dependencies to ensure they are ready
        await resolve_upstream_task_futures(wait_for, return_data=False)
    except UpstreamTaskError as upstream_exc:
        state = await client.propose_state(
            Pending(name="NotReady", message=str(upstream_exc)),
            task_run_id=task_run.id,
        )
    else:
        # Transition from `PENDING` -> `RUNNING`
        state = await client.propose_state(
            Running(state_details=StateDetails(cache_key=cache_key)),
            task_run_id=task_run.id,
        )

    # Only run the task if we enter a `RUNNING` state
    while state.is_running():

        try:
            with TaskRunContext(
                task_run_id=task_run.id,
                flow_run_id=task_run.flow_run_id,
                task=task,
                client=client,
            ):
                args, kwargs = parameters_to_args_kwargs(task.fn, resolved_parameters)
                logger.info(
                    f"Executing task {task_run.name!r} with call {call_repr(task.fn, *args, **kwargs)}..."
                )
                result = task.fn(*args, **kwargs)
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

        state = await client.propose_state(terminal_state, task_run_id=task_run.id)

        if not state.is_final():
            logger.info(
                f"Task {task_run.name!r} received state {state} when proposing state {terminal_state} and will attempt to run again..."
            )
            # Attempt to enter a running state again
            state = await client.propose_state(Running(), task_run_id=task_run.id)

    logger.info(f"Task run {task_run.name!r} finished with state {state}")
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
    result = await resolve_futures_to_states(result)

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


@sync_compatible
async def raise_failed_state(state: State) -> None:
    """
    Given a FAILED state, raise the contained exception.

    If not given a FAILED state, this function will return immediately.

    If the state contains a result of multiple states, the first FAILED state will be
    raised.

    If the state is FAILED but does not contain an exception type result, a `TypeError`
    will be raised.
    """
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


async def resolve_upstream_task_futures(
    parameters: Dict[str, Any], return_data: bool = True
) -> Dict[str, Any]:
    """
    Resolve any `PrefectFuture` types nested in parameters into data.

    Returns:
        A copy of the parameters with resolved data

    Raises:
        UpstreamTaskError: If any of the upstream states are not `COMPLETED`
    """

    async def visit_fn(expr):
        # Resolves futures into data, raising if they are not completed after `wait` is
        # called.
        if isinstance(expr, PrefectFuture):
            state = await expr.wait()
            if not state.is_completed():
                raise UpstreamTaskError(
                    f"Upstream task run '{state.state_details.task_run_id}' did not reach a 'COMPLETED' state."
                )
            # Only load the state data if requested
            if return_data:
                return state.result()
        else:
            return expr

    return await visit_collection(
        parameters,
        visit_fn=visit_fn,
        return_data=return_data,
    )


@contextmanager
def tags(*new_tags: str) -> Set[str]:
    """
    Context manager to add tags to flow and task run calls.

    Tags are always combined with any existing tags.

    Yields:
        The current set of tags

    Examples:
        >>> from prefect import tags, task, flow
        >>> @task
        >>> def my_task():
        >>>     pass

        Run a task with tags

        >>> @flow
        >>> def my_flow():
        >>>     with tags("a", "b"):
        >>>         my_task()  # has tags: a, b

        Run a flow with tags

        >>> @flow
        >>> def my_flow():
        >>>     pass
        >>> with tags("a", b"):
        >>>     my_flow()  # has tags: a, b

        Run a task with nested tag contexts

        >>> @flow
        >>> def my_flow():
        >>>     with tags("a", "b"):
        >>>         with tags("c", "d"):
        >>>             my_task()  # has tags: a, b, c, d
        >>>         my_task()  # has tags: a, b

        Inspect the current tags

        >>> @flow
        >>> def my_flow():
        >>>     with tags("c", "d"):
        >>>         with tags("e", "f") as current_tags:
        >>>              print(current_tags)
        >>> with tags("a", b"):
        >>>     my_flow()
        {"a", "b", "c", "d", "e", "f"}
    """
    current_tags = TagsContext.get().current_tags
    new_tags = current_tags.union(new_tags)
    with TagsContext(current_tags=new_tags):
        yield new_tags
