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
import sys
from contextlib import AsyncExitStack, asynccontextmanager, nullcontext
from functools import partial
from typing import Any, Awaitable, Dict, Iterable, List, Optional, Set, TypeVar, Union
from uuid import UUID, uuid4

import anyio
import pendulum
from anyio import start_blocking_portal
from typing_extensions import Literal

import prefect
import prefect.context
from prefect.client.orion import OrionClient, get_client
from prefect.client.schemas import FlowRun, TaskRun
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
    MappingLengthMismatch,
    MappingMissingIterable,
    UpstreamTaskError,
)
from prefect.flows import Flow
from prefect.futures import PrefectFuture, call_repr, resolve_futures_to_states
from prefect.logging.configuration import setup_logging
from prefect.logging.handlers import OrionHandler
from prefect.logging.loggers import (
    flow_run_logger,
    get_logger,
    get_run_logger,
    task_run_logger,
)
from prefect.orion.schemas.core import TaskRunInput, TaskRunResult
from prefect.orion.schemas.filters import FlowRunFilter
from prefect.orion.schemas.responses import SetStateStatus
from prefect.orion.schemas.sorting import FlowRunSort
from prefect.orion.schemas.states import StateDetails, StateType
from prefect.results import ResultFactory
from prefect.settings import PREFECT_DEBUG_MODE
from prefect.states import (
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
from prefect.utilities.annotations import Quote, allow_failure, unmapped
from prefect.utilities.asyncutils import (
    gather,
    in_async_main_thread,
    run_async_from_worker_thread,
    run_sync_in_interruptible_worker_thread,
    run_sync_in_worker_thread,
)
from prefect.utilities.callables import parameters_to_args_kwargs
from prefect.utilities.collections import isiterable, visit_collection
from prefect.utilities.hashing import stable_hash
from prefect.utilities.pydantic import PartialModel

R = TypeVar("R")
EngineReturnType = Literal["future", "state", "result"]


UNTRACKABLE_TYPES = {bool, type(None), type(...), type(NotImplemented)}
engine_logger = get_logger("engine")


def enter_flow_run_engine_from_flow_call(
    flow: Flow, parameters: Dict[str, Any], return_type: EngineReturnType
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
            f"Script loading is in progress, flow {flow.name!r} will not be executed. "
            "Consider updating the script to only call the flow if executed directly:\n\n"
            f'\tif __name__ == "main":\n\t\t{flow.fn.__name__}()'
        )
        return None

    if TaskRunContext.get():
        raise RuntimeError(
            "Flows cannot be run from within tasks. Did you mean to call this "
            "flow in a flow?"
        )

    parent_flow_run_context = FlowRunContext.get()
    is_subflow_run = parent_flow_run_context is not None

    begin_run = partial(
        create_and_begin_subflow_run if is_subflow_run else create_then_begin_flow_run,
        flow=flow,
        parameters=parameters,
        return_type=return_type,
        client=parent_flow_run_context.client if is_subflow_run else None,
    )

    if not is_subflow_run:
        # Async flow run
        if flow.isasync:
            return begin_run()  # Return a coroutine for the user to await
        # Sync flow run
        elif in_async_main_thread():
            # An event loop is already running and we must create a blocking portal to
            # run async code from this synchronous context
            with start_blocking_portal() as portal:
                return portal.call(begin_run)
        else:
            # An event loop is not running so we will create one
            return anyio.run(begin_run)

    if not parent_flow_run_context.flow.isasync:
        # Async subflow run in sync flow run
        return run_async_from_worker_thread(begin_run)
    elif parent_flow_run_context.flow.isasync and flow.isasync:
        # Async subflow run in async flow run
        return begin_run()
    else:
        # Sync subflow run in async flow run
        return parent_flow_run_context.sync_portal.call(begin_run)


def enter_flow_run_engine_from_subprocess(flow_run_id: UUID) -> State:
    """
    Sync entrypoint for flow runs that have been submitted for execution by an agent

    Differs from `enter_flow_run_engine_from_flow_call` in that we have a flow run id
    but not a flow object. The flow must be retrieved before execution can begin.
    Additionally, this assumes that the caller is always in a context without an event
    loop as this should be called from a fresh process.
    """
    setup_logging()

    return anyio.run(retrieve_flow_then_begin_flow_run, flow_run_id)


@inject_client
async def create_then_begin_flow_run(
    flow: Flow,
    parameters: Dict[str, Any],
    return_type: EngineReturnType,
    client: OrionClient,
) -> Any:
    """
    Async entrypoint for flow calls

    Creates the flow run in the backend, then enters the main flow run engine.
    """
    # TODO: Returns a `State` depending on `return_type` and we can add an overload to
    #       the function signature to clarify this eventually.

    connect_error = await client.api_healthcheck()
    if connect_error:
        raise RuntimeError(
            f"Cannot create flow run. Failed to reach API at {client.api_url}."
        ) from connect_error
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

    if state.is_failed():
        flow_run_logger(flow_run).error(state.message)
        engine_logger.info(
            f"Flow run {flow_run.name!r} received invalid parameters and is marked as failed."
        )
    else:
        state = await begin_flow_run(
            flow=flow, flow_run=flow_run, parameters=parameters, client=client
        )

    if return_type == "state":
        return state
    elif return_type == "result":
        return await state.result(fetch=True)
    else:
        raise ValueError(f"Invalid return type for flow engine {return_type!r}.")


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
    try:
        flow = await load_flow_from_flow_run(flow_run, client=client)
    except Exception as exc:
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

    flow_run_context = PartialModel(FlowRunContext)

    async with AsyncExitStack() as stack:

        await stack.enter_async_context(
            report_flow_run_crashes(flow_run=flow_run, client=client)
        )

        # Create a task group for background tasks
        flow_run_context.background_tasks = await stack.enter_async_context(
            anyio.create_task_group()
        )

        # If the flow is async, we need to provide a portal so sync tasks can run
        flow_run_context.sync_portal = (
            stack.enter_context(start_blocking_portal()) if flow.isasync else None
        )

        logger.debug(
            f"Starting {type(flow.task_runner).__name__!r}; submitted tasks "
            f"will be run {CONCURRENCY_MESSAGES[flow.task_runner.concurrency_type]}..."
        )
        flow_run_context.task_runner = await stack.enter_async_context(
            flow.task_runner.start()
        )

        flow_run_context.result_factory = await ResultFactory.from_flow(
            flow, client=client
        )

        terminal_state = await orchestrate_flow_run(
            flow,
            flow_run=flow_run,
            parameters=parameters,
            client=client,
            partial_flow_run_context=flow_run_context,
            # Orchestration needs to be interruptible if it has a timeout
            interruptible=flow.timeout_seconds is not None,
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
    return_type: EngineReturnType,
    client: OrionClient,
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

    parent_logger.debug(f"Resolving inputs to {flow.name!r}")
    task_inputs = {k: await collect_task_run_inputs(v) for k, v in parameters.items()}

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

    if parent_task_run.state.is_final():

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
            state=parent_task_run.state,
            tags=TagsContext.get().current_tags,
        )

        parent_logger.info(
            f"Created subflow run {flow_run.name!r} for flow {flow.name!r}"
        )
        logger = flow_run_logger(flow_run, flow)
        result_factory = await ResultFactory.from_flow(
            flow, client=parent_flow_run_context.client
        )

        if flow.should_validate_parameters:
            failed_state = None
            try:
                parameters = flow.validate_parameters(parameters)
            except Exception:
                message = "Validation of flow parameters failed with error:"
                logger.exception(message)
                failed_state = await exception_to_failed_state(
                    message=message, result_factory=result_factory
                )

            if failed_state is not None:
                await propose_state(
                    client,
                    state=failed_state,
                    flow_run_id=flow_run.id,
                )
                return failed_state

        async with AsyncExitStack() as stack:
            await stack.enter_async_context(
                report_flow_run_crashes(flow_run=flow_run, client=client)
            )
            task_runner = await stack.enter_async_context(flow.task_runner.start())

            terminal_state = await orchestrate_flow_run(
                flow,
                flow_run=flow_run,
                parameters=parameters,
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
                ),
            )

    # Display the full state (including the result) if debugging
    display_state = repr(terminal_state) if PREFECT_DEBUG_MODE else str(terminal_state)
    logger.log(
        level=logging.INFO if terminal_state.is_completed() else logging.ERROR,
        msg=f"Finished in state {display_state}",
        extra={"send_to_orion": False},
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
    interruptible: bool,
    client: OrionClient,
    partial_flow_run_context: PartialModel[FlowRunContext],
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

    timeout_context = (
        anyio.fail_after(flow.timeout_seconds)
        if flow.timeout_seconds
        else nullcontext()
    )
    flow_run_context = None

    state = await propose_state(client, Running(), flow_run_id=flow_run.id)

    while state.is_running():
        waited_for_task_runs = False

        # Update the flow run to the latest data
        flow_run = await client.read_flow_run(flow_run.id)
        try:
            with timeout_context as timeout_scope:
                with partial_flow_run_context.finalize(
                    flow=flow,
                    flow_run=flow_run,
                    client=client,
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
                        run_sync = (
                            run_sync_in_interruptible_worker_thread
                            if interruptible or timeout_scope
                            else run_sync_in_worker_thread
                        )
                        result = await run_sync(flow_call)

                waited_for_task_runs = await wait_for_task_runs_and_report_crashes(
                    flow_run_context.task_run_futures, client=client
                )

        except Exception as exc:
            name = message = None
            if (
                # Flow run timeouts
                isinstance(exc, TimeoutError)
                and timeout_scope
                # Only update the message if the timeout was actually encountered since
                # this could be a timeout in the user's code
                and timeout_scope.cancel_called
            ):
                # TODO: Cancel task runs if feasible
                name = "TimedOut"
                message = f"Flow run exceeded timeout of {flow.timeout_seconds} seconds"
            else:
                # Generic exception in user code
                message = "Flow run encountered an exception."
                logger.exception("Encountered exception during execution:")
            terminal_state = await exception_to_failed_state(
                name=name,
                message=message,
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
        # block storage and send the resulting data document to the Orion API instead.
        # This prevents the pickled return value of flow runs
        # from being sent to the Orion API and stored in the Orion database.
        # state.data is left as is, otherwise we would have to load
        # the data from block storage again after storing.
        state = await propose_state(
            client,
            state=terminal_state,
            flow_run_id=flow_run.id,
        )

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
            state = await propose_state(client, Running(), flow_run_id=flow_run.id)

    return state


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
            "Tasks cannot be run outside of a flow. To call the underlying task function outside of a flow use `task.fn()`."
        )

    if TaskRunContext.get():
        raise RuntimeError(
            "Tasks cannot be run from within tasks. Did you mean to call this "
            "task in a flow?"
        )

    if flow_run_context.timeout_scope and flow_run_context.timeout_scope.cancel_called:
        raise TimeoutError("Flow run timed out")

    begin_run = partial(
        begin_task_map if mapped else get_task_call_return_value,
        task=task,
        flow_run_context=flow_run_context,
        parameters=parameters,
        wait_for=wait_for,
        return_type=return_type,
        task_runner=task_runner,
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

    iterable_parameters = {}
    static_parameters = {}
    for key, val in parameters.items():
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
            "Received iterable parameters with different lengths. Parameters "
            f"for map must all be the same length. Got lengths: {iterable_parameter_lengths}"
        )

    map_length = list(lengths)[0]

    task_runs = []
    for i in range(map_length):
        call_parameters = {key: value[i] for key, value in iterable_parameters.items()}
        call_parameters.update({key: value for key, value in static_parameters.items()})
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

    return await gather(*task_runs)


async def collect_task_run_inputs(expr: Any, max_depth: int = -1) -> Set[TaskRunInput]:
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

    def add_futures_and_states_to_inputs(obj):
        if isinstance(obj, allow_failure):
            obj = obj.unwrap()

        if isinstance(obj, PrefectFuture):
            run_async_from_worker_thread(obj._wait_for_submission)
            inputs.add(TaskRunResult(id=obj.task_run.id))
        elif isinstance(obj, State):
            if obj.state_details.task_run_id:
                inputs.add(TaskRunResult(id=obj.state_details.task_run_id))
        else:
            state = get_state_for_result(obj)
            if state and state.state_details.task_run_id:
                inputs.add(TaskRunResult(id=state.state_details.task_run_id))

    await run_sync_in_worker_thread(
        visit_collection,
        expr,
        visit_fn=add_futures_and_states_to_inputs,
        return_data=False,
        max_depth=max_depth,
    )

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
    task_run_name = f"{task.name}-{stable_hash(task.task_key)[:8]}-{dynamic_key}"

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
            background_tasks = maybe_flow_run_context.background_tasks
        else:
            # Otherwise, retrieve a new client
            client = await stack.enter_async_context(get_client())
            interruptible = False
            background_tasks = await stack.enter_async_context(
                anyio.create_task_group()
            )

        await stack.enter_async_context(report_task_run_crashes(task_run, client))

        # TODO: Use the background tasks group to manage logging for this task

        connect_error = await client.api_healthcheck()
        if connect_error:
            raise RuntimeError(
                f"Cannot orchestrate task run '{task_run.id}'. "
                f"Failed to connect to API at {client.api_url}."
            ) from connect_error

        try:
            return await orchestrate_task_run(
                task=task,
                task_run=task_run,
                parameters=parameters,
                wait_for=wait_for,
                result_factory=result_factory,
                interruptible=interruptible,
                client=client,
            )
        except Abort:
            # Task run already completed, just fetch its state
            task_run = await client.read_task_run(task_run.id)
            task_run_logger(task_run).info(
                f"Task run '{task_run.id}' already finished."
            )
            return task_run.state


async def orchestrate_task_run(
    task: Task,
    task_run: TaskRun,
    parameters: Dict[str, Any],
    wait_for: Optional[Iterable[PrefectFuture]],
    result_factory: ResultFactory,
    interruptible: bool,
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
        result_factory=result_factory,
    )

    try:
        # Resolve futures in parameters into data
        resolved_parameters = await resolve_inputs(parameters)
        # Resolve futures in any non-data dependencies to ensure they are ready
        await resolve_inputs(wait_for, return_data=False)
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
    cache_key = (
        task.cache_key_fn(task_run_context, resolved_parameters)
        if task.cache_key_fn
        else None
    )

    # Transition from `PENDING` -> `RUNNING`
    state = await propose_state(
        client,
        Running(state_details=StateDetails(cache_key=cache_key)),
        task_run_id=task_run.id,
    )

    # Only run the task if we enter a `RUNNING` state
    while state.is_running():
        # Retrieve the latest metadata for the task run context
        task_run = await client.read_task_run(task_run.id)

        try:
            args, kwargs = parameters_to_args_kwargs(task.fn, resolved_parameters)

            if PREFECT_DEBUG_MODE.value():
                logger.debug(f"Executing {call_repr(task.fn, *args, **kwargs)}")
            else:
                logger.debug(f"Beginning execution...", extra={"state_message": True})

            with task_run_context.copy(
                update={"task_run": task_run, "start_time": pendulum.now("UTC")}
            ):
                if task.isasync:
                    result = await task.fn(*args, **kwargs)
                else:
                    run_sync = (
                        run_sync_in_interruptible_worker_thread
                        if interruptible
                        else run_sync_in_worker_thread
                    )
                    result = await run_sync(task.fn, *args, **kwargs)

        except Exception:
            logger.exception("Encountered exception during execution:")
            terminal_state = await exception_to_failed_state(
                message="Task run encountered an exception:",
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
            state = await propose_state(client, Running(), task_run_id=task_run.id)

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


@asynccontextmanager
async def report_flow_run_crashes(flow_run: FlowRun, client: OrionClient):
    """
    Detect flow run crashes during this context and update the run to a proper final
    state.

    This context _must_ reraise the exception to properly exit the run.
    """
    try:
        yield
    except Abort:
        # Do not capture aborts as crashes
        raise
    except BaseException as exc:
        state = await exception_to_crashed_state(exc)
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


@asynccontextmanager
async def report_task_run_crashes(task_run: TaskRun, client: OrionClient):
    """
    Detect task run crashes during this context and update the run to a proper final
    state.

    This context _must_ reraise the exception to properly exit the run.
    """
    try:
        yield
    except Abort:
        # Do not capture aborts as crashes
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

    def resolve_input(expr):
        state = None
        should_allow_failure = False

        if isinstance(expr, allow_failure):
            expr = expr.unwrap()
            should_allow_failure = True

        if isinstance(expr, Quote):
            return expr.unquote()
        elif isinstance(expr, PrefectFuture):
            state = run_async_from_worker_thread(expr._wait)
        elif isinstance(expr, State):
            state = expr
        else:
            return expr

        # Do not allow uncompleted upstreams except failures when `allow_failure` has
        # been used
        if not state.is_completed() and not (
            should_allow_failure and state.is_failed()
        ):
            raise UpstreamTaskError(
                f"Upstream task run '{state.state_details.task_run_id}' did not reach a 'COMPLETED' state."
            )

        # Only retrieve the result if requested as it may be expensive
        return state.result(raise_on_failure=False, fetch=True) if return_data else None

    return await run_sync_in_worker_thread(
        visit_collection,
        parameters,
        visit_fn=resolve_input,
        return_data=return_data,
        max_depth=max_depth,
    )


async def propose_state(
    client: OrionClient,
    state: State,
    force: bool = False,
    task_run_id: UUID = None,
    flow_run_id: UUID = None,
) -> State:
    """
    Propose a new state for a flow run or task run, invoking Orion orchestration logic.

    If the proposed state is accepted, the provided `state` will be augmented with
     details and returned.

    If the proposed state is rejected, a new state returned by the Orion API will be
    returned.

    If the proposed state results in a WAIT instruction from the Orion API, the
    function will sleep and attempt to propose the state again.

    If the proposed state results in an ABORT instruction from the Orion API, an
    error will be raised.

    Args:
        state: a new state for the task or flow run
        task_run_id: an optional task run id, used when proposing task run states
        flow_run_id: an optional flow run id, used when proposing flow run states

    Returns:
        a [State model][prefect.orion.schemas.states] representation of the flow or task run
            state

    Raises:
        ValueError: if neither task_run_id or flow_run_id is provided
        prefect.exceptions.Abort: if an ABORT instruction is received from
            the Orion API
    """

    # Determine if working with a task run or flow run
    if not task_run_id and not flow_run_id:
        raise ValueError("You must provide either a `task_run_id` or `flow_run_id`")

    # Handle task and sub-flow tracing
    if state.is_final():
        if state.data is not None:
            link_state_to_result(
                state, await state.result(raise_on_failure=False, fetch=True)
            )

    # Attempt to set the state
    if task_run_id:
        response = await client.set_task_run_state(
            task_run_id,
            state,
            force=force,
        )
    elif flow_run_id:
        response = await client.set_flow_run_state(
            flow_run_id,
            state,
            force=force,
        )
    else:
        raise ValueError(
            "Neither flow run id or task run id were provided. At least one must "
            "be given."
        )

    # Parse the response to return the new state
    if response.status == SetStateStatus.ACCEPT:
        # Update the state with the details if provided
        if response.state.state_details:
            state.state_details = response.state.state_details
        return state

    elif response.status == SetStateStatus.ABORT:
        raise prefect.exceptions.Abort(response.details.reason)

    elif response.status == SetStateStatus.WAIT:
        engine_logger.debug(
            f"Received wait instruction for {response.details.delay_seconds}s: "
            f"{response.details.reason}"
        )
        await anyio.sleep(response.details.delay_seconds)
        return await propose_state(
            client,
            state,
            task_run_id=task_run_id,
            flow_run_id=flow_run_id,
        )

    elif response.status == SetStateStatus.REJECT:
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


if __name__ == "__main__":
    import os
    import sys

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
