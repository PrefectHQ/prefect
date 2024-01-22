"""
Client-side execution and orchestration of tasks without a parent flow run.

## Engine process overview

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
import random
import signal
import time
from contextlib import AsyncExitStack, asynccontextmanager
from functools import partial
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Set,
    TypeVar,
    Union,
)
from uuid import UUID, uuid4

import anyio
import pendulum
from typing_extensions import Literal

import prefect
import prefect.context
import prefect.plugins
from prefect._internal.concurrency.api import create_call, from_async, from_sync
from prefect._internal.concurrency.cancellation import CancelledError, get_deadline
from prefect.client.orchestration import PrefectClient, get_client
from prefect.client.schemas import OrchestrationResult, TaskRun
from prefect.client.schemas.objects import (
    StateDetails,
    StateType,
    TaskRunInput,
    TaskRunResult,
)
from prefect.client.schemas.responses import SetStateStatus
from prefect.client.utilities import inject_client
from prefect.context import (
    FlowRunContext,
    TagsContext,
    TaskRunContext,
)
from prefect.events import Event, emit_event
from prefect.exceptions import (
    Abort,
    MappingLengthMismatch,
    MappingMissingIterable,
    Pause,
    PrefectException,
    TerminationSignal,
    UpstreamTaskError,
)
from prefect.futures import PrefectFuture, call_repr
from prefect.input import RunInput
from prefect.logging.configuration import setup_logging
from prefect.logging.handlers import APILogHandler
from prefect.logging.loggers import (
    get_logger,
    get_run_logger,
    patch_print,
    task_run_logger,
)
from prefect.results import BaseResult, ResultFactory, UnknownResult
from prefect.settings import (
    PREFECT_DEBUG_MODE,
    PREFECT_LOGGING_LOG_PRINTS,
    PREFECT_TASK_INTROSPECTION_WARN_THRESHOLD,
    PREFECT_TASKS_REFRESH_CACHE,
)
from prefect.states import (
    Completed,
    Paused,
    Pending,
    Running,
    State,
    Suspended,
    exception_to_crashed_state,
    exception_to_failed_state,
    get_state_exception,
    is_state,
    return_value_to_state,
)
from prefect.task_runners import (
    BaseTaskRunner,
    TaskConcurrencyType,
)
from prefect.tasks import Task
from prefect.utilities.annotations import allow_failure, quote, unmapped
from prefect.utilities.asyncutils import (
    gather,
    is_async_fn,
)
from prefect.utilities.callables import (
    collapse_variadic_parameters,
    explode_variadic_parameter,
    get_parameter_defaults,
    parameters_to_args_kwargs,
)
from prefect.utilities.collections import StopVisiting, isiterable, visit_collection
from prefect.utilities.importtools import import_object
from prefect.utilities.pydantic import PartialModel
from prefect.utilities.text import truncated_to

R = TypeVar("R")
T = TypeVar("T", bound=RunInput)
EngineReturnType = Literal["future", "state", "result"]


API_HEALTHCHECKS = {}
UNTRACKABLE_TYPES = {bool, type(None), type(...), type(NotImplemented)}
engine_logger = get_logger("engine")


async def load_task_from_entrypoint(entrypoint: str) -> Task:
    """
    Load a task from an entrypoint string

    Args:
        - entrypoint (str): The entrypoint string to load a task from

    Returns:
        - Task: The loaded task
    """

    # Load the task from the entrypoint
    task = import_object(entrypoint)

    if not isinstance(task, Task):
        raise TypeError(f"Entrypoint {entrypoint} did not return a Task")

    return task


def enter_task_run_engine_from_subprocess(task_run_id: UUID) -> State:
    """
    Sync entrypoint for task runs that have been submitted for execution

    Differs from `enter_flow_run_engine_from_flow_call` in that we have a flow run id
    but not a flow object. The flow must be retrieved before execution can begin.
    Additionally, this assumes that the caller is always in a context without an event
    loop as this should be called from a fresh process.
    """

    # Ensure collections are imported and have the opportunity to register types before
    # loading the user code from the deployment
    prefect.plugins.load_prefect_collections()

    setup_logging()

    state = from_sync.wait_for_call_in_new_thread(
        create_call(retrieve_task_then_begin_task_run, task_run_id),
        contexts=[capture_sigterm()],
    )

    APILogHandler.flush()
    return state


@inject_client
async def retrieve_task_then_begin_task_run(
    task_run_id: UUID, client: PrefectClient
) -> State:
    """
    Async entrypoint for task runs that have been submitted for execution by an agent

    - Retrieves the deployment information
    - Loads the task object using deployment information
    - Updates the task run version
    """
    task_run = await client.read_task_run(task_run_id)

    entrypoint = os.environ.get("PREFECT__TASK_ENTRYPOINT")

    try:
        task = await load_task_from_entrypoint(entrypoint)
    except Exception:
        message = "Task could not be retrieved from entrypoint"
        task_run_logger(task_run).exception(message)
        state = await exception_to_failed_state(message=message)
        await client.set_task_run_state(
            state=state, task_run_id=task_run_id, force=True
        )
        return state

    parameters = task_run.parameters

    # Ensure default values are populated
    parameters = {**get_parameter_defaults(task.fn), **parameters}

    return await begin_task_run(
        task=task,
        task_run=task_run,
        parameters=parameters,
    )


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
    This function recurses through an expression to generate a set of any discernible
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
        # Expressions inside quotes should not be traversed
        elif isinstance(obj, quote):
            raise StopVisiting
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
    flow_run_context = prefect.context.FlowRunContext.get()
    if flow_run_context:
        flow_run = flow_run_context.flow_run
    else:
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
    task_introspection_start_time = time.perf_counter()
    try:
        # Resolve futures in parameters into data
        resolved_parameters = await resolve_inputs(parameters)
        # Resolve futures in any non-data dependencies to ensure they are ready
        await resolve_inputs({"wait_for": wait_for}, return_data=False)
    except UpstreamTaskError as upstream_exc:
        return await propose_task_run_state(
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

    # Completed states with persisted results should have result data. If it's missing,
    # this could be a manual state transition, so we should use the Unknown result type
    # to represent that we know we don't know the result.
    if (
        last_state
        and last_state.is_completed()
        and result_factory.persist_result
        and not last_state.data
    ):
        state = await propose_task_run_state(
            client,
            state=Completed(data=await UnknownResult.create()),
            task_run_id=task_run.id,
            force=True,
        )

    # Transition from `PENDING` -> `RUNNING`
    try:
        state = await propose_task_run_state(
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
                state = await propose_task_run_state(
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

            if terminal_state.is_failed():
                # Defer to user to decide whether failure is retriable
                terminal_state.state_details.retriable = (
                    await _check_task_failure_retriable(task, task_run, terminal_state)
                )
            state = await propose_task_run_state(
                client, terminal_state, task_run_id=task_run.id
            )

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

            if not state.is_final() and not state.is_paused():
                logger.info(
                    (
                        f"Received non-final state {state.name!r} when proposing final"
                        f" state {terminal_state.name!r} and will attempt to run"
                        " again..."
                    ),
                    extra={"send_to_api": False},
                )
                # Attempt to enter a running state again
                state = await propose_task_run_state(
                    client, Running(), task_run_id=task_run.id
                )
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
    def cancel_task_run(*args):
        raise TerminationSignal(signal=signal.SIGTERM)

    original_term_handler = None
    try:
        original_term_handler = signal.signal(signal.SIGTERM, cancel_task_run)
    except ValueError:
        # Signals only work in the main thread
        pass

    try:
        yield
    except TerminationSignal as exc:
        # Termination signals are swapped out during a task run to perform
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
            #       incorrectly evaluate to false — to resolve this, we must track all
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


async def propose_task_run_state(
    client: PrefectClient,
    state: State,
    task_run_id: UUID,
    force: bool = False,
) -> State:
    """
    Propose a new state for a task run, invoking Prefect orchestration logic.

    If the proposed state is accepted, the provided `state` will be augmented with
     details and returned.

    If the proposed state is rejected, a new state returned by the Prefect API will be
    returned.

    If the proposed state results in a WAIT instruction from the Prefect API, the
    function will sleep and attempt to propose the state again.

    If the proposed state results in an ABORT instruction from the Prefect API, an
    error will be raised.

    Args:
        state: a new state for the task run

    Returns:
        a [State model][prefect.client.schemas.objects.State] representation of the
            task run state

    Raises:
        ValueError: if neither task_run_id is provided
        prefect.exceptions.Abort: if an ABORT instruction is received from
            the Prefect API
    """

    # Handle task tracing
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
    set_state = partial(client.set_task_run_state, task_run_id, state, force=force)
    response = await set_state_and_handle_waits(set_state)

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
            raise Pause(response.details.reason, state=response.state)
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


def should_log_prints(_task: Task) -> bool:
    return _task.log_prints or PREFECT_LOGGING_LOG_PRINTS.value()


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


def _get_hook_name(hook: Callable) -> str:
    return (
        hook.__name__
        if hasattr(hook, "__name__")
        else (
            hook.func.__name__ if isinstance(hook, partial) else hook.__class__.__name__
        )
    )


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
