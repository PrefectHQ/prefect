import asyncio
import logging
import os
import random
import sys
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
from typing_extensions import Literal

import prefect
import prefect.context
import prefect.plugins
from prefect._internal.compatibility.deprecated import deprecated_parameter
from prefect._internal.compatibility.experimental import experimental_parameter
from prefect._internal.concurrency.api import create_call, from_async
from prefect._internal.concurrency.cancellation import CancelledError
from prefect.client.orchestration import PrefectClient, get_client
from prefect.client.schemas import TaskRun
from prefect.client.schemas.objects import (
    StateDetails,
    StateType,
    TaskRunInput,
)
from prefect.client.schemas.responses import SetStateStatus
from prefect.client.utilities import inject_client
from prefect.context import (
    FlowRunContext,
    TagsContext,
    TaskRunContext,
)
from prefect.exceptions import (
    Abort,
    FlowPauseTimeout,
    MappingLengthMismatch,
    MappingMissingIterable,
    NotPausedError,
    Pause,
    UpstreamTaskError,
)
from prefect.futures import PrefectFuture, call_repr
from prefect.input import keyset_from_paused_state
from prefect.input.run_input import run_input_subclass_from_type
from prefect.logging.configuration import setup_logging
from prefect.logging.handlers import APILogHandler
from prefect.logging.loggers import (
    get_logger,
    get_run_logger,
    patch_print,
    task_run_logger,
)
from prefect.results import ResultFactory, UnknownResult
from prefect.settings import (
    PREFECT_DEBUG_MODE,
    PREFECT_TASK_INTROSPECTION_WARN_THRESHOLD,
    PREFECT_TASKS_REFRESH_CACHE,
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
    _resolve_custom_task_run_name,
    check_api_reachable,
    collect_task_run_inputs,
    emit_task_run_state_change_event,
    propose_state,
    resolve_inputs,
    should_log_prints,
)

R = TypeVar("R")
T = TypeVar("T")
EngineReturnType = Literal["future", "state", "result"]

NUM_CHARS_DYNAMIC_KEY = 8

engine_logger = get_logger("engine")


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


async def _run_task_hooks(task: Task, task_run: TaskRun, state: State) -> None:
    """Run the on_failure and on_completion hooks for a task, making sure to
    catch and log any errors that occur.
    """
    hooks = None
    if state.is_failed() and task.on_failure_hooks:
        hooks = task.on_failure_hooks
    elif state.is_completed() and task.on_completion_hooks:
        hooks = task.on_completion_hooks

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


async def create_autonomous_task_run(task: Task, parameters: Dict[str, Any]) -> TaskRun:
    """
    Create a task run in the API for an autonomous task submission and store
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
        from prefect.new_flow_engine import (
            load_flow_and_flow_run,
            run_flow_async,
            run_flow_sync,
        )

        flow_run, flow = load_flow_and_flow_run(flow_run_id=flow_run_id)
        # run the flow
        if flow.isasync:
            run_sync(run_flow_async(flow, flow_run=flow_run))
        else:
            run_flow_sync(flow, flow_run=flow_run)
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
