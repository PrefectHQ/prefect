import asyncio
import contextlib
import os
import signal
import time
from collections.abc import Awaitable, Callable, Generator
from functools import partial
from logging import Logger
from typing import (
    TYPE_CHECKING,
    Any,
    NoReturn,
    Optional,
    TypeVar,
    Union,
    cast,
)
from uuid import UUID

import anyio
from opentelemetry import propagate, trace
from typing_extensions import TypeIs

import prefect
import prefect.exceptions
from prefect._internal.concurrency.cancellation import get_deadline
from prefect.client.schemas import OrchestrationResult, TaskRun
from prefect.client.schemas.objects import TaskRunInput, TaskRunResult
from prefect.client.schemas.responses import (
    SetStateStatus,
    StateAbortDetails,
    StateRejectDetails,
    StateWaitDetails,
)
from prefect.context import FlowRunContext
from prefect.events import Event, emit_event
from prefect.exceptions import (
    Pause,
    PrefectException,
    TerminationSignal,
    UpstreamTaskError,
)
from prefect.flows import Flow
from prefect.futures import PrefectFuture
from prefect.logging.loggers import get_logger
from prefect.results import ResultRecord, should_persist_result
from prefect.settings import PREFECT_LOGGING_LOG_PRINTS
from prefect.states import State
from prefect.tasks import Task
from prefect.utilities.annotations import allow_failure, quote
from prefect.utilities.collections import StopVisiting, visit_collection
from prefect.utilities.text import truncated_to

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient, SyncPrefectClient

API_HEALTHCHECKS: dict[str, float] = {}
UNTRACKABLE_TYPES: set[type[Any]] = {bool, type(None), type(...), type(NotImplemented)}
engine_logger: Logger = get_logger("engine")
T = TypeVar("T")


async def collect_task_run_inputs(expr: Any, max_depth: int = -1) -> set[TaskRunResult]:
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

    inputs: set[TaskRunResult] = set()

    def add_futures_and_states_to_inputs(obj: Any) -> None:
        if isinstance(obj, PrefectFuture):
            inputs.add(TaskRunResult(id=obj.task_run_id))
        elif isinstance(obj, State):
            if obj.state_details.task_run_id:
                inputs.add(
                    TaskRunResult(
                        id=obj.state_details.task_run_id,
                    )
                )
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

    return inputs


def collect_task_run_inputs_sync(
    expr: Any, future_cls: Any = PrefectFuture, max_depth: int = -1
) -> set[TaskRunInput]:
    """
    This function recurses through an expression to generate a set of any discernible
    task run inputs it finds in the data structure. It produces a set of all inputs
    found.

    Examples:
        >>> task_inputs = {
        >>>    k: collect_task_run_inputs_sync(v) for k, v in parameters.items()
        >>> }
    """
    # TODO: This function needs to be updated to detect parameters and constants

    inputs: set[TaskRunInput] = set()

    def add_futures_and_states_to_inputs(obj: Any) -> None:
        if isinstance(obj, future_cls) and hasattr(obj, "task_run_id"):
            inputs.add(
                TaskRunResult(
                    id=obj.task_run_id,
                )
            )
        elif isinstance(obj, State):
            if obj.state_details.task_run_id:
                inputs.add(
                    TaskRunResult(
                        id=obj.state_details.task_run_id,
                    )
                )
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

    return inputs


@contextlib.contextmanager
def capture_sigterm() -> Generator[None, Any, None]:
    def cancel_flow_run(*args: object) -> NoReturn:
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
    parameters: dict[str, Any], return_data: bool = True, max_depth: int = -1
) -> dict[str, Any]:
    """
    Resolve any `Quote`, `PrefectFuture`, or `State` types nested in parameters into
    data.

    Returns:
        A copy of the parameters with resolved data

    Raises:
        UpstreamTaskError: If any of the upstream states are not `COMPLETED`
    """

    futures: set[PrefectFuture[Any]] = set()
    states: set[State[Any]] = set()
    result_by_state: dict[State[Any], Any] = {}

    if not parameters:
        return {}

    def collect_futures_and_states(expr: Any, context: dict[str, Any]) -> Any:
        # Expressions inside quotes should not be traversed
        if isinstance(context.get("annotation"), quote):
            raise StopVisiting()

        if isinstance(expr, PrefectFuture):
            fut: PrefectFuture[Any] = expr
            futures.add(fut)
        if isinstance(expr, State):
            state: State[Any] = expr
            states.add(state)

        return cast(Any, expr)

    visit_collection(
        parameters,
        visit_fn=collect_futures_and_states,
        return_data=False,
        max_depth=max_depth,
        context={},
    )

    # Only retrieve the result if requested as it may be expensive
    if return_data:
        finished_states = [state for state in states if state.is_final()]

        state_results = [
            state.aresult(raise_on_failure=False) for state in finished_states
        ]
        state_results = await asyncio.gather(*state_results)

        for state, result in zip(finished_states, state_results):
            result_by_state[state] = result

    def resolve_input(expr: Any, context: dict[str, Any]) -> Any:
        state: Optional[State[Any]] = None

        # Expressions inside quotes should not be modified
        if isinstance(context.get("annotation"), quote):
            raise StopVisiting()

        if isinstance(expr, PrefectFuture):
            state = expr.state
        elif isinstance(expr, State):
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

    resolved_parameters: dict[str, Any] = {}
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


def _is_result_record(data: Any) -> TypeIs[ResultRecord[Any]]:
    return isinstance(data, ResultRecord)


async def propose_state(
    client: "PrefectClient",
    state: State[Any],
    force: bool = False,
    task_run_id: Optional[UUID] = None,
    flow_run_id: Optional[UUID] = None,
) -> State[Any]:
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
        result: Any
        if _is_result_record(state.data):
            result = state.data.result
        else:
            result = state.data

        link_state_to_result(state, result)

    # Handle repeated WAITs in a loop instead of recursively, to avoid
    # reaching max recursion depth in extreme cases.
    async def set_state_and_handle_waits(
        set_state_func: Callable[[], Awaitable[OrchestrationResult[Any]]],
    ) -> OrchestrationResult[Any]:
        response = await set_state_func()
        while response.status == SetStateStatus.WAIT:
            if TYPE_CHECKING:
                assert isinstance(response.details, StateWaitDetails)
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
        if TYPE_CHECKING:
            assert response.state is not None
        state.id = response.state.id
        state.timestamp = response.state.timestamp
        if response.state.state_details:
            state.state_details = response.state.state_details
        return state

    elif response.status == SetStateStatus.ABORT:
        if TYPE_CHECKING:
            assert isinstance(response.details, StateAbortDetails)

        raise prefect.exceptions.Abort(response.details.reason)

    elif response.status == SetStateStatus.REJECT:
        if TYPE_CHECKING:
            assert response.state is not None
            assert isinstance(response.details, StateRejectDetails)

        if response.state.is_paused():
            raise Pause(response.details.reason, state=response.state)
        return response.state

    else:
        raise ValueError(
            f"Received unexpected `SetStateStatus` from server: {response.status!r}"
        )


def propose_state_sync(
    client: "SyncPrefectClient",
    state: State[Any],
    force: bool = False,
    task_run_id: Optional[UUID] = None,
    flow_run_id: Optional[UUID] = None,
) -> State[Any]:
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
        if _is_result_record(state.data):
            result = state.data.result
        else:
            result = state.data

        link_state_to_result(state, result)

    # Handle repeated WAITs in a loop instead of recursively, to avoid
    # reaching max recursion depth in extreme cases.
    def set_state_and_handle_waits(
        set_state_func: Callable[[], OrchestrationResult[Any]],
    ) -> OrchestrationResult[Any]:
        response = set_state_func()
        while response.status == SetStateStatus.WAIT:
            if TYPE_CHECKING:
                assert isinstance(response.details, StateWaitDetails)
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
        if TYPE_CHECKING:
            assert response.state is not None
        # Update the state with the details if provided
        state.id = response.state.id
        state.timestamp = response.state.timestamp
        if response.state.state_details:
            state.state_details = response.state.state_details
        return state

    elif response.status == SetStateStatus.ABORT:
        if TYPE_CHECKING:
            assert isinstance(response.details, StateAbortDetails)
        raise prefect.exceptions.Abort(response.details.reason)

    elif response.status == SetStateStatus.REJECT:
        if TYPE_CHECKING:
            assert response.state is not None
            assert isinstance(response.details, StateRejectDetails)
        if response.state.is_paused():
            raise Pause(response.details.reason, state=response.state)
        return response.state

    else:
        raise ValueError(
            f"Received unexpected `SetStateStatus` from server: {response.status!r}"
        )


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
    # Drop the data field to avoid holding a strong reference to the result
    # Holding large user objects in memory can cause memory bloat
    linked_state = state.model_copy(update={"data": None})

    if flow_run_context:

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
            flow_run_context.task_run_results[id(obj)] = linked_state

        visit_collection(expr=result, visit_fn=link_if_trackable, max_depth=1)


def should_log_prints(flow_or_task: Union["Flow[..., Any]", "Task[..., Any]"]) -> bool:
    flow_run_context = FlowRunContext.get()

    if flow_or_task.log_prints is None:
        if flow_run_context:
            return flow_run_context.log_prints
        else:
            return PREFECT_LOGGING_LOG_PRINTS.value()

    return flow_or_task.log_prints


async def check_api_reachable(client: "PrefectClient", fail_message: str) -> None:
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
    initial_state: Optional[State[Any]],
    validated_state: State[Any],
    follows: Optional[Event] = None,
) -> Optional[Event]:
    state_message_truncation_length = 100_000

    if _is_result_record(validated_state.data) and should_persist_result():
        data = validated_state.data.metadata.model_dump(mode="json")
    else:
        data = None

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
                    "state_details": initial_state.state_details.model_dump(
                        mode="json",
                        exclude_none=True,
                        exclude_unset=True,
                        exclude={"flow_run_id", "task_run_id"},
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
                "state_details": validated_state.state_details.model_dump(
                    mode="json",
                    exclude_none=True,
                    exclude_unset=True,
                    exclude={"flow_run_id", "task_run_id"},
                ),
                "data": data,
            },
            "task_run": task_run.model_dump(
                mode="json",
                exclude_none=True,
                exclude={
                    "id",
                    "created",
                    "updated",
                    "flow_run_id",
                    "state_id",
                    "state_type",
                    "state_name",
                    "state",
                    # server materialized fields
                    "estimated_start_time_delta",
                    "estimated_run_time",
                },
            ),
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
            "prefect.orchestration": "client",
        },
        follows=follows,
    )


def resolve_to_final_result(expr: Any, context: dict[str, Any]) -> Any:
    """
    Resolve any `PrefectFuture`, or `State` types nested in parameters into
    data. Designed to be use with `visit_collection`.
    """
    state: Optional[State[Any]] = None

    # Expressions inside quotes should not be modified
    if isinstance(context.get("annotation"), quote):
        raise StopVisiting()

    if isinstance(expr, PrefectFuture):
        upstream_task_run: Optional[TaskRun] = context.get("current_task_run")
        upstream_task: Optional["Task[..., Any]"] = context.get("current_task")
        if (
            upstream_task
            and upstream_task_run
            and expr.task_run_id == upstream_task_run.id
        ):
            raise ValueError(
                f"Discovered a task depending on itself. Raising to avoid a deadlock. Please inspect the inputs and dependencies of {upstream_task.name}."
            )

        expr.wait()
        state = expr.state
    elif isinstance(expr, State):
        state = expr
    else:
        return expr

    assert state

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

    result: Any = state.result(raise_on_failure=False, _sync=True)  # pyright: ignore[reportCallIssue] _sync messes up type inference and can be removed once async_dispatch is removed

    if state.state_details.traceparent:
        parameter_context = propagate.extract(
            {"traceparent": state.state_details.traceparent}
        )
        attributes = {}

        # If this future is being used as a parameter (as opposed to just a wait_for),
        # add attributes to the span to indicate the parameter name and type
        if "parameter_name" in context:
            attributes = {
                "prefect.input.name": context["parameter_name"],
                "prefect.input.type": type(result).__name__,
            }

        trace.get_current_span().add_link(
            context=trace.get_current_span(parameter_context).get_span_context(),
            attributes=attributes,
        )

    return result


def resolve_inputs_sync(
    parameters: dict[str, Any], return_data: bool = True, max_depth: int = -1
) -> dict[str, Any]:
    """
    Resolve any `Quote`, `PrefectFuture`, or `State` types nested in parameters into
    data.

    Returns:
        A copy of the parameters with resolved data

    Raises:
        UpstreamTaskError: If any of the upstream states are not `COMPLETED`
    """

    if not parameters:
        return {}

    resolved_parameters: dict[str, Any] = {}
    for parameter, value in parameters.items():
        try:
            resolved_parameters[parameter] = visit_collection(
                value,
                visit_fn=resolve_to_final_result,
                return_data=return_data,
                max_depth=max_depth,
                remove_annotations=True,
                context={"parameter_name": parameter},
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
