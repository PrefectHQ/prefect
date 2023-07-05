"""
Client-side execution and orchestration of flows and tasks.

## Engine process overview

### Flows

- **The flow is called by the user or an existing flow run is executed in a new process.**

    See `Flow.__call__` and `prefect.engine.__main__` (`python -m prefect.engine`)

- **A synchronous function acts as an entrypoint to the engine.**
    The engine executes on a dedicated "global loop" thread. For asynchronous flow calls,
    we return a coroutine from the entrypoint so the user can enter the engine without
    blocking their event loop.

    See `enter_flow_run_engine_from_flow_call`, `enter_flow_run_engine_from_subprocess`

- **The thread that calls the entrypoint waits until orchestration of the flow run completes.**
    This thread is referred to as the "user" thread and is usually the "main" thread.
    The thread is not blocked while waiting — it allows the engine to send work back to it.
    This allows us to send calls back to the user thread from the global loop thread.

    See `wait_for_call_in_loop_thread` and `call_soon_in_waiting_thread`

- **The asynchronous engine branches depending on if the flow run exists already and if
    there is a parent flow run in the current context.**

    See `create_then_begin_flow_run`, `create_and_begin_subflow_run`, and `retrieve_flow_then_begin_flow_run`

- **The asynchronous engine prepares for execution of the flow run.**
    This includes starting the task runner, preparing context, etc.

    See `begin_flow_run`

- **The flow run is orchestrated through states, calling the user's function as necessary.**
    Generally the user's function is sent for execution on the user thread.
    If the flow function cannot be safely executed on the user thread, e.g. it is
    a synchronous child in an asynchronous parent it will be scheduled on a worker
    thread instead.

    See `orchestrate_flow_run`, `call_soon_in_waiting_thread`, `call_soon_in_new_thread`

### Tasks

- **The task is called or submitted by the user.**
    We require that this is always within a flow.

    See `Task.__call__` and `Task.submit`
    
- **A synchronous function acts as an entrypoint to the engine.**
    Unlike flow calls, this _will not_ block until completion if `submit` was used.

    See `enter_task_run_engine`

- **A future is created for the task call.**
    Creation of the task run and submission to the task runner is scheduled as a 
    background task so submission of many tasks can occur concurrently.

    See `create_task_run_future` and `create_task_run_then_submit`

- **The engine branches depending on if a future, state, or result is requested.**
    If a future is requested, it is returned immediately to the user thread.
    Otherwise, the engine will wait for the task run to complete and return the final
    state or result.

    See `get_task_call_return_value`

- **An engine function is submitted to the task runner.**
    The task runner will schedule this function for execution on a worker.
    When executed, it will prepare for orchestration and wait for completion of the run.

    See `create_task_run_then_submit` and `begin_task_run`

- **The task run is orchestrated through states, calling the user's function as necessary.**
    The user's function is always executed in a worker thread for isolation. 
    
    See `orchestrate_task_run`, `call_soon_in_new_thread`

    _Ideally, for local and sequential task runners we would send the task run to the
    user thread as we do for flows. See [#9855](https://github.com/PrefectHQ/prefect/pull/9855).
"""
import asyncio
import contextlib
import logging
import os
import signal
import prefect.plugins
import threading
import sys
import time
from contextlib import AsyncExitStack, asynccontextmanager
from functools import partial
from typing import Any, Awaitable, Dict, Iterable, List, Optional, Set, TypeVar, Union
from uuid import UUID, uuid4

import anyio
import pendulum
from anyio import start_blocking_portal
from typing_extensions import Literal

import prefect
import prefect.context
import prefect.plugins
from prefect.states import is_state
from prefect._internal.concurrency.api import create_call, from_async, from_sync
from prefect._internal.concurrency.calls import get_current_call
from prefect._internal.concurrency.threads import wait_for_global_loop_exit
from prefect._internal.concurrency.cancellation import CancelledError, get_deadline
from prefect.client.orchestration import PrefectClient, get_client
from prefect.client.schemas import FlowRun, OrchestrationResult, TaskRun
from prefect.client.schemas.filters import FlowRunFilter
from prefect.client.schemas.objects import (
    StateDetails,
    StateType,
    TaskRunInput,
    TaskRunResult,
)
from prefect.client.schemas.responses import SetStateStatus
from prefect.client.schemas.sorting import FlowRunSort
from prefect.client.utilities import inject_client
from prefect.context import (
    FlowRunContext,
    PrefectObjectRegistry,
    TagsContext,
    TaskRunContext,
)
from prefect.deployments import load_flow_from_flow_run
from prefect.events import Event, emit_event
from prefect.exceptions import (
    Abort,
    FlowPauseTimeout,
    MappingLengthMismatch,
    MappingMissingIterable,
    NotPausedError,
    Pause,
    PausedRun,
    PrefectException,
    TerminationSignal,
    UpstreamTaskError,
)
from prefect.flows import Flow
from prefect.futures import PrefectFuture, call_repr, resolve_futures_to_states
from prefect.logging.configuration import setup_logging
from prefect.logging.handlers import APILogHandler
from prefect.logging.loggers import (
    flow_run_logger,
    get_logger,
    get_run_logger,
    patch_print,
    task_run_logger,
)
from prefect.results import BaseResult, ResultFactory
from prefect.settings import (
    PREFECT_DEBUG_MODE,
    PREFECT_LOGGING_LOG_PRINTS,
    PREFECT_TASKS_REFRESH_CACHE,
    PREFECT_UI_URL,
)
from prefect.states import (
    Paused,
    Pending,
    Running,
    State,
    exception_to_crashed_state,
    exception_to_failed_state,
    get_state_exception,
    return_value_to_state,
)
from prefect.task_runners import (
    CONCURRENCY_MESSAGES,
    BaseTaskRunner,
    TaskConcurrencyType,
)
from prefect.tasks import Task
from prefect.utilities.annotations import allow_failure, quote, unmapped
from prefect.utilities.asyncutils import (
    gather,
    is_async_fn,
    sync_compatible,
)
from prefect.utilities.callables import (
    collapse_variadic_parameters,
    explode_variadic_parameter,
    get_parameter_defaults,
    parameters_to_args_kwargs,
)
from prefect.utilities.collections import StopVisiting, isiterable, visit_collection
from prefect.utilities.pydantic import PartialModel
from prefect.utilities.text import truncated_to

R = TypeVar("R")
EngineReturnType = Literal["future", "state", "result"]


API_HEALTHCHECKS = {}
UNTRACKABLE_TYPES = {bool, type(None), type(...), type(NotImplemented)}
engine_logger = get_logger("engine")


def enter_flow_run_engine_from_flow_call(
    flow: Flow,
    parameters: Dict[str, Any],
    wait_for: Optional[Iterable[PrefectFuture]],
    return_type: EngineReturnType,
) -> Union[State, Awaitable[State]]:
    """
    Sync entrypoint for flow calls.

    This function does the heavy lifting of ensuring we can get into an async context
    for flow run execution with minimal overhead.
    """
    setup_logging()

    registry = PrefectObjectRegistry.get()
    if registry and registry.block_code_execution:
        engine_logger.warning(
            f"Script loading is in progress, flow {flow.name!r} will not be executed."
            " Consider updating the script to only call the flow if executed"
            f' directly:\n\n\tif __name__ == "__main__":\n\t\t{flow.fn.__name__}()'
        )
        return None

    if TaskRunContext.get():
        raise RuntimeError(
            "Flows cannot be run from within tasks. Did you mean to call this "
            "flow in a flow?"
        )

    parent_flow_run_context = FlowRunContext.get()
    is_subflow_run = parent_flow_run_context is not None

    if wait_for is not None and not is_subflow_run:
        raise ValueError("Only flows run as subflows can wait for dependencies.")

    begin_run = create_call(
        create_and_begin_subflow_run if is_subflow_run else create_then_begin_flow_run,
        flow=flow,
        parameters=parameters,
        wait_for=wait_for,
        return_type=return_type,
        client=parent_flow_run_context.client if is_subflow_run else None,
        user_thread=threading.current_thread(),
    )

    # On completion of root flows, wait for the global thread to ensure that
    # any work there is complete
    done_callbacks = (
        [create_call(wait_for_global_loop_exit)] if not is_subflow_run else None
    )

    # WARNING: You must define any context managers here to pass to our concurrency
    # api instead of entering them in here in the engine entrypoint. Otherwise, async
    # flows will not use the context as this function _exits_ to return an awaitable to
    # the user. Generally, you should enter contexts _within_ the async `begin_run`
    # instead but if you need to enter a context from the main thread you'll need to do
    # it here.
    contexts = [capture_sigterm()]

    if flow.isasync and (
        not is_subflow_run or (is_subflow_run and parent_flow_run_context.flow.isasync)
    ):
        # return a coro for the user to await if the flow is async
        # unless it is an async subflow called in a sync flow
        retval = from_async.wait_for_call_in_loop_thread(
            begin_run,
            done_callbacks=done_callbacks,
            contexts=contexts,
        )

    else:
        retval = from_sync.wait_for_call_in_loop_thread(
            begin_run,
            done_callbacks=done_callbacks,
            contexts=contexts,
        )

    return retval


def enter_flow_run_engine_from_subprocess(flow_run_id: UUID) -> State:
    """
    Sync entrypoint for flow runs that have been submitted for execution by an agent

    Differs from `enter_flow_run_engine_from_flow_call` in that we have a flow run id
    but not a flow object. The flow must be retrieved before execution can begin.
    Additionally, this assumes that the caller is always in a context without an event
    loop as this should be called from a fresh process.
    """

    # Ensure collections are imported and have the opportunity to register types before
    # loading the user code from the deployment
    prefect.plugins.load_prefect_collections()

    setup_logging()

    state = from_sync.wait_for_call_in_loop_thread(
        create_call(
            retrieve_flow_then_begin_flow_run,
            flow_run_id,
            user_thread=threading.current_thread(),
        ),
        contexts=[capture_sigterm()],
    )

    APILogHandler.flush()
    return state


@inject_client
async def create_then_begin_flow_run(
    flow: Flow,
    parameters: Dict[str, Any],
    wait_for: Optional[Iterable[PrefectFuture]],
    return_type: EngineReturnType,
    client: PrefectClient,
    user_thread: threading.Thread,
) -> Any:
    """
    Async entrypoint for flow calls

    Creates the flow run in the backend, then enters the main flow run engine.
    """
    # TODO: Returns a `State` depending on `return_type` and we can add an overload to
    #       the function signature to clarify this eventually.

    await check_api_reachable(client, "Cannot create flow run")

    state = Pending()
    if flow.should_validate_parameters:
        try:
            parameters = flow.validate_parameters(parameters)
        except Exception:
            state = await exception_to_failed_state(
                message="Validation of flow parameters failed with error:"
            )

    flow_run = await client.create_flow_run(
        flow,
        # Send serialized parameters to the backend
        parameters=flow.serialize_parameters(parameters),
        state=state,
        tags=TagsContext.get().current_tags,
    )

    engine_logger.info(f"Created flow run {flow_run.name!r} for flow {flow.name!r}")

    logger = flow_run_logger(flow_run, flow)

    ui_url = PREFECT_UI_URL.value()
    if ui_url:
        logger.info(
            f"View at {ui_url}/flow-runs/flow-run/{flow_run.id}",
            extra={"send_to_api": False},
        )

    if state.is_failed():
        logger.error(state.message)
        engine_logger.info(
            f"Flow run {flow_run.name!r} received invalid parameters and is marked as"
            " failed."
        )
    else:
        state = await begin_flow_run(
            flow=flow,
            flow_run=flow_run,
            parameters=parameters,
            client=client,
            user_thread=user_thread,
        )

    if return_type == "state":
        return state
    elif return_type == "result":
        return await state.result(fetch=True)
    else:
        raise ValueError(f"Invalid return type for flow engine {return_type!r}.")


@inject_client
async def retrieve_flow_then_begin_flow_run(
    flow_run_id: UUID,
    client: PrefectClient,
    user_thread: threading.Thread,
) -> State:
    """
    Async entrypoint for flow runs that have been submitted for execution by an agent

    - Retrieves the deployment information
    - Loads the flow object using deployment information
    - Updates the flow run version
    """
    flow_run = await client.read_flow_run(flow_run_id)
    try:
        flow = await load_flow_from_flow_run(flow_run, client=client)
    except Exception:
        message = "Flow could not be retrieved from deployment."
        flow_run_logger(flow_run).exception(message)
        state = await exception_to_failed_state(message=message)
        await client.set_flow_run_state(
            state=state, flow_run_id=flow_run_id, force=True
        )
        return state

    # Update the flow run policy defaults to match settings on the flow
    # Note: Mutating the flow run object prevents us from performing another read
    #       operation if these properties are used by the client downstream
    if flow_run.empirical_policy.retry_delay is None:
        flow_run.empirical_policy.retry_delay = flow.retry_delay_seconds

    if flow_run.empirical_policy.retries is None:
        flow_run.empirical_policy.retries = flow.retries

    await client.update_flow_run(
        flow_run_id=flow_run_id,
        flow_version=flow.version,
        empirical_policy=flow_run.empirical_policy,
    )

    if flow.should_validate_parameters:
        failed_state = None
        try:
            parameters = flow.validate_parameters(flow_run.parameters)
        except Exception:
            message = "Validation of flow parameters failed with error: "
            flow_run_logger(flow_run).exception(message)
            failed_state = await exception_to_failed_state(message=message)

        if failed_state is not None:
            await propose_state(
                client,
                state=failed_state,
                flow_run_id=flow_run_id,
            )
            return failed_state
    else:
        parameters = flow_run.parameters

    # Ensure default values are populated
    parameters = {**get_parameter_defaults(flow.fn), **parameters}

    return await begin_flow_run(
        flow=flow,
        flow_run=flow_run,
        parameters=parameters,
        client=client,
        user_thread=user_thread,
    )


async def begin_flow_run(
    flow: Flow,
    flow_run: FlowRun,
    parameters: Dict[str, Any],
    client: PrefectClient,
    user_thread: threading.Thread,
) -> State:
    """
    Begins execution of a flow run; blocks until completion of the flow run

    - Starts a task runner
    - Determines the result storage block to use
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

    log_prints = should_log_prints(flow)
    flow_run_context = PartialModel(FlowRunContext, log_prints=log_prints)

    async with AsyncExitStack() as stack:
        await stack.enter_async_context(
            report_flow_run_crashes(flow_run=flow_run, client=client, flow=flow)
        )

        # Create a task group for background tasks
        flow_run_context.background_tasks = await stack.enter_async_context(
            anyio.create_task_group()
        )

        # If the flow is async, we need to provide a portal so sync tasks can run
        flow_run_context.sync_portal = (
            stack.enter_context(start_blocking_portal()) if flow.isasync else None
        )

        task_runner = flow.task_runner.duplicate()
        if task_runner is NotImplemented:
            # Backwards compatibility; will not support concurrent flow runs
            task_runner = flow.task_runner
            logger.warning(
                f"Task runner {type(task_runner).__name__!r} does not implement the"
                " `duplicate` method and will fail if used for concurrent execution of"
                " the same flow."
            )

        logger.debug(
            f"Starting {type(flow.task_runner).__name__!r}; submitted tasks "
            f"will be run {CONCURRENCY_MESSAGES[flow.task_runner.concurrency_type]}..."
        )

        flow_run_context.task_runner = await stack.enter_async_context(
            task_runner.start()
        )

        flow_run_context.result_factory = await ResultFactory.from_flow(
            flow, client=client
        )

        if log_prints:
            stack.enter_context(patch_print())

        terminal_or_paused_state = await orchestrate_flow_run(
            flow,
            flow_run=flow_run,
            parameters=parameters,
            wait_for=None,
            client=client,
            partial_flow_run_context=flow_run_context,
            # Orchestration needs to be interruptible if it has a timeout
            interruptible=flow.timeout_seconds is not None,
            user_thread=user_thread,
        )

    if terminal_or_paused_state.is_paused():
        timeout = terminal_or_paused_state.state_details.pause_timeout
        logger.log(
            level=logging.INFO,
            msg=(
                "Currently paused and suspending execution. Resume before"
                f" {timeout.to_rfc3339_string()} to finish execution."
            ),
        )
        await APILogHandler.aflush()

        return terminal_or_paused_state
    else:
        terminal_state = terminal_or_paused_state

    # If debugging, use the more complete `repr` than the usual `str` description
    display_state = repr(terminal_state) if PREFECT_DEBUG_MODE else str(terminal_state)

    logger.log(
        level=logging.INFO if terminal_state.is_completed() else logging.ERROR,
        msg=f"Finished in state {display_state}",
    )

    # When a "root" flow run finishes, flush logs so we do not have to rely on handling
    # during interpreter shutdown
    await APILogHandler.aflush()

    return terminal_state


@inject_client
async def create_and_begin_subflow_run(
    flow: Flow,
    parameters: Dict[str, Any],
    wait_for: Optional[Iterable[PrefectFuture]],
    return_type: EngineReturnType,
    client: PrefectClient,
    user_thread: threading.Thread,
) -> Any:
    """
    Async entrypoint for flows calls within a flow run

    Subflows differ from parent flows in that they
    - Resolve futures in passed parameters into values
    - Create a dummy task for representation in the parent flow
    - Retrieve default result storage from the parent flow rather than the server

    Returns:
        The final state of the run
    """
    parent_flow_run_context = FlowRunContext.get()
    parent_logger = get_run_logger(parent_flow_run_context)
    log_prints = should_log_prints(flow)
    terminal_state = None

    parent_logger.debug(f"Resolving inputs to {flow.name!r}")
    task_inputs = {k: await collect_task_run_inputs(v) for k, v in parameters.items()}

    if wait_for:
        task_inputs["wait_for"] = await collect_task_run_inputs(wait_for)

    rerunning = parent_flow_run_context.flow_run.run_count > 1

    # Generate a task in the parent flow run to represent the result of the subflow run
    dummy_task = Task(name=flow.name, fn=flow.fn, version=flow.version)
    parent_task_run = await client.create_task_run(
        task=dummy_task,
        flow_run_id=parent_flow_run_context.flow_run.id,
        dynamic_key=_dynamic_key_for_task_run(parent_flow_run_context, dummy_task),
        task_inputs=task_inputs,
        state=Pending(),
    )

    # Resolve any task futures in the input
    parameters = await resolve_inputs(parameters)

    if parent_task_run.state.is_final() and not (
        rerunning and not parent_task_run.state.is_completed()
    ):
        # Retrieve the most recent flow run from the database
        flow_runs = await client.read_flow_runs(
            flow_run_filter=FlowRunFilter(
                parent_task_run_id={"any_": [parent_task_run.id]}
            ),
            sort=FlowRunSort.EXPECTED_START_TIME_ASC,
        )
        flow_run = flow_runs[-1]

        # Set up variables required downstream
        terminal_state = flow_run.state
        logger = flow_run_logger(flow_run, flow)

    else:
        flow_run = await client.create_flow_run(
            flow,
            parameters=flow.serialize_parameters(parameters),
            parent_task_run_id=parent_task_run.id,
            state=parent_task_run.state if not rerunning else Pending(),
            tags=TagsContext.get().current_tags,
        )

        parent_logger.info(
            f"Created subflow run {flow_run.name!r} for flow {flow.name!r}"
        )

        logger = flow_run_logger(flow_run, flow)
        ui_url = PREFECT_UI_URL.value()
        if ui_url:
            logger.info(
                f"View at {ui_url}/flow-runs/flow-run/{flow_run.id}",
                extra={"send_to_api": False},
            )

        result_factory = await ResultFactory.from_flow(
            flow, client=parent_flow_run_context.client
        )

        if flow.should_validate_parameters:
            try:
                parameters = flow.validate_parameters(parameters)
            except Exception:
                message = "Validation of flow parameters failed with error:"
                logger.exception(message)
                terminal_state = await propose_state(
                    client,
                    state=await exception_to_failed_state(
                        message=message, result_factory=result_factory
                    ),
                    flow_run_id=flow_run.id,
                )

        if terminal_state is None or not terminal_state.is_final():
            async with AsyncExitStack() as stack:
                await stack.enter_async_context(
                    report_flow_run_crashes(flow_run=flow_run, client=client, flow=flow)
                )

                task_runner = flow.task_runner.duplicate()
                if task_runner is NotImplemented:
                    # Backwards compatibility; will not support concurrent flow runs
                    task_runner = flow.task_runner
                    logger.warning(
                        f"Task runner {type(task_runner).__name__!r} does not implement"
                        " the `duplicate` method and will fail if used for concurrent"
                        " execution of the same flow."
                    )

                await stack.enter_async_context(task_runner.start())

                if log_prints:
                    stack.enter_context(patch_print())

                terminal_state = await orchestrate_flow_run(
                    flow,
                    flow_run=flow_run,
                    parameters=parameters,
                    wait_for=wait_for,
                    # If the parent flow run has a timeout, then this one needs to be
                    # interruptible as well
                    interruptible=parent_flow_run_context.timeout_scope is not None,
                    client=client,
                    partial_flow_run_context=PartialModel(
                        FlowRunContext,
                        sync_portal=parent_flow_run_context.sync_portal,
                        task_runner=task_runner,
                        background_tasks=parent_flow_run_context.background_tasks,
                        result_factory=result_factory,
                        log_prints=log_prints,
                    ),
                    user_thread=user_thread,
                )

    # Display the full state (including the result) if debugging
    display_state = repr(terminal_state) if PREFECT_DEBUG_MODE else str(terminal_state)
    logger.log(
        level=logging.INFO if terminal_state.is_completed() else logging.ERROR,
        msg=f"Finished in state {display_state}",
    )

    # Track the subflow state so the parent flow can use it to determine its final state
    parent_flow_run_context.flow_run_states.append(terminal_state)

    if return_type == "state":
        return terminal_state
    elif return_type == "result":
        return await terminal_state.result(fetch=True)
    else:
        raise ValueError(f"Invalid return type for flow engine {return_type!r}.")


async def orchestrate_flow_run(
    flow: Flow,
    flow_run: FlowRun,
    parameters: Dict[str, Any],
    wait_for: Optional[Iterable[PrefectFuture]],
    interruptible: bool,
    client: PrefectClient,
    partial_flow_run_context: PartialModel[FlowRunContext],
    user_thread: threading.Thread,
) -> State:
    """
    Executes a flow run.

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

    flow_run_context = None
    parent_flow_run_context = FlowRunContext.get()

    try:
        # Resolve futures in any non-data dependencies to ensure they are ready
        if wait_for is not None:
            await resolve_inputs({"wait_for": wait_for}, return_data=False)
    except UpstreamTaskError as upstream_exc:
        return await propose_state(
            client,
            Pending(name="NotReady", message=str(upstream_exc)),
            flow_run_id=flow_run.id,
            # if orchestrating a run already in a pending state, force orchestration to
            # update the state name
            force=flow_run.state.is_pending(),
        )

    state = await propose_state(client, Running(), flow_run_id=flow_run.id)

    # flag to ensure we only update the flow run name once
    run_name_set = False

    while state.is_running():
        waited_for_task_runs = False

        # Update the flow run to the latest data
        flow_run = await client.read_flow_run(flow_run.id)
        try:
            with partial_flow_run_context.finalize(
                flow=flow,
                flow_run=flow_run,
                client=client,
                parameters=parameters,
            ) as flow_run_context:
                # update flow run name
                if not run_name_set and flow.flow_run_name:
                    flow_run_name = _resolve_custom_flow_run_name(
                        flow=flow, parameters=parameters
                    )

                    await client.update_flow_run(
                        flow_run_id=flow_run.id, name=flow_run_name
                    )
                    logger.extra["flow_run_name"] = flow_run_name
                    logger.debug(
                        f"Renamed flow run {flow_run.name!r} to {flow_run_name!r}"
                    )
                    flow_run.name = flow_run_name
                    run_name_set = True

                args, kwargs = parameters_to_args_kwargs(flow.fn, parameters)
                logger.debug(
                    f"Executing flow {flow.name!r} for flow run {flow_run.name!r}..."
                )

                if PREFECT_DEBUG_MODE:
                    logger.debug(f"Executing {call_repr(flow.fn, *args, **kwargs)}")
                else:
                    logger.debug(
                        "Beginning execution...", extra={"state_message": True}
                    )

                flow_call = create_call(flow.fn, *args, **kwargs)

                # This check for a parent call is needed for cases where the engine
                # was entered directly during testing
                parent_call = get_current_call()

                if parent_call and (
                    not parent_flow_run_context
                    or (
                        parent_flow_run_context
                        and parent_flow_run_context.flow.isasync == flow.isasync
                    )
                ):
                    from_async.call_soon_in_waiting_thread(
                        flow_call, thread=user_thread, timeout=flow.timeout_seconds
                    )
                else:
                    from_async.call_soon_in_new_thread(
                        flow_call, timeout=flow.timeout_seconds
                    )

                result = await flow_call.aresult()

                waited_for_task_runs = await wait_for_task_runs_and_report_crashes(
                    flow_run_context.task_run_futures, client=client
                )
        except PausedRun:
            paused_flow_run = await client.read_flow_run(flow_run.id)
            paused_flow_run_state = paused_flow_run.state
            return paused_flow_run_state
        except CancelledError as exc:
            if not flow_call.timedout():
                # If the flow call was not cancelled by us; this is a crash
                raise
            # Construct a new exception as `TimeoutError`
            original = exc
            exc = TimeoutError()
            exc.__cause__ = original
            logger.exception("Encountered exception during execution:")
            terminal_state = await exception_to_failed_state(
                exc,
                message=f"Flow run exceeded timeout of {flow.timeout_seconds} seconds",
                result_factory=flow_run_context.result_factory,
                name="TimedOut",
            )
        except Exception:
            # Generic exception in user code
            logger.exception("Encountered exception during execution:")
            terminal_state = await exception_to_failed_state(
                message="Flow run encountered an exception.",
                result_factory=flow_run_context.result_factory,
            )
        else:
            if result is None:
                # All tasks and subflows are reference tasks if there is no return value
                # If there are no tasks, use `None` instead of an empty iterable
                result = (
                    flow_run_context.task_run_futures
                    + flow_run_context.task_run_states
                    + flow_run_context.flow_run_states
                ) or None

            terminal_state = await return_value_to_state(
                await resolve_futures_to_states(result),
                result_factory=flow_run_context.result_factory,
            )

        if not waited_for_task_runs:
            # An exception occured that prevented us from waiting for task runs to
            # complete. Ensure that we wait for them before proposing a final state
            # for the flow run.
            await wait_for_task_runs_and_report_crashes(
                flow_run_context.task_run_futures, client=client
            )

        # Before setting the flow run state, store state.data using
        # block storage and send the resulting data document to the Prefect API instead.
        # This prevents the pickled return value of flow runs
        # from being sent to the Prefect API and stored in the Prefect database.
        # state.data is left as is, otherwise we would have to load
        # the data from block storage again after storing.
        state = await propose_state(
            client,
            state=terminal_state,
            flow_run_id=flow_run.id,
        )

        await _run_flow_hooks(flow=flow, flow_run=flow_run, state=state)

        if state.type != terminal_state.type and PREFECT_DEBUG_MODE:
            logger.debug(
                (
                    f"Received new state {state} when proposing final state"
                    f" {terminal_state}"
                ),
                extra={"send_to_api": False},
            )

        if not state.is_final():
            logger.info(
                (
                    f"Received non-final state {state.name!r} when proposing final"
                    f" state {terminal_state.name!r} and will attempt to run again..."
                ),
                extra={"send_to_api": False},
            )
            # Attempt to enter a running state again
            state = await propose_state(client, Running(), flow_run_id=flow_run.id)

    return state


@sync_compatible
async def pause_flow_run(
    flow_run_id: UUID = None,
    timeout: int = 300,
    poll_interval: int = 10,
    reschedule: bool = False,
    key: str = None,
):
    """
    Pauses the current flow run by stopping execution until resumed.

    When called within a flow run, execution will block and no downstream tasks will
    run until the flow is resumed. Task runs that have already started will continue
    running. A timeout parameter can be passed that will fail the flow run if it has not
    been resumed within the specified time.

    Args:
        flow_run_id: a flow run id. If supplied, this function will attempt to pause
            the specified flow run outside of the flow run process. When paused, the
            flow run will continue execution until the NEXT task is orchestrated, at
            which point the flow will exit. Any tasks that have already started will
            run until completion. When resumed, the flow run will be rescheduled to
            finish execution. In order pause a flow run in this way, the flow needs to
            have an associated deployment and results need to be configured with the
            `persist_results` option.
        timeout: the number of seconds to wait for the flow to be resumed before
            failing. Defaults to 5 minutes (300 seconds). If the pause timeout exceeds
            any configured flow-level timeout, the flow might fail even after resuming.
        poll_interval: The number of seconds between checking whether the flow has been
            resumed. Defaults to 10 seconds.
        reschedule: Flag that will reschedule the flow run if resumed. Instead of
            blocking execution, the flow will gracefully exit (with no result returned)
            instead. To use this flag, a flow needs to have an associated deployment and
            results need to be configured with the `persist_results` option.
        key: An optional key to prevent calling pauses more than once. This defaults to
            the number of pauses observed by the flow so far, and prevents pauses that
            use the "reschedule" option from running the same pause twice. A custom key
            can be supplied for custom pausing behavior.
    """
    if flow_run_id:
        return await _out_of_process_pause(
            flow_run_id=flow_run_id,
            timeout=timeout,
            reschedule=reschedule,
            key=key,
        )
    else:
        return await _in_process_pause(
            timeout=timeout, poll_interval=poll_interval, reschedule=reschedule, key=key
        )


@inject_client
async def _in_process_pause(
    timeout: int = 300,
    poll_interval: int = 10,
    reschedule=False,
    key: str = None,
    client=None,
):
    if TaskRunContext.get():
        raise RuntimeError("Cannot pause task runs.")

    context = FlowRunContext.get()
    if not context:
        raise RuntimeError("Flow runs can only be paused from within a flow run.")

    logger = get_run_logger(context=context)

    pause_counter = _observed_flow_pauses(context)
    pause_key = key or str(pause_counter)

    logger.info("Pausing flow, execution will continue when this flow run is resumed.")

    try:
        state = await propose_state(
            client=client,
            state=Paused(
                timeout_seconds=timeout, reschedule=reschedule, pause_key=pause_key
            ),
            flow_run_id=context.flow_run.id,
        )
    except Abort as exc:
        # Aborted pause requests mean the pause is not allowed
        raise RuntimeError(f"Flow run cannot be paused: {exc}")

    if state.is_running():
        # The orchestrator requests that this pause be ignored
        return

    if not state.is_paused():
        # If we receive anything but a PAUSED state, we are unable to continue
        raise RuntimeError(
            f"Flow run cannot be paused. Received non-paused state from API: {state}"
        )

    if reschedule:
        # If a rescheduled pause, exit this process so the run can be resubmitted later
        raise Pause()

    # Otherwise, block and check for completion on an interval
    with anyio.move_on_after(timeout):
        # attempt to check if a flow has resumed at least once
        initial_sleep = min(timeout / 2, poll_interval)
        await anyio.sleep(initial_sleep)
        flow_run = await client.read_flow_run(context.flow_run.id)
        if flow_run.state.is_running():
            logger.info("Resuming flow run execution!")
            return

        while True:
            await anyio.sleep(poll_interval)
            flow_run = await client.read_flow_run(context.flow_run.id)
            if flow_run.state.is_running():
                logger.info("Resuming flow run execution!")
                return

    # check one last time before failing the flow
    flow_run = await client.read_flow_run(context.flow_run.id)
    if flow_run.state.is_running():
        logger.info("Resuming flow run execution!")
        return

    raise FlowPauseTimeout("Flow run was paused and never resumed.")


@inject_client
async def _out_of_process_pause(
    flow_run_id: UUID,
    timeout: int = 300,
    reschedule: bool = True,
    key: str = None,
    client=None,
):
    if reschedule:
        raise RuntimeError(
            "Pausing a flow run out of process requires the `reschedule` option set to"
            " True."
        )

    response = await client.set_flow_run_state(
        flow_run_id,
        Paused(timeout_seconds=timeout, reschedule=True, pause_key=key),
    )
    if response.status != SetStateStatus.ACCEPT:
        raise RuntimeError(response.details.reason)


@sync_compatible
async def resume_flow_run(flow_run_id):
    """
    Resumes a paused flow.

    Args:
        flow_run_id: the flow_run_id to resume
    """
    client = get_client()
    flow_run = await client.read_flow_run(flow_run_id)

    if not flow_run.state.is_paused():
        raise NotPausedError("Cannot resume a run that isn't paused!")

    response = await client.resume_flow_run(flow_run_id)

    if response.status == SetStateStatus.REJECT:
        if response.state.type == StateType.FAILED:
            raise FlowPauseTimeout("Flow run can no longer be resumed.")
        else:
            raise RuntimeError(f"Cannot resume this run: {response.details.reason}")


def enter_task_run_engine(
    task: Task,
    parameters: Dict[str, Any],
    wait_for: Optional[Iterable[PrefectFuture]],
    return_type: EngineReturnType,
    task_runner: Optional[BaseTaskRunner],
    mapped: bool,
) -> Union[PrefectFuture, Awaitable[PrefectFuture]]:
    """
    Sync entrypoint for task calls
    """

    flow_run_context = FlowRunContext.get()
    if not flow_run_context:
        raise RuntimeError(
            "Tasks cannot be run outside of a flow. To call the underlying task"
            " function outside of a flow use `task.fn()`."
        )

    if TaskRunContext.get():
        raise RuntimeError(
            "Tasks cannot be run from within tasks. Did you mean to call this "
            "task in a flow?"
        )

    if flow_run_context.timeout_scope and flow_run_context.timeout_scope.cancel_called:
        raise TimeoutError("Flow run timed out")

    begin_run = create_call(
        begin_task_map if mapped else get_task_call_return_value,
        task=task,
        flow_run_context=flow_run_context,
        parameters=parameters,
        wait_for=wait_for,
        return_type=return_type,
        task_runner=task_runner,
    )

    if task.isasync and flow_run_context.flow.isasync:
        # return a coro for the user to await if an async task in an async flow
        return from_async.wait_for_call_in_loop_thread(begin_run)
    else:
        return from_sync.wait_for_call_in_loop_thread(begin_run)


async def begin_task_map(
    task: Task,
    flow_run_context: FlowRunContext,
    parameters: Dict[str, Any],
    wait_for: Optional[Iterable[PrefectFuture]],
    return_type: EngineReturnType,
    task_runner: Optional[BaseTaskRunner],
) -> List[Union[PrefectFuture, Awaitable[PrefectFuture]]]:
    """Async entrypoint for task mapping"""
    # We need to resolve some futures to map over their data, collect the upstream
    # links beforehand to retain relationship tracking.
    task_inputs = {
        k: await collect_task_run_inputs(v, max_depth=0) for k, v in parameters.items()
    }

    # Resolve the top-level parameters in order to get mappable data of a known length.
    # Nested parameters will be resolved in each mapped child where their relationships
    # will also be tracked.
    parameters = await resolve_inputs(parameters, max_depth=1)

    # Ensure that any parameters in kwargs are expanded before this check
    parameters = explode_variadic_parameter(task.fn, parameters)

    iterable_parameters = {}
    static_parameters = {}
    annotated_parameters = {}
    for key, val in parameters.items():
        if isinstance(val, (allow_failure, quote)):
            # Unwrap annotated parameters to determine if they are iterable
            annotated_parameters[key] = val
            val = val.unwrap()

        if isinstance(val, unmapped):
            static_parameters[key] = val.value
        elif isiterable(val):
            iterable_parameters[key] = list(val)
        else:
            static_parameters[key] = val

    if not len(iterable_parameters):
        raise MappingMissingIterable(
            "No iterable parameters were received. Parameters for map must "
            f"include at least one iterable. Parameters: {parameters}"
        )

    iterable_parameter_lengths = {
        key: len(val) for key, val in iterable_parameters.items()
    }
    lengths = set(iterable_parameter_lengths.values())
    if len(lengths) > 1:
        raise MappingLengthMismatch(
            "Received iterable parameters with different lengths. Parameters for map"
            f" must all be the same length. Got lengths: {iterable_parameter_lengths}"
        )

    map_length = list(lengths)[0]

    task_runs = []
    for i in range(map_length):
        call_parameters = {key: value[i] for key, value in iterable_parameters.items()}
        call_parameters.update({key: value for key, value in static_parameters.items()})

        # Add default values for parameters; these are skipped earlier since they should
        # not be mapped over
        for key, value in get_parameter_defaults(task.fn).items():
            call_parameters.setdefault(key, value)

        # Re-apply annotations to each key again
        for key, annotation in annotated_parameters.items():
            call_parameters[key] = annotation.rewrap(call_parameters[key])

        # Collapse any previously exploded kwargs
        call_parameters = collapse_variadic_parameters(task.fn, call_parameters)

        task_runs.append(
            partial(
                get_task_call_return_value,
                task=task,
                flow_run_context=flow_run_context,
                parameters=call_parameters,
                wait_for=wait_for,
                return_type=return_type,
                task_runner=task_runner,
                extra_task_inputs=task_inputs,
            )
        )

    # Maintain the order of the task runs when using the sequential task runner
    runner = task_runner if task_runner else flow_run_context.task_runner
    if runner.concurrency_type == TaskConcurrencyType.SEQUENTIAL:
        return [await task_run() for task_run in task_runs]

    return await gather(*task_runs)


async def collect_task_run_inputs(expr: Any, max_depth: int = -1) -> Set[TaskRunInput]:
    """
    This function recurses through an expression to generate a set of any discernable
    task run inputs it finds in the data structure. It produces a set of all inputs
    found.

    Examples:
        >>> task_inputs = {
        >>>    k: await collect_task_run_inputs(v) for k, v in parameters.items()
        >>> }
    """
    # TODO: This function needs to be updated to detect parameters and constants

    inputs = set()
    futures = set()

    def add_futures_and_states_to_inputs(obj):
        if isinstance(obj, PrefectFuture):
            # We need to wait for futures to be submitted before we can get the task
            # run id but we want to do so asynchronously
            futures.add(obj)
        elif is_state(obj):
            if obj.state_details.task_run_id:
                inputs.add(TaskRunResult(id=obj.state_details.task_run_id))
        else:
            state = get_state_for_result(obj)
            if state and state.state_details.task_run_id:
                inputs.add(TaskRunResult(id=state.state_details.task_run_id))

    visit_collection(
        expr,
        visit_fn=add_futures_and_states_to_inputs,
        return_data=False,
        max_depth=max_depth,
    )

    await asyncio.gather(*[future._wait_for_submission() for future in futures])
    for future in futures:
        inputs.add(TaskRunResult(id=future.task_run.id))

    return inputs


async def get_task_call_return_value(
    task: Task,
    flow_run_context: FlowRunContext,
    parameters: Dict[str, Any],
    wait_for: Optional[Iterable[PrefectFuture]],
    return_type: EngineReturnType,
    task_runner: Optional[BaseTaskRunner],
    extra_task_inputs: Optional[Dict[str, Set[TaskRunInput]]] = None,
):
    extra_task_inputs = extra_task_inputs or {}

    future = await create_task_run_future(
        task=task,
        flow_run_context=flow_run_context,
        parameters=parameters,
        wait_for=wait_for,
        task_runner=task_runner,
        extra_task_inputs=extra_task_inputs,
    )
    if return_type == "future":
        return future
    elif return_type == "state":
        return await future._wait()
    elif return_type == "result":
        return await future._result()
    else:
        raise ValueError(f"Invalid return type for task engine {return_type!r}.")


async def create_task_run_future(
    task: Task,
    flow_run_context: FlowRunContext,
    parameters: Dict[str, Any],
    wait_for: Optional[Iterable[PrefectFuture]],
    task_runner: Optional[BaseTaskRunner],
    extra_task_inputs: Dict[str, Set[TaskRunInput]],
) -> PrefectFuture:
    # Default to the flow run's task runner
    task_runner = task_runner or flow_run_context.task_runner

    # Generate a name for the future
    dynamic_key = _dynamic_key_for_task_run(flow_run_context, task)
    task_run_name = f"{task.name}-{dynamic_key}"

    # Generate a future
    future = PrefectFuture(
        name=task_run_name,
        key=uuid4(),
        task_runner=task_runner,
        asynchronous=task.isasync and flow_run_context.flow.isasync,
    )

    # Create and submit the task run in the background
    flow_run_context.background_tasks.start_soon(
        partial(
            create_task_run_then_submit,
            task=task,
            task_run_name=task_run_name,
            task_run_dynamic_key=dynamic_key,
            future=future,
            flow_run_context=flow_run_context,
            parameters=parameters,
            wait_for=wait_for,
            task_runner=task_runner,
            extra_task_inputs=extra_task_inputs,
        )
    )

    # Track the task run future in the flow run context
    flow_run_context.task_run_futures.append(future)

    if task_runner.concurrency_type == TaskConcurrencyType.SEQUENTIAL:
        await future._wait()

    # Return the future without waiting for task run creation or submission
    return future


async def create_task_run_then_submit(
    task: Task,
    task_run_name: str,
    task_run_dynamic_key: str,
    future: PrefectFuture,
    flow_run_context: FlowRunContext,
    parameters: Dict[str, Any],
    wait_for: Optional[Iterable[PrefectFuture]],
    task_runner: BaseTaskRunner,
    extra_task_inputs: Dict[str, Set[TaskRunInput]],
) -> None:
    task_run = await create_task_run(
        task=task,
        name=task_run_name,
        flow_run_context=flow_run_context,
        parameters=parameters,
        dynamic_key=task_run_dynamic_key,
        wait_for=wait_for,
        extra_task_inputs=extra_task_inputs,
    )

    # Attach the task run to the future to support `get_state` operations
    future.task_run = task_run

    await submit_task_run(
        task=task,
        future=future,
        flow_run_context=flow_run_context,
        parameters=parameters,
        task_run=task_run,
        wait_for=wait_for,
        task_runner=task_runner,
    )

    future._submitted.set()


async def create_task_run(
    task: Task,
    name: str,
    flow_run_context: FlowRunContext,
    parameters: Dict[str, Any],
    dynamic_key: str,
    wait_for: Optional[Iterable[PrefectFuture]],
    extra_task_inputs: Dict[str, Set[TaskRunInput]],
) -> TaskRun:
    task_inputs = {k: await collect_task_run_inputs(v) for k, v in parameters.items()}
    if wait_for:
        task_inputs["wait_for"] = await collect_task_run_inputs(wait_for)

    # Join extra task inputs
    for k, extras in extra_task_inputs.items():
        task_inputs[k] = task_inputs[k].union(extras)

    logger = get_run_logger(flow_run_context)

    task_run = await flow_run_context.client.create_task_run(
        task=task,
        name=name,
        flow_run_id=flow_run_context.flow_run.id,
        dynamic_key=dynamic_key,
        state=Pending(),
        extra_tags=TagsContext.get().current_tags,
        task_inputs=task_inputs,
    )

    logger.info(f"Created task run {task_run.name!r} for task {task.name!r}")

    return task_run


async def submit_task_run(
    task: Task,
    future: PrefectFuture,
    flow_run_context: FlowRunContext,
    parameters: Dict[str, Any],
    task_run: TaskRun,
    wait_for: Optional[Iterable[PrefectFuture]],
    task_runner: BaseTaskRunner,
) -> PrefectFuture:
    logger = get_run_logger(flow_run_context)

    if task_runner.concurrency_type == TaskConcurrencyType.SEQUENTIAL:
        logger.info(f"Executing {task_run.name!r} immediately...")

    future = await task_runner.submit(
        key=future.key,
        call=partial(
            begin_task_run,
            task=task,
            task_run=task_run,
            parameters=parameters,
            wait_for=wait_for,
            result_factory=await ResultFactory.from_task(
                task, client=flow_run_context.client
            ),
            log_prints=should_log_prints(task),
            settings=prefect.context.SettingsContext.get().copy(),
        ),
    )

    if task_runner.concurrency_type != TaskConcurrencyType.SEQUENTIAL:
        logger.info(f"Submitted task run {task_run.name!r} for execution.")

    return future


async def begin_task_run(
    task: Task,
    task_run: TaskRun,
    parameters: Dict[str, Any],
    wait_for: Optional[Iterable[PrefectFuture]],
    result_factory: ResultFactory,
    log_prints: bool,
    settings: prefect.context.SettingsContext,
):
    """
    Entrypoint for task run execution.

    This function is intended for submission to the task runner.

    This method may be called from a worker so we ensure the settings context has been
    entered. For example, with a runner that is executing tasks in the same event loop,
    we will likely not enter the context again because the current context already
    matches:

    main thread:
    --> Flow called with settings A
    --> `begin_task_run` executes same event loop
    --> Profile A matches and is not entered again

    However, with execution on a remote environment, we are going to need to ensure the
    settings for the task run are respected by entering the context:

    main thread:
    --> Flow called with settings A
    --> `begin_task_run` is scheduled on a remote worker, settings A is serialized
    remote worker:
    --> Remote worker imports Prefect (may not occur)
    --> Global settings is loaded with default settings
    --> `begin_task_run` executes on a different event loop than the flow
    --> Current settings is not set or does not match, settings A is entered
    """
    maybe_flow_run_context = prefect.context.FlowRunContext.get()

    async with AsyncExitStack() as stack:
        # The settings context may be null on a remote worker so we use the safe `.get`
        # method and compare it to the settings required for this task run
        if prefect.context.SettingsContext.get() != settings:
            stack.enter_context(settings)
            setup_logging()

        if maybe_flow_run_context:
            # Accessible if on a worker that is running in the same thread as the flow
            client = maybe_flow_run_context.client
            # Only run the task in an interruptible thread if it in the same thread as
            # the flow _and_ the flow run has a timeout attached. If the task is on a
            # worker, the flow run timeout will not be raised in the worker process.
            interruptible = maybe_flow_run_context.timeout_scope is not None
        else:
            # Otherwise, retrieve a new client
            client = await stack.enter_async_context(get_client())
            interruptible = False
            await stack.enter_async_context(anyio.create_task_group())

        await stack.enter_async_context(report_task_run_crashes(task_run, client))

        # TODO: Use the background tasks group to manage logging for this task

        if log_prints:
            stack.enter_context(patch_print())

        await check_api_reachable(
            client, f"Cannot orchestrate task run '{task_run.id}'"
        )
        try:
            state = await orchestrate_task_run(
                task=task,
                task_run=task_run,
                parameters=parameters,
                wait_for=wait_for,
                result_factory=result_factory,
                log_prints=log_prints,
                interruptible=interruptible,
                client=client,
            )

            if not maybe_flow_run_context:
                # When a a task run finishes on a remote worker flush logs to prevent
                # loss if the process exits
                await APILogHandler.aflush()

        except Abort as abort:
            # Task run probably already completed, fetch its state
            task_run = await client.read_task_run(task_run.id)

            if task_run.state.is_final():
                task_run_logger(task_run).info(
                    f"Task run '{task_run.id}' already finished."
                )
            else:
                # TODO: This is a concerning case; we should determine when this occurs
                #       1. This can occur when the flow run is not in a running state
                task_run_logger(task_run).warning(
                    f"Task run '{task_run.id}' received abort during orchestration: "
                    f"{abort} Task run is in {task_run.state.type.value} state."
                )
            state = task_run.state

        except Pause:
            task_run_logger(task_run).info(
                "Task run encountered a pause signal during orchestration."
            )
            state = Paused()

        return state


async def orchestrate_task_run(
    task: Task,
    task_run: TaskRun,
    parameters: Dict[str, Any],
    wait_for: Optional[Iterable[PrefectFuture]],
    result_factory: ResultFactory,
    log_prints: bool,
    interruptible: bool,
    client: PrefectClient,
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
    flow_run = await client.read_flow_run(task_run.flow_run_id)
    logger = task_run_logger(task_run, task=task, flow_run=flow_run)

    partial_task_run_context = PartialModel(
        TaskRunContext,
        task_run=task_run,
        task=task,
        client=client,
        result_factory=result_factory,
        log_prints=log_prints,
    )

    try:
        # Resolve futures in parameters into data
        resolved_parameters = await resolve_inputs(parameters)
        # Resolve futures in any non-data dependencies to ensure they are ready
        await resolve_inputs({"wait_for": wait_for}, return_data=False)
    except UpstreamTaskError as upstream_exc:
        return await propose_state(
            client,
            Pending(name="NotReady", message=str(upstream_exc)),
            task_run_id=task_run.id,
            # if orchestrating a run already in a pending state, force orchestration to
            # update the state name
            force=task_run.state.is_pending(),
        )

    # Generate the cache key to attach to proposed states
    # The cache key uses a TaskRunContext that does not include a `timeout_context``
    cache_key = (
        task.cache_key_fn(
            partial_task_run_context.finalize(parameters=resolved_parameters),
            resolved_parameters,
        )
        if task.cache_key_fn
        else None
    )

    task_run_context = partial_task_run_context.finalize(parameters=resolved_parameters)

    # Ignore the cached results for a cache key, default = false
    # Setting on task level overrules the Prefect setting (env var)
    refresh_cache = (
        task.refresh_cache
        if task.refresh_cache is not None
        else PREFECT_TASKS_REFRESH_CACHE.value()
    )

    # Emit an event to capture that the task run was in the `PENDING` state.
    last_event = _emit_task_run_state_change_event(
        task_run=task_run, initial_state=None, validated_state=task_run.state
    )
    last_state = task_run.state

    # Transition from `PENDING` -> `RUNNING`
    state = await propose_state(
        client,
        Running(
            state_details=StateDetails(cache_key=cache_key, refresh_cache=refresh_cache)
        ),
        task_run_id=task_run.id,
    )

    # Emit an event to capture the result of proposing a `RUNNING` state.
    last_event = _emit_task_run_state_change_event(
        task_run=task_run,
        initial_state=last_state,
        validated_state=state,
        follows=last_event,
    )
    last_state = state

    # flag to ensure we only update the task run name once
    run_name_set = False

    # Only run the task if we enter a `RUNNING` state
    while state.is_running():
        # Retrieve the latest metadata for the task run context
        task_run = await client.read_task_run(task_run.id)

        with task_run_context.copy(
            update={"task_run": task_run, "start_time": pendulum.now("UTC")}
        ):
            try:
                args, kwargs = parameters_to_args_kwargs(task.fn, resolved_parameters)
                # update task run name
                if not run_name_set and task.task_run_name:
                    task_run_name = _resolve_custom_task_run_name(
                        task=task, parameters=resolved_parameters
                    )
                    await client.set_task_run_name(
                        task_run_id=task_run.id, name=task_run_name
                    )
                    logger.extra["task_run_name"] = task_run_name
                    logger.debug(
                        f"Renamed task run {task_run.name!r} to {task_run_name!r}"
                    )
                    task_run.name = task_run_name
                    run_name_set = True

                if PREFECT_DEBUG_MODE.value():
                    logger.debug(f"Executing {call_repr(task.fn, *args, **kwargs)}")
                else:
                    logger.debug(
                        "Beginning execution...", extra={"state_message": True}
                    )

                call = from_async.call_soon_in_new_thread(
                    create_call(task.fn, *args, **kwargs), timeout=task.timeout_seconds
                )
                result = await call.aresult()

            except (CancelledError, asyncio.CancelledError) as exc:
                if not call.timedout():
                    # If the task call was not cancelled by us; this is a crash
                    raise
                # Construct a new exception as `TimeoutError`
                original = exc
                exc = TimeoutError()
                exc.__cause__ = original
                logger.exception("Encountered exception during execution:")
                terminal_state = await exception_to_failed_state(
                    exc,
                    message=(
                        f"Task run exceeded timeout of {task.timeout_seconds} seconds"
                    ),
                    result_factory=task_run_context.result_factory,
                    name="TimedOut",
                )
            except Exception as exc:
                logger.exception("Encountered exception during execution:")
                terminal_state = await exception_to_failed_state(
                    exc,
                    message="Task run encountered an exception",
                    result_factory=task_run_context.result_factory,
                )
            else:
                terminal_state = await return_value_to_state(
                    result,
                    result_factory=task_run_context.result_factory,
                )

                # for COMPLETED tasks, add the cache key and expiration
                if terminal_state.is_completed():
                    terminal_state.state_details.cache_expiration = (
                        (pendulum.now("utc") + task.cache_expiration)
                        if task.cache_expiration
                        else None
                    )
                    terminal_state.state_details.cache_key = cache_key

            state = await propose_state(client, terminal_state, task_run_id=task_run.id)
            last_event = _emit_task_run_state_change_event(
                task_run=task_run,
                initial_state=last_state,
                validated_state=state,
                follows=last_event,
            )
            last_state = state

            await _run_task_hooks(
                task=task,
                task_run=task_run,
                state=state,
            )

            if state.type != terminal_state.type and PREFECT_DEBUG_MODE:
                logger.debug(
                    (
                        f"Received new state {state} when proposing final state"
                        f" {terminal_state}"
                    ),
                    extra={"send_to_api": False},
                )

            if not state.is_final():
                logger.info(
                    (
                        f"Received non-final state {state.name!r} when proposing final"
                        f" state {terminal_state.name!r} and will attempt to run"
                        " again..."
                    ),
                    extra={"send_to_api": False},
                )
                # Attempt to enter a running state again
                state = await propose_state(client, Running(), task_run_id=task_run.id)
                last_event = _emit_task_run_state_change_event(
                    task_run=task_run,
                    initial_state=last_state,
                    validated_state=state,
                    follows=last_event,
                )
                last_state = state

    # If debugging, use the more complete `repr` than the usual `str` description
    display_state = repr(state) if PREFECT_DEBUG_MODE else str(state)

    logger.log(
        level=logging.INFO if state.is_completed() else logging.ERROR,
        msg=f"Finished in state {display_state}",
    )

    return state


async def wait_for_task_runs_and_report_crashes(
    task_run_futures: Iterable[PrefectFuture], client: PrefectClient
) -> Literal[True]:
    crash_exceptions = []

    # Gather states concurrently first
    states = await gather(*(future._wait for future in task_run_futures))

    for future, state in zip(task_run_futures, states):
        logger = task_run_logger(future.task_run)

        if not state.type == StateType.CRASHED:
            continue

        # We use this utility instead of `state.result` for type checking
        exception = await get_state_exception(state)

        task_run = await client.read_task_run(future.task_run.id)
        if not task_run.state.is_crashed():
            logger.info(f"Crash detected! {state.message}")
            logger.debug("Crash details:", exc_info=exception)

            # Update the state of the task run
            result = await client.set_task_run_state(
                task_run_id=future.task_run.id, state=state, force=True
            )
            if result.status == SetStateStatus.ACCEPT:
                engine_logger.debug(
                    f"Reported crashed task run {future.name!r} successfully."
                )
            else:
                engine_logger.warning(
                    f"Failed to report crashed task run {future.name!r}. "
                    f"Orchestrator did not accept state: {result!r}"
                )
        else:
            # Populate the state details on the local state
            future._final_state.state_details = task_run.state.state_details

        crash_exceptions.append(exception)

    # Now that we've finished reporting crashed tasks, reraise any exit exceptions
    for exception in crash_exceptions:
        if isinstance(exception, (KeyboardInterrupt, SystemExit)):
            raise exception

    return True


@contextlib.contextmanager
def capture_sigterm():
    def cancel_flow_run(*args):
        raise TerminationSignal(signal=signal.SIGTERM)

    original_term_handler = None
    try:
        original_term_handler = signal.signal(signal.SIGTERM, cancel_flow_run)
    except ValueError:
        # Signals only work in the main thread
        pass

    try:
        yield
    except TerminationSignal as exc:
        # Termination signals are swapped out during a flow run to perform
        # a graceful shutdown and raise this exception. This `os.kill` call
        # ensures that the previous handler, likely the Python default,
        # gets called as well.
        if original_term_handler is not None:
            signal.signal(exc.signal, original_term_handler)
            os.kill(os.getpid(), exc.signal)

        raise

    finally:
        if original_term_handler is not None:
            signal.signal(signal.SIGTERM, original_term_handler)


@asynccontextmanager
async def report_flow_run_crashes(flow_run: FlowRun, client: PrefectClient, flow: Flow):
    """
    Detect flow run crashes during this context and update the run to a proper final
    state.

    This context _must_ reraise the exception to properly exit the run.
    """

    try:
        yield
    except (Abort, Pause):
        # Do not capture internal signals as crashes
        raise
    except BaseException as exc:
        state = await exception_to_crashed_state(exc)
        logger = flow_run_logger(flow_run)
        with anyio.CancelScope(shield=True):
            logger.error(f"Crash detected! {state.message}")
            logger.debug("Crash details:", exc_info=exc)
            flow_run_state = await propose_state(client, state, flow_run_id=flow_run.id)
            engine_logger.debug(
                f"Reported crashed flow run {flow_run.name!r} successfully!"
            )

            # Only `on_crashed` and `on_cancellation` flow run state change hooks can be called here.
            # We call the hooks after the state change proposal to `CRASHED` is validated
            # or rejected (if it is in a `CANCELLING` state).
            await _run_flow_hooks(
                flow=flow,
                flow_run=flow_run,
                state=flow_run_state,
            )

        # Reraise the exception
        raise


@asynccontextmanager
async def report_task_run_crashes(task_run: TaskRun, client: PrefectClient):
    """
    Detect task run crashes during this context and update the run to a proper final
    state.

    This context _must_ reraise the exception to properly exit the run.
    """
    try:
        yield
    except (Abort, Pause):
        # Do not capture internal signals as crashes
        raise
    except BaseException as exc:
        state = await exception_to_crashed_state(exc)
        logger = task_run_logger(task_run)
        with anyio.CancelScope(shield=True):
            logger.error(f"Crash detected! {state.message}")
            logger.debug("Crash details:", exc_info=exc)
            await client.set_task_run_state(
                state=state,
                task_run_id=task_run.id,
                force=True,
            )
            engine_logger.debug(
                f"Reported crashed task run {task_run.name!r} successfully!"
            )

        # Reraise the exception
        raise


async def resolve_inputs(
    parameters: Dict[str, Any], return_data: bool = True, max_depth: int = -1
) -> Dict[str, Any]:
    """
    Resolve any `Quote`, `PrefectFuture`, or `State` types nested in parameters into
    data.

    Returns:
        A copy of the parameters with resolved data

    Raises:
        UpstreamTaskError: If any of the upstream states are not `COMPLETED`
    """

    futures = set()
    states = set()
    result_by_state = {}

    if not parameters:
        return {}

    def collect_futures_and_states(expr, context):
        # Expressions inside quotes should not be traversed
        if isinstance(context.get("annotation"), quote):
            raise StopVisiting()

        if isinstance(expr, PrefectFuture):
            futures.add(expr)
        if is_state(expr):
            states.add(expr)

        return expr

    visit_collection(
        parameters,
        visit_fn=collect_futures_and_states,
        return_data=False,
        max_depth=max_depth,
        context={},
    )

    # Wait for all futures so we do not block when we retrieve the state in `resolve_input`
    states.update(await asyncio.gather(*[future._wait() for future in futures]))

    # Only retrieve the result if requested as it may be expensive
    if return_data:
        finished_states = [state for state in states if state.is_final()]

        state_results = await asyncio.gather(
            *[
                state.result(raise_on_failure=False, fetch=True)
                for state in finished_states
            ]
        )

        for state, result in zip(finished_states, state_results):
            result_by_state[state] = result

    def resolve_input(expr, context):
        state = None

        # Expressions inside quotes should not be modified
        if isinstance(context.get("annotation"), quote):
            raise StopVisiting()

        if isinstance(expr, PrefectFuture):
            state = expr._final_state
        elif is_state(expr):
            state = expr
        else:
            return expr

        # Do not allow uncompleted upstreams except failures when `allow_failure` has
        # been used
        if not state.is_completed() and not (
            # TODO: Note that the contextual annotation here is only at the current level
            #       if `allow_failure` is used then another annotation is used, this will
            #       incorrectly evaulate to false — to resolve this, we must track all
            #       annotations wrapping the current expression but this is not yet
            #       implemented.
            isinstance(context.get("annotation"), allow_failure)
            and state.is_failed()
        ):
            raise UpstreamTaskError(
                f"Upstream task run '{state.state_details.task_run_id}' did not reach a"
                " 'COMPLETED' state."
            )

        return result_by_state.get(state)

    resolved_parameters = {}
    for parameter, value in parameters.items():
        try:
            resolved_parameters[parameter] = visit_collection(
                value,
                visit_fn=resolve_input,
                return_data=return_data,
                # we're manually going 1 layer deeper here
                max_depth=max_depth - 1,
                remove_annotations=True,
                context={},
            )
        except UpstreamTaskError:
            raise
        except Exception as exc:
            raise PrefectException(
                f"Failed to resolve inputs in parameter {parameter!r}. If your"
                " parameter type is not supported, consider using the `quote`"
                " annotation to skip resolution of inputs."
            ) from exc

    return resolved_parameters


async def propose_state(
    client: PrefectClient,
    state: State,
    force: bool = False,
    task_run_id: UUID = None,
    flow_run_id: UUID = None,
) -> State:
    """
    Propose a new state for a flow run or task run, invoking Prefect orchestration logic.

    If the proposed state is accepted, the provided `state` will be augmented with
     details and returned.

    If the proposed state is rejected, a new state returned by the Prefect API will be
    returned.

    If the proposed state results in a WAIT instruction from the Prefect API, the
    function will sleep and attempt to propose the state again.

    If the proposed state results in an ABORT instruction from the Prefect API, an
    error will be raised.

    Args:
        state: a new state for the task or flow run
        task_run_id: an optional task run id, used when proposing task run states
        flow_run_id: an optional flow run id, used when proposing flow run states

    Returns:
        a [State model][prefect.client.schemas.objects.State] representation of the
            flow or task run state

    Raises:
        ValueError: if neither task_run_id or flow_run_id is provided
        prefect.exceptions.Abort: if an ABORT instruction is received from
            the Prefect API
    """

    # Determine if working with a task run or flow run
    if not task_run_id and not flow_run_id:
        raise ValueError("You must provide either a `task_run_id` or `flow_run_id`")

    # Handle task and sub-flow tracing
    if state.is_final():
        if isinstance(state.data, BaseResult) and state.data.has_cached_object():
            # Avoid fetching the result unless it is cached, otherwise we defeat
            # the purpose of disabling `cache_result_in_memory`
            result = await state.result(raise_on_failure=False, fetch=True)
        else:
            result = state.data

        link_state_to_result(state, result)

    # Handle repeated WAITs in a loop instead of recursively, to avoid
    # reaching max recursion depth in extreme cases.
    async def set_state_and_handle_waits(set_state_func) -> OrchestrationResult:
        response = await set_state_func()
        while response.status == SetStateStatus.WAIT:
            engine_logger.debug(
                f"Received wait instruction for {response.details.delay_seconds}s: "
                f"{response.details.reason}"
            )
            await anyio.sleep(response.details.delay_seconds)
            response = await set_state_func()
        return response

    # Attempt to set the state
    if task_run_id:
        set_state = partial(client.set_task_run_state, task_run_id, state, force=force)
        response = await set_state_and_handle_waits(set_state)
    elif flow_run_id:
        set_state = partial(client.set_flow_run_state, flow_run_id, state, force=force)
        response = await set_state_and_handle_waits(set_state)
    else:
        raise ValueError(
            "Neither flow run id or task run id were provided. At least one must "
            "be given."
        )

    # Parse the response to return the new state
    if response.status == SetStateStatus.ACCEPT:
        # Update the state with the details if provided
        state.id = response.state.id
        state.timestamp = response.state.timestamp
        if response.state.state_details:
            state.state_details = response.state.state_details
        return state

    elif response.status == SetStateStatus.ABORT:
        raise prefect.exceptions.Abort(response.details.reason)

    elif response.status == SetStateStatus.REJECT:
        if response.state.is_paused():
            raise Pause(response.details.reason)
        return response.state

    else:
        raise ValueError(
            f"Received unexpected `SetStateStatus` from server: {response.status!r}"
        )


def _dynamic_key_for_task_run(context: FlowRunContext, task: Task) -> int:
    if task.task_key not in context.task_run_dynamic_keys:
        context.task_run_dynamic_keys[task.task_key] = 0
    else:
        context.task_run_dynamic_keys[task.task_key] += 1

    return context.task_run_dynamic_keys[task.task_key]


def _observed_flow_pauses(context: FlowRunContext) -> int:
    if "counter" not in context.observed_flow_pauses:
        context.observed_flow_pauses["counter"] = 1
    else:
        context.observed_flow_pauses["counter"] += 1
    return context.observed_flow_pauses["counter"]


def get_state_for_result(obj: Any) -> Optional[State]:
    """
    Get the state related to a result object.

    `link_state_to_result` must have been called first.
    """
    flow_run_context = FlowRunContext.get()
    if flow_run_context:
        return flow_run_context.task_run_results.get(id(obj))


def link_state_to_result(state: State, result: Any) -> None:
    """
    Caches a link between a state and a result and its components using
    the `id` of the components to map to the state. The cache is persisted to the
    current flow run context since task relationships are limited to within a flow run.

    This allows dependency tracking to occur when results are passed around.
    Note: Because `id` is used, we cannot cache links between singleton objects.

    We only cache the relationship between components 1-layer deep.
    Example:
        Given the result [1, ["a","b"], ("c",)], the following elements will be
        mapped to the state:
        - [1, ["a","b"], ("c",)]
        - ["a","b"]
        - ("c",)

        Note: the int `1` will not be mapped to the state because it is a singleton.

    Other Notes:
    We do not hash the result because:
    - If changes are made to the object in the flow between task calls, we can still
      track that they are related.
    - Hashing can be expensive.
    - Not all objects are hashable.

    We do not set an attribute, e.g. `__prefect_state__`, on the result because:

    - Mutating user's objects is dangerous.
    - Unrelated equality comparisons can break unexpectedly.
    - The field can be preserved on copy.
    - We cannot set this attribute on Python built-ins.
    """

    flow_run_context = FlowRunContext.get()

    def link_if_trackable(obj: Any) -> None:
        """Track connection between a task run result and its associated state if it has a unique ID.

        We cannot track booleans, Ellipsis, None, NotImplemented, or the integers from -5 to 256
        because they are singletons.

        This function will mutate the State if the object is an untrackable type by setting the value
        for `State.state_details.untrackable_result` to `True`.

        """
        if (type(obj) in UNTRACKABLE_TYPES) or (
            isinstance(obj, int) and (-5 <= obj <= 256)
        ):
            state.state_details.untrackable_result = True
            return
        flow_run_context.task_run_results[id(obj)] = state

    if flow_run_context:
        visit_collection(expr=result, visit_fn=link_if_trackable, max_depth=1)


def should_log_prints(flow_or_task: Union[Flow, Task]) -> bool:
    flow_run_context = FlowRunContext.get()

    if flow_or_task.log_prints is None:
        if flow_run_context:
            return flow_run_context.log_prints
        else:
            return PREFECT_LOGGING_LOG_PRINTS.value()

    return flow_or_task.log_prints


def _resolve_custom_flow_run_name(flow: Flow, parameters: Dict[str, Any]) -> str:
    if callable(flow.flow_run_name):
        flow_run_name = flow.flow_run_name()
        if not isinstance(flow_run_name, str):
            raise TypeError(
                f"Callable {flow.flow_run_name} for 'flow_run_name' returned type"
                f" {type(flow_run_name).__name__} but a string is required."
            )
    elif isinstance(flow.flow_run_name, str):
        flow_run_name = flow.flow_run_name.format(**parameters)
    else:
        raise TypeError(
            "Expected string or callable for 'flow_run_name'; got"
            f" {type(flow.flow_run_name).__name__} instead."
        )

    return flow_run_name


def _resolve_custom_task_run_name(task: Task, parameters: Dict[str, Any]) -> str:
    if callable(task.task_run_name):
        task_run_name = task.task_run_name()
        if not isinstance(task_run_name, str):
            raise TypeError(
                f"Callable {task.task_run_name} for 'task_run_name' returned type"
                f" {type(task_run_name).__name__} but a string is required."
            )
    elif isinstance(task.task_run_name, str):
        task_run_name = task.task_run_name.format(**parameters)
    else:
        raise TypeError(
            "Expected string or callable for 'task_run_name'; got"
            f" {type(task.task_run_name).__name__} instead."
        )

    return task_run_name


async def _run_task_hooks(task: Task, task_run: TaskRun, state: State) -> None:
    """Run the on_failure and on_completion hooks for a task, making sure to
    catch and log any errors that occur.
    """
    hooks = None
    if state.is_failed() and task.on_failure:
        hooks = task.on_failure
    elif state.is_completed() and task.on_completion:
        hooks = task.on_completion

    if hooks:
        logger = task_run_logger(task_run)
        for hook in hooks:
            try:
                logger.info(
                    f"Running hook {hook.__name__!r} in response to entering state"
                    f" {state.name!r}"
                )
                if is_async_fn(hook):
                    await hook(task=task, task_run=task_run, state=state)
                else:
                    await from_async.call_in_new_thread(
                        create_call(hook, task=task, task_run=task_run, state=state)
                    )
            except Exception:
                logger.error(
                    f"An error was encountered while running hook {hook.__name__!r}",
                    exc_info=True,
                )
            else:
                logger.info(f"Hook {hook.__name__!r} finished running successfully")


async def _run_flow_hooks(flow: Flow, flow_run: FlowRun, state: State) -> None:
    """Run the on_failure, on_completion, on_cancellation, and on_crashed hooks for a flow, making sure to
    catch and log any errors that occur.
    """
    hooks = None
    if state.is_failed() and flow.on_failure:
        hooks = flow.on_failure
    elif state.is_completed() and flow.on_completion:
        hooks = flow.on_completion
    elif state.is_cancelling() and flow.on_cancellation:
        hooks = flow.on_cancellation
    elif state.is_crashed() and flow.on_crashed:
        hooks = flow.on_crashed

    if hooks:
        logger = flow_run_logger(flow_run)
        for hook in hooks:
            try:
                logger.info(
                    f"Running hook {hook.__name__!r} in response to entering state"
                    f" {state.name!r}"
                )
                if is_async_fn(hook):
                    await hook(flow=flow, flow_run=flow_run, state=state)
                else:
                    await from_async.call_in_new_thread(
                        create_call(hook, flow=flow, flow_run=flow_run, state=state)
                    )
            except Exception:
                logger.error(
                    f"An error was encountered while running hook {hook.__name__!r}",
                    exc_info=True,
                )
            else:
                logger.info(f"Hook {hook.__name__!r} finished running successfully")


async def check_api_reachable(client: PrefectClient, fail_message: str):
    # Do not perform a healthcheck if it exists and is not expired
    api_url = str(client.api_url)
    if api_url in API_HEALTHCHECKS:
        expires = API_HEALTHCHECKS[api_url]
        if expires > time.monotonic():
            return

    connect_error = await client.api_healthcheck()
    if connect_error:
        raise RuntimeError(
            f"{fail_message}. Failed to reach API at {api_url}."
        ) from connect_error

    # Create a 10 minute cache for the healthy response
    API_HEALTHCHECKS[api_url] = get_deadline(60 * 10)


def _emit_task_run_state_change_event(
    task_run: TaskRun,
    initial_state: Optional[State],
    validated_state: State,
    follows: Optional[Event] = None,
) -> Event:
    state_message_truncation_length = 100_000

    return emit_event(
        id=validated_state.id,
        occurred=validated_state.timestamp,
        event=f"prefect.task-run.{validated_state.name}",
        payload={
            "intended": {
                "from": str(initial_state.type.value) if initial_state else None,
                "to": str(validated_state.type.value) if validated_state else None,
            },
            "initial_state": (
                {
                    "type": str(initial_state.type.value),
                    "name": initial_state.name,
                    "message": truncated_to(
                        state_message_truncation_length, initial_state.message
                    ),
                }
                if initial_state
                else None
            ),
            "validated_state": {
                "type": str(validated_state.type.value),
                "name": validated_state.name,
                "message": truncated_to(
                    state_message_truncation_length, validated_state.message
                ),
            },
        },
        resource={
            "prefect.resource.id": f"prefect.task-run.{task_run.id}",
            "prefect.resource.name": task_run.name,
            "prefect.state-message": truncated_to(
                state_message_truncation_length, validated_state.message
            ),
            "prefect.state-name": validated_state.name or "",
            "prefect.state-timestamp": (
                validated_state.timestamp.isoformat()
                if validated_state and validated_state.timestamp
                else ""
            ),
            "prefect.state-type": str(validated_state.type.value),
        },
        follows=follows,
    )


if __name__ == "__main__":
    try:
        flow_run_id = UUID(
            sys.argv[1] if len(sys.argv) > 1 else os.environ.get("PREFECT__FLOW_RUN_ID")
        )
    except Exception:
        engine_logger.error(
            f"Invalid flow run id. Recieved arguments: {sys.argv}", exc_info=True
        )
        exit(1)

    try:
        enter_flow_run_engine_from_subprocess(flow_run_id)
    except Abort as exc:
        engine_logger.info(
            f"Engine execution of flow run '{flow_run_id}' aborted by orchestrator:"
            f" {exc}"
        )
        exit(0)
    except Pause as exc:
        engine_logger.info(
            f"Engine execution of flow run '{flow_run_id}' is paused: {exc}"
        )
        exit(0)
    except Exception:
        engine_logger.error(
            (
                f"Engine execution of flow run '{flow_run_id}' exited with unexpected "
                "exception"
            ),
            exc_info=True,
        )
        exit(1)
    except BaseException:
        engine_logger.error(
            (
                f"Engine execution of flow run '{flow_run_id}' interrupted by base "
                "exception"
            ),
            exc_info=True,
        )
        # Let the exit code be determined by the base exception type
        raise
