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
import logging
from contextlib import AsyncExitStack, asynccontextmanager, nullcontext
from functools import partial
from typing import Any, Awaitable, Dict, Iterable, Optional, Set, TypeVar, Union
from uuid import UUID, uuid4

import anyio
import pendulum
from anyio import start_blocking_portal
from anyio.abc import BlockingPortal

import prefect
import prefect.context
from prefect.client import OrionClient, get_client, inject_client
from prefect.context import FlowRunContext, TagsContext, TaskRunContext
from prefect.deployments import load_flow_from_deployment
from prefect.exceptions import Abort, UpstreamTaskError
from prefect.flows import Flow
from prefect.futures import PrefectFuture, call_repr, resolve_futures_to_data
from prefect.logging.handlers import OrionHandler
from prefect.logging.loggers import (
    flow_run_logger,
    get_logger,
    get_run_logger,
    task_run_logger,
)
from prefect.orion.schemas import core
from prefect.orion.schemas.core import FlowRun, TaskRun
from prefect.orion.schemas.data import DataDocument
from prefect.orion.schemas.responses import SetStateStatus
from prefect.orion.schemas.states import Failed, Pending, Running, State, StateDetails
from prefect.settings import PREFECT_DEBUG_MODE, get_current_settings
from prefect.states import (
    exception_to_crashed_state,
    return_value_to_state,
    safe_encode_exception,
)
from prefect.task_runners import BaseTaskRunner
from prefect.tasks import Task
from prefect.utilities.asyncio import (
    gather,
    in_async_main_thread,
    run_async_from_worker_thread,
    run_sync_in_worker_thread,
)
from prefect.utilities.callables import parameters_to_args_kwargs
from prefect.utilities.collections import visit_collection

R = TypeVar("R")
engine_logger = get_logger("engine")


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

    profile = prefect.context.get_profile_context()
    profile.initialize()

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
        if in_async_main_thread():
            # An event loop is already running and we must create a blocking portal to
            # run async code from this synchronous context
            with start_blocking_portal() as portal:
                return portal.call(begin_run)
        else:
            # An event loop is not running so we will create one
            return anyio.run(begin_run)

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
    profile = prefect.context.get_profile_context()
    profile.initialize()

    return anyio.run(retrieve_flow_then_begin_flow_run, flow_run_id)


@inject_client
async def create_then_begin_flow_run(
    flow: Flow, parameters: Dict[str, Any], client: OrionClient
) -> State:
    """
    Async entrypoint for flow calls

    Creates the flow run in the backend, then enters the main flow run engine.
    """
    connect_error = await client.api_healthcheck()
    if connect_error:
        raise RuntimeError(
            f"Cannot create flow run. Failed to reach API at {client.api_url}."
        ) from connect_error

    state = Pending()
    if flow.should_validate_parameters:
        try:
            parameters = flow.validate_parameters(parameters)
        except Exception as exc:
            state = Failed(
                message="Flow run received invalid parameters.",
                data=DataDocument.encode("cloudpickle", exc),
            )

    flow_run = await client.create_flow_run(
        flow,
        # Send serialized parameters to the backend
        parameters=flow.serialize_parameters(parameters),
        state=state,
        tags=TagsContext.get().current_tags,
    )

    engine_logger.info(f"Created flow run {flow_run.name!r} for flow {flow.name!r}")

    if state.is_failed():
        engine_logger.info(
            f"Flow run {flow_run.name!r} received invalid parameters and is marked as failed."
        )
        return state

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

    flow_run_logger(flow_run).debug(
        f"Loading flow for deployment {deployment.name!r}..."
    )
    try:
        flow = await load_flow_from_deployment(deployment, client=client)
    except Exception as exc:
        message = "Flow could not be retrieved from deployment."
        flow_run_logger(flow_run).exception(message)
        state = Failed(message=message, data=safe_encode_exception(exc))
        await client.set_flow_run_state(
            state=state, flow_run_id=flow_run_id, force=True
        )
        return state

    await client.update_flow_run(
        flow_run_id=flow_run_id,
        flow_version=flow.version,
    )

    if flow.should_validate_parameters:
        try:
            parameters = flow.validate_parameters(flow_run.parameters)
        except Exception as exc:
            state = Failed(
                message="Flow run received invalid parameters.",
                data=DataDocument.encode("cloudpickle", exc),
            )
            await client.propose_state(
                state=state,
                flow_run_id=flow_run_id,
            )
            return state
    else:
        parameters = flow_run.parameters

    return await begin_flow_run(
        flow=flow,
        flow_run=flow_run,
        parameters=parameters,
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

    - Starts a task runner
    - Orchestrates the flow run (runs the user-function and generates tasks)
    - Waits for tasks to complete / shutsdown the task runner
    - Sets a terminal state for the flow run

    Note that the `flow_run` contains a `parameters` attribute which is the serialized
    parameters sent to the backend while the `parameters` argument here should be the
    deserialized and validated dictionary of python objects.

    Returns:
        The final state of the run
    """
    logger = flow_run_logger(flow_run, flow)
    async with AsyncExitStack() as stack:

        await stack.enter_async_context(
            report_flow_run_crashes(flow_run=flow_run, client=client)
        )

        # If the flow is async, we need to provide a portal so sync tasks can run
        sync_portal = (
            stack.enter_context(start_blocking_portal()) if flow.isasync else None
        )

        logger.info(f"Using task runner {type(flow.task_runner).__name__!r}")
        task_runner = await stack.enter_async_context(flow.task_runner.start())

        terminal_state = await orchestrate_flow_run(
            flow,
            flow_run=flow_run,
            parameters=parameters,
            task_runner=task_runner,
            client=client,
            sync_portal=sync_portal,
        )

        await client.propose_state(
            state=terminal_state,
            flow_run_id=flow_run.id,
        )

    # If debugging, use the more complete `repr` than the usual `str` description
    display_state = repr(terminal_state) if PREFECT_DEBUG_MODE else str(terminal_state)

    logger.log(
        level=logging.INFO if terminal_state.is_completed() else logging.ERROR,
        msg=f"Finished in state {display_state}",
        extra={"send_to_orion": False},
    )

    # When a "root" flow run finishes, flush logs so we do not have to rely on handling
    # during interpreter shutdown
    OrionHandler.flush(block=True)

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
    - Resolve futures in passed parameters into values
    - Create a dummy task for representation in the parent flow

    Returns:
        The final state of the run
    """
    parent_flow_run_context = FlowRunContext.get()
    parent_logger = get_run_logger(parent_flow_run_context)

    parent_logger.debug(f"Resolving inputs to {flow.name!r}")
    task_inputs = {k: await collect_task_run_inputs(v) for k, v in parameters.items()}

    # Generate a task in the parent flow run to represent the result of the subflow run
    parent_task_run = await client.create_task_run(
        task=Task(name=flow.name, fn=lambda _: ...),
        flow_run_id=parent_flow_run_context.flow_run.id,
        dynamic_key=uuid4().hex,  # TODO: We can use a more friendly key here if needed
        task_inputs=task_inputs,
    )

    # Resolve any task futures in the input
    parameters = await resolve_futures_to_data(parameters)

    flow_run = await client.create_flow_run(
        flow,
        parameters=flow.serialize_parameters(parameters),
        parent_task_run_id=parent_task_run.id,
        state=Pending(),
        tags=TagsContext.get().current_tags,
    )

    parent_logger.info(f"Created subflow run {flow_run.name!r} for flow {flow.name!r}")
    logger = flow_run_logger(flow_run, flow)

    if flow.should_validate_parameters:
        try:
            parameters = flow.validate_parameters(parameters)
        except Exception as exc:
            state = Failed(
                message="Flow run received invalid parameters.",
                data=DataDocument.encode("cloudpickle", exc),
            )
            await client.propose_state(
                state=state,
                flow_run_id=flow_run.id,
            )
            logger.error("Received invalid parameters", exc_info=True)
            return state

    async with AsyncExitStack() as stack:
        await stack.enter_async_context(
            report_flow_run_crashes(flow_run=flow_run, client=client)
        )
        task_runner = await stack.enter_async_context(flow.task_runner.start())

        terminal_state = await orchestrate_flow_run(
            flow,
            flow_run=flow_run,
            parameters=parameters,
            task_runner=task_runner,
            client=client,
            sync_portal=parent_flow_run_context.sync_portal,
        )

    # Display the full state (including the result) if debugging
    display_state = repr(terminal_state) if PREFECT_DEBUG_MODE else str(terminal_state)
    logger.log(
        level=logging.INFO if terminal_state.is_completed() else logging.ERROR,
        msg=f"Finished in state {display_state}",
        extra={"send_to_orion": False},
    )

    # Track the subflow state so the parent flow can use it to determine its final state
    parent_flow_run_context.subflow_states.append(terminal_state)

    return terminal_state


async def orchestrate_flow_run(
    flow: Flow,
    flow_run: FlowRun,
    task_runner: BaseTaskRunner,
    parameters: Dict[str, Any],
    client: OrionClient,
    sync_portal: BlockingPortal,
) -> State:
    """
    Executes a flow run

    Note on flow timeouts:
        Since async flows are run directly in the main event loop, timeout behavior will
        match that described by anyio. If the flow is awaiting something, it will
        immediately return; otherwise, the next time it awaits it will exit. Sync flows
        are being task runner in a worker thread, which cannot be interrupted. The worker
        thread will exit at the next task call. The worker thread also has access to the
        status of the cancellation scope at `FlowRunContext.timeout_scope.cancel_called`
        which allows it to raise a `TimeoutError` to respect the timeout.

    Returns:
        The final state of the run
    """
    logger = flow_run_logger(flow_run, flow)

    # TODO: Implement state orchestation logic using return values from the API
    await client.propose_state(
        Running(),
        flow_run_id=flow_run.id,
    )

    timeout_context = (
        anyio.fail_after(flow.timeout_seconds)
        if flow.timeout_seconds
        else nullcontext()
    )

    try:
        with timeout_context as timeout_scope:
            with FlowRunContext(
                flow=flow,
                flow_run=flow_run,
                client=client,
                task_runner=task_runner,
                sync_portal=sync_portal,
                timeout_scope=timeout_scope,
            ) as flow_run_context:
                args, kwargs = parameters_to_args_kwargs(flow.fn, parameters)
                logger.debug(
                    f"Executing flow {flow.name!r} for flow run {flow_run.name!r}..."
                )

                if PREFECT_DEBUG_MODE:
                    logger.debug(f"Executing {call_repr(flow.fn, *args, **kwargs)}")
                else:
                    logger.debug(
                        f"Beginning execution...", extra={"state_message": True}
                    )

                flow_call = partial(flow.fn, *args, **kwargs)

                if flow.isasync:
                    result = await flow_call()
                else:
                    result = await run_sync_in_worker_thread(flow_call)

            await wait_for_task_runs_and_report_crashes(
                flow_run_context.task_run_futures, client=client
            )

    except TimeoutError as exc:
        state = Failed(
            name="TimedOut",
            message=f"Flow run exceeded timeout of {flow.timeout_seconds} seconds",
        )
    except Exception as exc:
        logger.error(
            f"Encountered exception during execution:",
            exc_info=True,
        )
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

        state = await return_value_to_state(result, serializer="cloudpickle")

    state = await client.propose_state(
        state=state,
        flow_run_id=flow_run.id,
    )

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

    if flow_run_context.timeout_scope and flow_run_context.timeout_scope.cancel_called:
        raise TimeoutError("Flow run timed out")

    begin_run = partial(
        create_and_submit_task_run,
        task=task,
        flow_run_context=flow_run_context,
        parameters=parameters,
        dynamic_key=dynamic_key,
        wait_for=wait_for,
    )

    # Async task run in async flow run
    if task.isasync and flow_run_context.flow.isasync:
        return begin_run()  # Return a coroutine for the user to await

    # Async or sync task run in sync flow run
    elif not flow_run_context.flow.isasync:
        return run_async_from_worker_thread(begin_run)

    # Sync task run in async flow run
    else:
        # Call out to the sync portal since we are not in a worker thread
        return flow_run_context.sync_portal.call(begin_run)


async def collect_task_run_inputs(
    expr: Any,
) -> Set[Union[core.TaskRunResult, core.Parameter, core.Constant]]:
    """
    This function recurses through an expression to generate a set of any discernable
    task run inputs it finds in the data structure. It produces a set of all inputs
    found.

    Example:
        >>> task_inputs = {
        >>>    k: await collect_task_run_inputs(v) for k, v in parameters.items()
        >>> }
    """
    # TODO: This function needs to be updated to detect parameters and constants

    inputs = set()

    async def add_futures_and_states_to_inputs(obj):
        if isinstance(obj, PrefectFuture):
            inputs.add(core.TaskRunResult(id=obj.run_id))

        if isinstance(obj, State):
            if obj.state_details.task_run_id:
                inputs.add(core.TaskRunResult(id=obj.state_details.task_run_id))

    await visit_collection(
        expr, visit_fn=add_futures_and_states_to_inputs, return_data=False
    )

    return inputs


async def create_and_submit_task_run(
    task: Task,
    flow_run_context: FlowRunContext,
    parameters: Dict[str, Any],
    dynamic_key: str,
    wait_for: Optional[Iterable[PrefectFuture]],
) -> PrefectFuture:
    """
    Async entrypoint for task calls.

    Tasks must be called within a flow. When tasks are called, they create a task run
    and submit orchestration of the run to the flow run's task runner. The task runner
    returns a future that is returned immediately.
    """
    task_inputs = {k: await collect_task_run_inputs(v) for k, v in parameters.items()}
    if wait_for:
        task_inputs["wait_for"] = await collect_task_run_inputs(wait_for)

    logger = get_run_logger(flow_run_context)

    task_run = await flow_run_context.client.create_task_run(
        task=task,
        flow_run_id=flow_run_context.flow_run.id,
        dynamic_key=dynamic_key,
        state=Pending(),
        extra_tags=TagsContext.get().current_tags,
        task_inputs=task_inputs,
    )

    logger.info(f"Created task run {task_run.name!r} for task {task.name!r}")

    future = await flow_run_context.task_runner.submit(
        task_run,
        run_fn=begin_task_run,
        run_kwargs=dict(
            task=task,
            task_run=task_run,
            parameters=parameters,
            wait_for=wait_for,
            settings=get_current_settings(),
        ),
        asynchronous=task.isasync,
    )

    logger.debug(f"Submitted task run {task_run.name!r} to task runner")

    # Track the task run future in the flow run context
    flow_run_context.task_run_futures.append(future)

    return future


async def begin_task_run(
    task: Task,
    task_run: TaskRun,
    parameters: Dict[str, Any],
    wait_for: Optional[Iterable[PrefectFuture]],
    settings: prefect.settings.Settings,
):
    """
    Entrypoint for task run execution.

    This function is intended for submission to the task runner.

    This method may be called from a worker so we enter a temporary profile context
    with the settings from submission and ensure it is initialized.
    """
    flow_run_context = prefect.context.FlowRunContext.get()

    async with AsyncExitStack() as stack:
        profile = stack.enter_context(
            prefect.context.ProfileContext(
                name=f"task-run-{task_run.name}", settings=settings, env={}
            )
        )
        profile.initialize(create_home=False)

        if flow_run_context:
            # Accessible if on a worker that is running in the same thread as the flow
            client = flow_run_context.client
        else:
            # Otherwise, retrieve a new client
            client = await stack.enter_async_context(get_client())

        connect_error = await client.api_healthcheck()
        if connect_error:
            raise RuntimeError(
                f"Cannot orchestrate task run '{task_run.id}'. "
                f"Failed to connect to API at {client.api_url}."
            ) from connect_error

        return await orchestrate_task_run(
            task=task,
            task_run=task_run,
            parameters=parameters,
            wait_for=wait_for,
            client=client,
        )


async def orchestrate_task_run(
    task: Task,
    task_run: TaskRun,
    parameters: Dict[str, Any],
    wait_for: Optional[Iterable[PrefectFuture]],
    client: OrionClient,
) -> State:
    """
    Execute a task run

    This function should be submitted to an task runner. We must construct the context
    here instead of receiving it already populated since we may be in a new environment.

    Proposes a RUNNING state, then
    - if accepted, the task user function will be run
    - if rejected, the received state will be returned

    When the user function is run, the result will be used to determine a final state
    - if an exception is encountered, it is trapped and stored in a FAILED state
    - otherwise, `return_value_to_state` is used to determine the state

    If the final state is COMPLETED, we generate a cache key as specified by the task

    The final state is then proposed
    - if accepted, this is the final state and will be returned
    - if rejected and a new final state is provided, it will be returned
    - if rejected and a non-final state is provided, we will attempt to enter a RUNNING
        state again

    Returns:
        The final state of the run
    """
    logger = task_run_logger(task_run, task=task)
    task_run_context = TaskRunContext(
        task_run=task_run,
        task=task,
        client=client,
    )

    cache_key = (
        task.cache_key_fn(task_run_context, parameters) if task.cache_key_fn else None
    )

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
            args, kwargs = parameters_to_args_kwargs(task.fn, resolved_parameters)

            if PREFECT_DEBUG_MODE.value():
                logger.debug(f"Executing {call_repr(task.fn, *args, **kwargs)}")
            else:
                logger.debug(f"Beginning execution...", extra={"state_message": True})

            with task_run_context:
                if task.isasync:
                    result = await task.fn(*args, **kwargs)
                else:
                    result = await run_sync_in_worker_thread(task.fn, *args, **kwargs)

        except Exception as exc:
            logger.error(
                f"Encountered exception during execution:",
                exc_info=True,
            )
            terminal_state = Failed(
                message="Task run encountered an exception.",
                data=DataDocument.encode("cloudpickle", exc),
            )
        else:
            terminal_state = await return_value_to_state(
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

        if state.type != terminal_state.type and PREFECT_DEBUG_MODE:
            logger.debug(
                f"Received new state {state} when proposing final state {terminal_state}",
                extra={"send_to_orion": False},
            )

        if not state.is_final():
            logger.info(
                f"Received non-final state {state.name!r} when proposing final state {terminal_state.name!r} and will attempt to run again...",
                extra={"send_to_orion": False},
            )
            # Attempt to enter a running state again
            state = await client.propose_state(Running(), task_run_id=task_run.id)

    # If debugging, use the more complete `repr` than the usual `str` description
    display_state = repr(state) if PREFECT_DEBUG_MODE else str(state)

    logger.log(
        level=logging.INFO if state.is_completed() else logging.ERROR,
        msg=f"Finished in state {display_state}",
        extra={"send_to_orion": False},
    )

    return state


async def wait_for_task_runs_and_report_crashes(
    task_run_futures: Iterable[PrefectFuture], client: OrionClient
) -> None:
    crash_exceptions = []

    # Gather states concurrently first
    states = await gather(*(future._wait for future in task_run_futures))

    for future, state in zip(task_run_futures, states):
        logger = task_run_logger(future.task_run)

        if not state.name == "Crashed":
            continue

        exception = state.result(raise_on_failure=False)

        logger.info(f"Crash detected! {state.message}")
        logger.debug("Crash details:", exc_info=exception)

        # Update the state of the task run
        result = await client.set_task_run_state(
            task_run_id=future.task_run.id, state=state, force=True
        )
        if result.status == SetStateStatus.ACCEPT:
            engine_logger.debug(
                f"Reported crashed task run {future.task_run.name!r} successfully."
            )
        else:
            engine_logger.warning(
                f"Failed to report crashed task run {future.task_run.name!r}. "
                f"Orchestrator did not accept state: {result!r}"
            )

        crash_exceptions.append(exception)

    # Now that we've finished reporting crashed tasks, reraise any exit exceptions
    for exception in crash_exceptions:
        if isinstance(exception, (KeyboardInterrupt, SystemExit)):
            raise exception


@asynccontextmanager
async def report_flow_run_crashes(flow_run: FlowRun, client: OrionClient):
    """
    Detect flow run crashes during this context and update the run to a proper final
    state.

    This context _must_ reraise the exception to properly exit the run.
    """
    try:
        yield
    except BaseException as exc:
        state = exception_to_crashed_state(exc)
        logger = flow_run_logger(flow_run)
        with anyio.CancelScope(shield=True):
            logger.error(f"Crash detected! {state.message}")
            logger.debug("Crash details:", exc_info=exc)
            await client.set_flow_run_state(
                state=state,
                flow_run_id=flow_run.id,
                force=True,
            )
            engine_logger.debug(
                f"Reported crashed flow run {flow_run.name!r} successfully!"
            )

        # Reraise the exception
        raise exc from None


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
            state = await expr._wait()
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


if __name__ == "__main__":
    import sys

    try:
        flow_run_id = UUID(sys.argv[1])
    except Exception:
        engine_logger.error(
            f"Invalid flow run id. Recieved arguments: {sys.argv}", exc_info=True
        )
        exit(1)

    try:
        enter_flow_run_engine_from_subprocess(flow_run_id)
    except Abort as exc:
        engine_logger.info(
            f"Engine execution of flow run '{flow_run_id}' aborted by orchestrator: {exc}"
        )
        exit(0)
    except Exception:
        engine_logger.error(
            f"Engine execution of flow run '{flow_run_id}' exited with unexpected "
            "exception",
            exc_info=True,
        )
        exit(1)
    except BaseException:
        engine_logger.error(
            f"Engine execution of flow run '{flow_run_id}' interrupted by base "
            "exception",
            exc_info=True,
        )
        # Let the exit code be determined by the base exception type
        raise
