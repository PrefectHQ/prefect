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
import logging
import os
import random
import sys
import threading
import time
from contextlib import AsyncExitStack, asynccontextmanager
from functools import partial
from typing import (
    Any,
    Awaitable,
    Dict,
    Iterable,
    List,
    Optional,
    Set,
    Type,
    TypeVar,
    Union,
    overload,
)
from uuid import UUID, uuid4

import anyio
import pendulum
from anyio.from_thread import start_blocking_portal
from typing_extensions import Literal

import prefect
import prefect.context
import prefect.plugins
from prefect._internal.compatibility.deprecated import (
    deprecated_callable,
    deprecated_parameter,
)
from prefect._internal.compatibility.experimental import experimental_parameter
from prefect._internal.concurrency.api import create_call, from_async, from_sync
from prefect._internal.concurrency.calls import get_current_call
from prefect._internal.concurrency.cancellation import CancelledError
from prefect._internal.concurrency.threads import wait_for_global_loop_exit
from prefect.client.orchestration import PrefectClient, get_client
from prefect.client.schemas import FlowRun, TaskRun
from prefect.client.schemas.filters import FlowRunFilter
from prefect.client.schemas.objects import (
    StateDetails,
    StateType,
    TaskRunInput,
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
from prefect.exceptions import (
    Abort,
    FlowPauseTimeout,
    MappingLengthMismatch,
    MappingMissingIterable,
    NotPausedError,
    Pause,
    PausedRun,
    UpstreamTaskError,
)
from prefect.flows import Flow, load_flow_from_entrypoint
from prefect.futures import PrefectFuture, call_repr, resolve_futures_to_states
from prefect.input import keyset_from_paused_state
from prefect.input.run_input import run_input_subclass_from_type
from prefect.logging.configuration import setup_logging
from prefect.logging.handlers import APILogHandler
from prefect.logging.loggers import (
    flow_run_logger,
    get_logger,
    get_run_logger,
    patch_print,
    task_run_logger,
)
from prefect.results import ResultFactory, UnknownResult
from prefect.settings import (
    PREFECT_DEBUG_MODE,
    PREFECT_EXPERIMENTAL_ENABLE_NEW_ENGINE,
    PREFECT_RUN_ON_COMPLETION_HOOKS_ON_CACHED,
    PREFECT_TASK_INTROSPECTION_WARN_THRESHOLD,
    PREFECT_TASKS_REFRESH_CACHE,
    PREFECT_UI_URL,
)
from prefect.states import (
    Completed,
    Paused,
    Pending,
    Running,
    Scheduled,
    State,
    Suspended,
    exception_to_crashed_state,
    exception_to_failed_state,
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
    run_sync,
    sync_compatible,
)
from prefect.utilities.callables import (
    collapse_variadic_parameters,
    explode_variadic_parameter,
    get_parameter_defaults,
    parameters_to_args_kwargs,
)
from prefect.utilities.collections import isiterable
from prefect.utilities.engine import (
    _dynamic_key_for_task_run,
    _get_hook_name,
    _observed_flow_pauses,
    _resolve_custom_flow_run_name,
    _resolve_custom_task_run_name,
    capture_sigterm,
    check_api_reachable,
    collapse_excgroups,
    collect_task_run_inputs,
    emit_task_run_state_change_event,
    propose_state,
    resolve_inputs,
    should_log_prints,
    wait_for_task_runs_and_report_crashes,
)

R = TypeVar("R")
T = TypeVar("T")
EngineReturnType = Literal["future", "state", "result"]

NUM_CHARS_DYNAMIC_KEY = 8

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
    contexts = [capture_sigterm(), collapse_excgroups()]

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
        contexts=[capture_sigterm(), collapse_excgroups()],
    )

    APILogHandler.flush()
    return state


async def _make_flow_run(
    flow: Flow, parameters: Dict[str, Any], state: State, client: PrefectClient
) -> FlowRun:
    return await client.create_flow_run(
        flow,
        # Send serialized parameters to the backend
        parameters=flow.serialize_parameters(parameters),
        state=state,
        tags=TagsContext.get().current_tags,
    )


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

    flow_run = None
    state = Pending()
    if flow.should_validate_parameters:
        try:
            parameters = flow.validate_parameters(parameters)
        except Exception:
            state = await exception_to_failed_state(
                message="Validation of flow parameters failed with error:"
            )
            flow_run = await _make_flow_run(flow, parameters, state, client)
            await _run_flow_hooks(flow, flow_run, state)

    flow_run = flow_run or await _make_flow_run(flow, parameters, state, client)

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

    entrypoint = os.environ.get("PREFECT__FLOW_ENTRYPOINT")

    try:
        flow = (
            # We do not want to use a placeholder flow at runtime
            load_flow_from_entrypoint(entrypoint, use_placeholder_flow=False)
            if entrypoint
            else await load_flow_from_flow_run(
                flow_run, client=client, use_placeholder_flow=False
            )
        )
    except Exception:
        message = (
            "Flow could not be retrieved from"
            f" {'entrypoint' if entrypoint else 'deployment'}."
        )
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
    flow_run_context = FlowRunContext.construct(log_prints=log_prints)

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
        msg = "Currently paused and suspending execution."
        if timeout:
            msg += f" Resume before {timeout.to_rfc3339_string()} to finish execution."
        logger.log(level=logging.INFO, msg=msg)
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

    rerunning = (
        parent_flow_run_context.flow_run.run_count > 1
        if getattr(parent_flow_run_context, "flow_run", None)
        else False
    )

    # Generate a task in the parent flow run to represent the result of the subflow run
    dummy_task = Task(name=flow.name, fn=flow.fn, version=flow.version)
    parent_task_run = await client.create_task_run(
        task=dummy_task,
        flow_run_id=(
            parent_flow_run_context.flow_run.id
            if getattr(parent_flow_run_context, "flow_run", None)
            else None
        ),
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
                    partial_flow_run_context=FlowRunContext.construct(
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
    partial_flow_run_context: FlowRunContext,
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

    await _run_flow_hooks(flow=flow, flow_run=flow_run, state=state)

    while state.is_running():
        waited_for_task_runs = False

        # Update the flow run to the latest data
        flow_run = await client.read_flow_run(flow_run.id)
        try:
            with FlowRunContext(
                **{
                    **partial_flow_run_context.dict(),
                    **{
                        "flow_run": flow_run,
                        "flow": flow,
                        "client": client,
                        "parameters": parameters,
                    },
                }
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
                        getattr(parent_flow_run_context, "flow", None)
                        and parent_flow_run_context.flow.isasync == flow.isasync
                    )
                ):
                    from_async.call_soon_in_waiting_thread(
                        flow_call,
                        thread=user_thread,
                        timeout=flow.timeout_seconds,
                    )
                else:
                    from_async.call_soon_in_new_thread(
                        flow_call, timeout=flow.timeout_seconds
                    )

                result = await flow_call.aresult()

                waited_for_task_runs = await wait_for_task_runs_and_report_crashes(
                    flow_run_context.task_run_futures, client=client
                )
        except PausedRun as exc:
            # could get raised either via utility or by returning Paused from a task run
            # if a task run pauses, we set its state as the flow's state
            # to preserve reschedule and timeout behavior
            paused_flow_run = await client.read_flow_run(flow_run.id)
            if paused_flow_run.state.is_running():
                state = await propose_state(
                    client,
                    state=exc.state,
                    flow_run_id=flow_run.id,
                )

                return state
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
            # An exception occurred that prevented us from waiting for task runs to
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

        if not state.is_final() and not state.is_paused():
            logger.info(
                (
                    f"Received non-final state {state.name!r} when proposing final"
                    f" state {terminal_state.name!r} and will attempt to run again..."
                ),
            )
            # Attempt to enter a running state again
            state = await propose_state(client, Running(), flow_run_id=flow_run.id)

    return state


@deprecated_callable(
    start_date="Jun 2024",
    help="Will be moved in Prefect 3 to prefect.flow_runs:pause_flow_run",
)
@overload
async def pause_flow_run(
    wait_for_input: None = None,
    flow_run_id: UUID = None,
    timeout: int = 3600,
    poll_interval: int = 10,
    reschedule: bool = False,
    key: str = None,
) -> None:
    ...


@deprecated_callable(
    start_date="Jun 2024",
    help="Will be moved in Prefect 3 to prefect.flow_runs:pause_flow_run",
)
@overload
async def pause_flow_run(
    wait_for_input: Type[T],
    flow_run_id: UUID = None,
    timeout: int = 3600,
    poll_interval: int = 10,
    reschedule: bool = False,
    key: str = None,
) -> T:
    ...


@sync_compatible
@deprecated_parameter(
    "flow_run_id", start_date="Dec 2023", help="Use `suspend_flow_run` instead."
)
@deprecated_parameter(
    "reschedule",
    start_date="Dec 2023",
    when=lambda p: p is True,
    help="Use `suspend_flow_run` instead.",
)
@experimental_parameter(
    "wait_for_input", group="flow_run_input", when=lambda y: y is not None
)
async def pause_flow_run(
    wait_for_input: Optional[Type[T]] = None,
    flow_run_id: UUID = None,
    timeout: int = 3600,
    poll_interval: int = 10,
    reschedule: bool = False,
    key: str = None,
) -> Optional[T]:
    """
    Pauses the current flow run by blocking execution until resumed.

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
            failing. Defaults to 1 hour (3600 seconds). If the pause timeout exceeds
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
        wait_for_input: a subclass of `RunInput` or any type supported by
            Pydantic. If provided when the flow pauses, the flow will wait for the
            input to be provided before resuming. If the flow is resumed without
            providing the input, the flow will fail. If the flow is resumed with the
            input, the flow will resume and the input will be loaded and returned
            from this function.

    Example:
    ```python
    @task
    def task_one():
        for i in range(3):
            sleep(1)

    @flow
    def my_flow():
        terminal_state = task_one.submit(return_state=True)
        if terminal_state.type == StateType.COMPLETED:
            print("Task one succeeded! Pausing flow run..")
            pause_flow_run(timeout=2)
        else:
            print("Task one failed. Skipping pause flow run..")
    ```

    """
    if flow_run_id:
        if wait_for_input is not None:
            raise RuntimeError("Cannot wait for input when pausing out of process.")

        return await _out_of_process_pause(
            flow_run_id=flow_run_id,
            timeout=timeout,
            reschedule=reschedule,
            key=key,
        )
    else:
        return await _in_process_pause(
            timeout=timeout,
            poll_interval=poll_interval,
            reschedule=reschedule,
            key=key,
            wait_for_input=wait_for_input,
        )


@deprecated_callable(
    start_date="Jun 2024",
    help="Will be moved in Prefect 3 to prefect.flow_runs:_in_process_pause",
)
@inject_client
async def _in_process_pause(
    timeout: int = 3600,
    poll_interval: int = 10,
    reschedule=False,
    key: str = None,
    client=None,
    wait_for_input: Optional[T] = None,
) -> Optional[T]:
    if TaskRunContext.get():
        raise RuntimeError("Cannot pause task runs.")

    context = FlowRunContext.get()
    if not context:
        raise RuntimeError("Flow runs can only be paused from within a flow run.")

    logger = get_run_logger(context=context)

    pause_counter = _observed_flow_pauses(context)
    pause_key = key or str(pause_counter)

    logger.info("Pausing flow, execution will continue when this flow run is resumed.")

    proposed_state = Paused(
        timeout_seconds=timeout, reschedule=reschedule, pause_key=pause_key
    )

    if wait_for_input:
        wait_for_input = run_input_subclass_from_type(wait_for_input)
        run_input_keyset = keyset_from_paused_state(proposed_state)
        proposed_state.state_details.run_input_keyset = run_input_keyset

    try:
        state = await propose_state(
            client=client,
            state=proposed_state,
            flow_run_id=context.flow_run.id,
        )
    except Abort as exc:
        # Aborted pause requests mean the pause is not allowed
        raise RuntimeError(f"Flow run cannot be paused: {exc}")

    if state.is_running():
        # The orchestrator rejected the paused state which means that this
        # pause has happened before (via reschedule) and the flow run has
        # been resumed.
        if wait_for_input:
            # The flow run wanted input, so we need to load it and return it
            # to the user.
            await wait_for_input.load(run_input_keyset)

        return

    if not state.is_paused():
        # If we receive anything but a PAUSED state, we are unable to continue
        raise RuntimeError(
            f"Flow run cannot be paused. Received non-paused state from API: {state}"
        )

    if wait_for_input:
        # We're now in a paused state and the flow run is waiting for input.
        # Save the schema of the users `RunInput` subclass, stored in
        # `wait_for_input`, so the UI can display the form and we can validate
        # the input when the flow is resumed.
        await wait_for_input.save(run_input_keyset)

    if reschedule:
        # If a rescheduled pause, exit this process so the run can be resubmitted later
        raise Pause(state=state)

    # Otherwise, block and check for completion on an interval
    with anyio.move_on_after(timeout):
        # attempt to check if a flow has resumed at least once
        initial_sleep = min(timeout / 2, poll_interval)
        await anyio.sleep(initial_sleep)
        while True:
            flow_run = await client.read_flow_run(context.flow_run.id)
            if flow_run.state.is_running():
                logger.info("Resuming flow run execution!")
                if wait_for_input:
                    return await wait_for_input.load(run_input_keyset)
                return
            await anyio.sleep(poll_interval)

    # check one last time before failing the flow
    flow_run = await client.read_flow_run(context.flow_run.id)
    if flow_run.state.is_running():
        logger.info("Resuming flow run execution!")
        if wait_for_input:
            return await wait_for_input.load(run_input_keyset)
        return

    raise FlowPauseTimeout("Flow run was paused and never resumed.")


@deprecated_callable(
    start_date="Jun 2024",
    help="Will be moved in Prefect 3 to prefect.flow_runs.pause_flow_run.",
)
@inject_client
async def _out_of_process_pause(
    flow_run_id: UUID,
    timeout: int = 3600,
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


@deprecated_callable(
    start_date="Jun 2024",
    help="Will be moved in Prefect 3 to prefect.flow_runs:suspend_flow_run",
)
@overload
async def suspend_flow_run(
    wait_for_input: None = None,
    flow_run_id: Optional[UUID] = None,
    timeout: Optional[int] = 3600,
    key: Optional[str] = None,
    client: PrefectClient = None,
) -> None:
    ...


@overload
async def suspend_flow_run(
    wait_for_input: Type[T],
    flow_run_id: Optional[UUID] = None,
    timeout: Optional[int] = 3600,
    key: Optional[str] = None,
    client: PrefectClient = None,
) -> T:
    ...


@sync_compatible
@inject_client
@experimental_parameter(
    "wait_for_input", group="flow_run_input", when=lambda y: y is not None
)
async def suspend_flow_run(
    wait_for_input: Optional[Type[T]] = None,
    flow_run_id: Optional[UUID] = None,
    timeout: Optional[int] = 3600,
    key: Optional[str] = None,
    client: PrefectClient = None,
) -> Optional[T]:
    """
    Suspends a flow run by stopping code execution until resumed.

    When suspended, the flow run will continue execution until the NEXT task is
    orchestrated, at which point the flow will exit. Any tasks that have
    already started will run until completion. When resumed, the flow run will
    be rescheduled to finish execution. In order suspend a flow run in this
    way, the flow needs to have an associated deployment and results need to be
    configured with the `persist_results` option.

    Args:
        flow_run_id: a flow run id. If supplied, this function will attempt to
            suspend the specified flow run. If not supplied will attempt to
            suspend the current flow run.
        timeout: the number of seconds to wait for the flow to be resumed before
            failing. Defaults to 1 hour (3600 seconds). If the pause timeout
            exceeds any configured flow-level timeout, the flow might fail even
            after resuming.
        key: An optional key to prevent calling suspend more than once. This
            defaults to a random string and prevents suspends from running the
            same suspend twice. A custom key can be supplied for custom
            suspending behavior.
        wait_for_input: a subclass of `RunInput` or any type supported by
            Pydantic. If provided when the flow suspends, the flow will remain
            suspended until receiving the input before resuming. If the flow is
            resumed without providing the input, the flow will fail. If the flow is
            resumed with the input, the flow will resume and the input will be
            loaded and returned from this function.
    """
    context = FlowRunContext.get()

    if flow_run_id is None:
        if TaskRunContext.get():
            raise RuntimeError("Cannot suspend task runs.")

        if context is None or context.flow_run is None:
            raise RuntimeError(
                "Flow runs can only be suspended from within a flow run."
            )

        logger = get_run_logger(context=context)
        logger.info(
            "Suspending flow run, execution will be rescheduled when this flow run is"
            " resumed."
        )
        flow_run_id = context.flow_run.id
        suspending_current_flow_run = True
        pause_counter = _observed_flow_pauses(context)
        pause_key = key or str(pause_counter)
    else:
        # Since we're suspending another flow run we need to generate a pause
        # key that won't conflict with whatever suspends/pauses that flow may
        # have. Since this method won't be called during that flow run it's
        # okay that this is non-deterministic.
        suspending_current_flow_run = False
        pause_key = key or str(uuid4())

    proposed_state = Suspended(timeout_seconds=timeout, pause_key=pause_key)

    if wait_for_input:
        wait_for_input = run_input_subclass_from_type(wait_for_input)
        run_input_keyset = keyset_from_paused_state(proposed_state)
        proposed_state.state_details.run_input_keyset = run_input_keyset

    try:
        state = await propose_state(
            client=client,
            state=proposed_state,
            flow_run_id=flow_run_id,
        )
    except Abort as exc:
        # Aborted requests mean the suspension is not allowed
        raise RuntimeError(f"Flow run cannot be suspended: {exc}")

    if state.is_running():
        # The orchestrator rejected the suspended state which means that this
        # suspend has happened before and the flow run has been resumed.
        if wait_for_input:
            # The flow run wanted input, so we need to load it and return it
            # to the user.
            return await wait_for_input.load(run_input_keyset)
        return

    if not state.is_paused():
        # If we receive anything but a PAUSED state, we are unable to continue
        raise RuntimeError(
            f"Flow run cannot be suspended. Received unexpected state from API: {state}"
        )

    if wait_for_input:
        await wait_for_input.save(run_input_keyset)

    if suspending_current_flow_run:
        # Exit this process so the run can be resubmitted later
        raise Pause()


@deprecated_callable(
    start_date="Jun 2024",
    help="Will be moved in Prefect 3 to prefect.flow_runs:resume_flow_run",
)
@sync_compatible
async def resume_flow_run(flow_run_id, run_input: Optional[Dict] = None):
    """
    Resumes a paused flow.

    Args:
        flow_run_id: the flow_run_id to resume
        run_input: a dictionary of inputs to provide to the flow run.
    """
    client = get_client()
    async with client:
        flow_run = await client.read_flow_run(flow_run_id)

        if not flow_run.state.is_paused():
            raise NotPausedError("Cannot resume a run that isn't paused!")

        response = await client.resume_flow_run(flow_run_id, run_input=run_input)

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
    entering_from_task_run: Optional[bool] = False,
) -> Union[PrefectFuture, Awaitable[PrefectFuture], TaskRun]:
    """Sync entrypoint for task calls"""

    flow_run_context = FlowRunContext.get()

    if not flow_run_context:
        if return_type == "future" or mapped:
            raise RuntimeError(
                " If you meant to submit a background task, you need to set"
                " `prefect config set PREFECT_EXPERIMENTAL_ENABLE_TASK_SCHEDULING=true`"
                " and use `your_task.submit()` instead of `your_task()`."
            )
        from prefect.task_engine import submit_autonomous_task_run_to_engine

        return submit_autonomous_task_run_to_engine(
            task=task,
            task_run=None,
            parameters=parameters,
            task_runner=task_runner,
            wait_for=wait_for,
            return_type=return_type,
            client=get_client(),
        )

    if flow_run_context.timeout_scope and flow_run_context.timeout_scope.cancel_called:
        raise TimeoutError("Flow run timed out")

    call_arguments = {
        "task": task,
        "flow_run_context": flow_run_context,
        "parameters": parameters,
        "wait_for": wait_for,
        "return_type": return_type,
        "task_runner": task_runner,
    }

    if not mapped:
        call_arguments["entering_from_task_run"] = entering_from_task_run

    begin_run = create_call(
        begin_task_map if mapped else get_task_call_return_value, **call_arguments
    )

    if task.isasync and (
        flow_run_context.flow is None or flow_run_context.flow.isasync
    ):
        # return a coro for the user to await if an async task in an async flow
        return from_async.wait_for_call_in_loop_thread(begin_run)
    else:
        return from_sync.wait_for_call_in_loop_thread(begin_run)


async def begin_task_map(
    task: Task,
    flow_run_context: Optional[FlowRunContext],
    parameters: Dict[str, Any],
    wait_for: Optional[Iterable[PrefectFuture]],
    return_type: EngineReturnType,
    task_runner: Optional[BaseTaskRunner],
    autonomous: bool = False,
) -> List[Union[PrefectFuture, Awaitable[PrefectFuture], TaskRun]]:
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

        if autonomous:
            task_runs.append(
                await create_autonomous_task_run(
                    task=task,
                    parameters=call_parameters,
                )
            )
        else:
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

    if autonomous:
        return task_runs

    # Maintain the order of the task runs when using the sequential task runner
    runner = task_runner if task_runner else flow_run_context.task_runner
    if runner.concurrency_type == TaskConcurrencyType.SEQUENTIAL:
        return [await task_run() for task_run in task_runs]

    return await gather(*task_runs)


async def get_task_call_return_value(
    task: Task,
    flow_run_context: FlowRunContext,
    parameters: Dict[str, Any],
    wait_for: Optional[Iterable[PrefectFuture]],
    return_type: EngineReturnType,
    task_runner: Optional[BaseTaskRunner],
    extra_task_inputs: Optional[Dict[str, Set[TaskRunInput]]] = None,
    entering_from_task_run: Optional[bool] = False,
):
    extra_task_inputs = extra_task_inputs or {}

    future = await create_task_run_future(
        task=task,
        flow_run_context=flow_run_context,
        parameters=parameters,
        wait_for=wait_for,
        task_runner=task_runner,
        extra_task_inputs=extra_task_inputs,
        entering_from_task_run=entering_from_task_run,
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
    entering_from_task_run: Optional[bool] = False,
) -> PrefectFuture:
    # Default to the flow run's task runner
    task_runner = task_runner or flow_run_context.task_runner

    # Generate a name for the future
    dynamic_key = _dynamic_key_for_task_run(flow_run_context, task)

    task_run_name = (
        f"{task.name}-{dynamic_key}"
        if flow_run_context and flow_run_context.flow_run
        else f"{task.name}-{dynamic_key[:NUM_CHARS_DYNAMIC_KEY]}"  # autonomous task run
    )

    # Generate a future
    future = PrefectFuture(
        name=task_run_name,
        key=uuid4(),
        task_runner=task_runner,
        asynchronous=(
            task.isasync and flow_run_context.flow.isasync
            if flow_run_context and flow_run_context.flow
            else task.isasync
        ),
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

    if not entering_from_task_run:
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
    task_run = (
        await create_task_run(
            task=task,
            name=task_run_name,
            flow_run_context=flow_run_context,
            parameters=parameters,
            dynamic_key=task_run_dynamic_key,
            wait_for=wait_for,
            extra_task_inputs=extra_task_inputs,
        )
        if not flow_run_context.autonomous_task_run
        else flow_run_context.autonomous_task_run
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
        flow_run_id=flow_run_context.flow_run.id if flow_run_context.flow_run else None,
        dynamic_key=dynamic_key,
        state=Pending(),
        extra_tags=TagsContext.get().current_tags,
        task_inputs=task_inputs,
    )

    if flow_run_context.flow_run:
        logger.info(f"Created task run {task_run.name!r} for task {task.name!r}")
    else:
        engine_logger.info(f"Created task run {task_run.name!r} for task {task.name!r}")

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

    if (
        task_runner.concurrency_type == TaskConcurrencyType.SEQUENTIAL
        and flow_run_context.flow_run
    ):
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

    if (
        task_runner.concurrency_type != TaskConcurrencyType.SEQUENTIAL
        and not flow_run_context.autonomous_task_run
    ):
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
            # Otherwise, retrieve a new clien`t
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
            # A pause signal here should mean the flow run suspended, so we
            # should do the same. We'll look up the flow run's pause state to
            # try and reuse it, so we capture any data like timeouts.
            flow_run = await client.read_flow_run(task_run.flow_run_id)
            if flow_run.state and flow_run.state.is_paused():
                state = flow_run.state
            else:
                state = Suspended()

            task_run_logger(task_run).info(
                "Task run encountered a pause signal during orchestration."
            )

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

    This function should be submitted to a task runner. We must construct the context
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
    flow_run_context = prefect.context.FlowRunContext.get()
    if flow_run_context:
        flow_run = flow_run_context.flow_run
    else:
        flow_run = await client.read_flow_run(task_run.flow_run_id)
    logger = task_run_logger(task_run, task=task, flow_run=flow_run)

    partial_task_run_context = TaskRunContext.construct(
        task_run=task_run,
        task=task,
        client=client,
        result_factory=result_factory,
        log_prints=log_prints,
    )
    task_introspection_start_time = time.perf_counter()
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
    task_introspection_end_time = time.perf_counter()

    introspection_time = round(
        task_introspection_end_time - task_introspection_start_time, 3
    )
    threshold = PREFECT_TASK_INTROSPECTION_WARN_THRESHOLD.value()
    if threshold and introspection_time > threshold:
        logger.warning(
            f"Task parameter introspection took {introspection_time} seconds "
            f", exceeding `PREFECT_TASK_INTROSPECTION_WARN_THRESHOLD` of {threshold}. "
            "Try wrapping large task parameters with "
            "`prefect.utilities.annotations.quote` for increased performance, "
            "e.g. `my_task(quote(param))`. To disable this message set "
            "`PREFECT_TASK_INTROSPECTION_WARN_THRESHOLD=0`."
        )

    # Generate the cache key to attach to proposed states
    # The cache key uses a TaskRunContext that does not include a `timeout_context``

    task_run_context = TaskRunContext(
        **partial_task_run_context.dict(), parameters=resolved_parameters
    )

    cache_key = (
        task.cache_key_fn(
            task_run_context,
            resolved_parameters,
        )
        if task.cache_key_fn
        else None
    )

    # Ignore the cached results for a cache key, default = false
    # Setting on task level overrules the Prefect setting (env var)
    refresh_cache = (
        task.refresh_cache
        if task.refresh_cache is not None
        else PREFECT_TASKS_REFRESH_CACHE.value()
    )

    # Emit an event to capture that the task run was in the `PENDING` state.
    last_event = emit_task_run_state_change_event(
        task_run=task_run, initial_state=None, validated_state=task_run.state
    )
    last_state = (
        Pending()
        if flow_run_context and flow_run_context.autonomous_task_run
        else task_run.state
    )

    # Completed states with persisted results should have result data. If it's missing,
    # this could be a manual state transition, so we should use the Unknown result type
    # to represent that we know we don't know the result.
    if (
        last_state
        and last_state.is_completed()
        and result_factory.persist_result
        and not last_state.data
    ):
        state = await propose_state(
            client,
            state=Completed(data=await UnknownResult.create()),
            task_run_id=task_run.id,
            force=True,
        )

    # Transition from `PENDING` -> `RUNNING`
    try:
        state = await propose_state(
            client,
            Running(
                state_details=StateDetails(
                    cache_key=cache_key, refresh_cache=refresh_cache
                )
            ),
            task_run_id=task_run.id,
        )
    except Pause as exc:
        # We shouldn't get a pause signal without a state, but if this happens,
        # just use a Paused state to assume an in-process pause.
        state = exc.state if exc.state else Paused()

        # If a flow submits tasks and then pauses, we may reach this point due
        # to concurrency timing because the tasks will try to transition after
        # the flow run has paused. Orchestration will send back a Paused state
        # for the task runs.
        if state.state_details.pause_reschedule:
            # If we're being asked to pause and reschedule, we should exit the
            # task and expect to be resumed later.
            raise

    if state.is_paused():
        BACKOFF_MAX = 10  # Seconds
        backoff_count = 0

        async def tick():
            nonlocal backoff_count
            if backoff_count < BACKOFF_MAX:
                backoff_count += 1
            interval = 1 + backoff_count + random.random() * backoff_count
            await anyio.sleep(interval)

        # Enter a loop to wait for the task run to be resumed, i.e.
        # become Pending, and then propose a Running state again.
        while True:
            await tick()

            # Propose a Running state again. We do this instead of reading the
            # task run because if the flow run times out, this lets
            # orchestration fail the task run.
            try:
                state = await propose_state(
                    client,
                    Running(
                        state_details=StateDetails(
                            cache_key=cache_key, refresh_cache=refresh_cache
                        )
                    ),
                    task_run_id=task_run.id,
                )
            except Pause as exc:
                if not exc.state:
                    continue

                if exc.state.state_details.pause_reschedule:
                    # If the pause state includes pause_reschedule, we should exit the
                    # task and expect to be resumed later. We've already checked for this
                    # above, but we check again here in case the state changed; e.g. the
                    # flow run suspended.
                    raise
                else:
                    # Propose a Running state again.
                    continue
            else:
                break

    # Emit an event to capture the result of proposing a `RUNNING` state.
    last_event = emit_task_run_state_change_event(
        task_run=task_run,
        initial_state=last_state,
        validated_state=state,
        follows=last_event,
    )
    last_state = state

    # flag to ensure we only update the task run name once
    run_name_set = False

    run_on_completion_hooks_on_cached = (
        PREFECT_RUN_ON_COMPLETION_HOOKS_ON_CACHED
        and state.is_completed()
        and state.name == "Cached"
    )

    if run_on_completion_hooks_on_cached:
        await _run_task_hooks(
            task=task,
            task_run=task_run,
            state=state,
        )

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

            if terminal_state.is_failed():
                # Defer to user to decide whether failure is retriable
                terminal_state.state_details.retriable = (
                    await _check_task_failure_retriable(task, task_run, terminal_state)
                )
            state = await propose_state(client, terminal_state, task_run_id=task_run.id)
            last_event = emit_task_run_state_change_event(
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

            if not state.is_final() and not state.is_paused():
                logger.info(
                    (
                        f"Received non-final state {state.name!r} when proposing final"
                        f" state {terminal_state.name!r} and will attempt to run"
                        " again..."
                    ),
                )
                # Attempt to enter a running state again
                state = await propose_state(client, Running(), task_run_id=task_run.id)
                last_event = emit_task_run_state_change_event(
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


@asynccontextmanager
async def report_flow_run_crashes(flow_run: FlowRun, client: PrefectClient, flow: Flow):
    """
    Detect flow run crashes during this context and update the run to a proper final
    state.

    This context _must_ reraise the exception to properly exit the run.
    """
    try:
        with collapse_excgroups():
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
        with collapse_excgroups():
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


async def _run_task_hooks(task: Task, task_run: TaskRun, state: State) -> None:
    """Run the on_failure and on_completion hooks for a task, making sure to
    catch and log any errors that occur.
    """
    hooks = None
    run_on_completion_hooks_on_cached = (
        PREFECT_RUN_ON_COMPLETION_HOOKS_ON_CACHED
        and state.is_completed()
        and state.name == "Cached"
    )
    if state.is_failed() and task.on_failure:
        hooks = task.on_failure
    elif (
        state.is_completed() or run_on_completion_hooks_on_cached
    ) and task.on_completion:
        hooks = task.on_completion

    if hooks:
        logger = task_run_logger(task_run)
        for hook in hooks:
            hook_name = _get_hook_name(hook)
            try:
                logger.info(
                    f"Running hook {hook_name!r} in response to entering state"
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
                    f"An error was encountered while running hook {hook_name!r}",
                    exc_info=True,
                )
            else:
                logger.info(f"Hook {hook_name!r} finished running successfully")


async def _check_task_failure_retriable(
    task: Task, task_run: TaskRun, state: State
) -> bool:
    """Run the `retry_condition_fn` callable for a task, making sure to catch and log any errors
    that occur. If None, return True. If not callable, logs an error and returns False.
    """
    if task.retry_condition_fn is None:
        return True

    logger = task_run_logger(task_run)

    try:
        logger.debug(
            f"Running `retry_condition_fn` check {task.retry_condition_fn!r} for task"
            f" {task.name!r}"
        )
        if is_async_fn(task.retry_condition_fn):
            return bool(
                await task.retry_condition_fn(task=task, task_run=task_run, state=state)
            )
        else:
            return bool(
                await from_async.call_in_new_thread(
                    create_call(
                        task.retry_condition_fn,
                        task=task,
                        task_run=task_run,
                        state=state,
                    )
                )
            )
    except Exception:
        logger.error(
            (
                "An error was encountered while running `retry_condition_fn` check"
                f" '{task.retry_condition_fn!r}' for task {task.name!r}"
            ),
            exc_info=True,
        )
        return False


async def _run_flow_hooks(flow: Flow, flow_run: FlowRun, state: State) -> None:
    """Run the on_failure, on_completion, on_cancellation, and on_crashed hooks for a flow, making sure to
    catch and log any errors that occur.
    """
    hooks = None
    enable_cancellation_and_crashed_hooks = (
        os.environ.get("PREFECT__ENABLE_CANCELLATION_AND_CRASHED_HOOKS", "true").lower()
        == "true"
    )

    if state.is_running() and flow.on_running:
        hooks = flow.on_running
    elif state.is_failed() and flow.on_failure:
        hooks = flow.on_failure
    elif state.is_completed() and flow.on_completion:
        hooks = flow.on_completion
    elif (
        enable_cancellation_and_crashed_hooks
        and state.is_cancelling()
        and flow.on_cancellation
    ):
        hooks = flow.on_cancellation
    elif (
        enable_cancellation_and_crashed_hooks and state.is_crashed() and flow.on_crashed
    ):
        hooks = flow.on_crashed

    if hooks:
        logger = flow_run_logger(flow_run)
        for hook in hooks:
            hook_name = _get_hook_name(hook)
            try:
                logger.info(
                    f"Running hook {hook_name!r} in response to entering state"
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
                    f"An error was encountered while running hook {hook_name!r}",
                    exc_info=True,
                )
            else:
                logger.info(f"Hook {hook_name!r} finished running successfully")


async def create_autonomous_task_run(task: Task, parameters: Dict[str, Any]) -> TaskRun:
    """Create a task run in the API for an autonomous task submission and store
    the provided parameters using the existing result storage mechanism.
    """
    async with get_client() as client:
        state = Scheduled()
        if parameters:
            parameters_id = uuid4()
            state.state_details.task_parameters_id = parameters_id

            # TODO: Improve use of result storage for parameter storage / reference
            task.persist_result = True

            factory = await ResultFactory.from_autonomous_task(task, client=client)
            await factory.store_parameters(parameters_id, parameters)

        task_run = await client.create_task_run(
            task=task,
            flow_run_id=None,
            dynamic_key=f"{task.task_key}-{str(uuid4())[:NUM_CHARS_DYNAMIC_KEY]}",
            state=state,
        )

        engine_logger.debug(f"Submitted run of task {task.name!r} for execution")

    return task_run


if __name__ == "__main__":
    try:
        flow_run_id = UUID(
            sys.argv[1] if len(sys.argv) > 1 else os.environ.get("PREFECT__FLOW_RUN_ID")
        )
    except Exception:
        engine_logger.error(
            f"Invalid flow run id. Received arguments: {sys.argv}", exc_info=True
        )
        exit(1)

    try:
        if PREFECT_EXPERIMENTAL_ENABLE_NEW_ENGINE.value():
            from prefect.new_flow_engine import (
                load_flow_and_flow_run,
                run_flow_async,
                run_flow_sync,
            )

            flow_run, flow = run_sync(load_flow_and_flow_run)
            # run the flow
            if flow.isasync:
                run_sync(run_flow_async(flow, flow_run=flow_run))
            else:
                run_flow_sync(flow, flow_run=flow_run)
        else:
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
