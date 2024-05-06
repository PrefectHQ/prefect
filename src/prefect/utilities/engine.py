import asyncio
import contextlib
import inspect
import os
import signal
import time
from functools import partial
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    Optional,
    Set,
    TypeVar,
    Union,
)
from uuid import UUID, uuid4

import anyio
from typing_extensions import Literal

import prefect
import prefect.context
import prefect.plugins
from prefect._internal.concurrency.cancellation import get_deadline
from prefect.client.orchestration import PrefectClient, SyncPrefectClient
from prefect.client.schemas import OrchestrationResult, TaskRun
from prefect.client.schemas.objects import (
    StateType,
    TaskRunInput,
    TaskRunResult,
)
from prefect.client.schemas.responses import SetStateStatus
from prefect.context import (
    FlowRunContext,
)
from prefect.events import Event, emit_event
from prefect.exceptions import (
    Pause,
    PrefectException,
    TerminationSignal,
    UpstreamTaskError,
)
from prefect.flows import Flow
from prefect.futures import PrefectFuture
from prefect.logging.loggers import (
    get_logger,
    task_run_logger,
)
from prefect.results import BaseResult
from prefect.settings import (
    PREFECT_LOGGING_LOG_PRINTS,
)
from prefect.states import (
    State,
    get_state_exception,
    is_state,
)
from prefect.tasks import Task
from prefect.utilities.annotations import allow_failure, quote
from prefect.utilities.asyncutils import (
    gather,
    run_sync,
)
from prefect.utilities.collections import StopVisiting, visit_collection
from prefect.utilities.text import truncated_to

API_HEALTHCHECKS = {}
UNTRACKABLE_TYPES = {bool, type(None), type(...), type(NotImplemented)}
engine_logger = get_logger("engine")
T = TypeVar("T")


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
            isinstance(context.get("annotation"), allow_failure) and state.is_failed()
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
    state: State[object],
    force: bool = False,
    task_run_id: Optional[UUID] = None,
    flow_run_id: Optional[UUID] = None,
) -> State[object]:
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
            raise Pause(response.details.reason, state=response.state)
        return response.state

    else:
        raise ValueError(
            f"Received unexpected `SetStateStatus` from server: {response.status!r}"
        )


def propose_state_sync(
    client: SyncPrefectClient,
    state: State[object],
    force: bool = False,
    task_run_id: Optional[UUID] = None,
    flow_run_id: Optional[UUID] = None,
) -> State[object]:
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
            result = state.result(raise_on_failure=False, fetch=True)
            if inspect.isawaitable(result):
                result = run_sync(result)
        else:
            result = state.data

        link_state_to_result(state, result)

    # Handle repeated WAITs in a loop instead of recursively, to avoid
    # reaching max recursion depth in extreme cases.
    def set_state_and_handle_waits(set_state_func) -> OrchestrationResult:
        response = set_state_func()
        while response.status == SetStateStatus.WAIT:
            engine_logger.debug(
                f"Received wait instruction for {response.details.delay_seconds}s: "
                f"{response.details.reason}"
            )
            time.sleep(response.details.delay_seconds)
            response = set_state_func()
        return response

    # Attempt to set the state
    if task_run_id:
        set_state = partial(client.set_task_run_state, task_run_id, state, force=force)
        response = set_state_and_handle_waits(set_state)
    elif flow_run_id:
        set_state = partial(client.set_flow_run_state, flow_run_id, state, force=force)
        response = set_state_and_handle_waits(set_state)
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
            raise Pause(response.details.reason, state=response.state)
        return response.state

    else:
        raise ValueError(
            f"Received unexpected `SetStateStatus` from server: {response.status!r}"
        )


def _dynamic_key_for_task_run(context: FlowRunContext, task: Task) -> int:
    if context.flow_run is None:  # this is an autonomous task run
        context.task_run_dynamic_keys[task.task_key] = getattr(
            task, "dynamic_key", str(uuid4())
        )

    elif task.task_key not in context.task_run_dynamic_keys:
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


def _get_hook_name(hook: Callable) -> str:
    return (
        hook.__name__
        if hasattr(hook, "__name__")
        else (
            hook.func.__name__ if isinstance(hook, partial) else hook.__class__.__name__
        )
    )


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


def emit_task_run_state_change_event(
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
