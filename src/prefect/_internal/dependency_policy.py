"""Internal dependency resolution policy and blocked-state construction."""

from typing import Any

from prefect.client.schemas.objects import StateDetails, StateType
from prefect.exceptions import UpstreamTaskError
from prefect.states import Pending, State
from prefect.utilities.annotations import allow_failure


def state_has_upstream_cause(state: State[Any]) -> bool:
    details = state.state_details
    return any(
        value is not None
        for value in (
            details.upstream_cause_flow_run_id,
            details.upstream_cause_task_run_id,
            details.upstream_cause_state_type,
            details.upstream_cause_state_name,
        )
    )


def dependency_state_allowed(state: State[Any], annotation: Any) -> bool:
    """Return whether a dependency state satisfies the active annotation policy."""
    if state.is_completed():
        return True

    if not isinstance(annotation, allow_failure):
        return False

    if not annotation.include_blocked:
        return state.is_failed() and not state_has_upstream_cause(state)

    if state.is_failed():
        return True

    if not (state.is_pending() and state.name == "NotReady"):
        return False

    if not state_has_upstream_cause(state):
        # Historical NotReady states have no causal provenance. Preserve the
        # existing transitive behavior for the default policy.
        return True

    return state.state_details.upstream_cause_state_type == StateType.FAILED


def upstream_task_error_from_state(state: State[Any]) -> UpstreamTaskError:
    """Create an upstream error with immediate and root-cause metadata."""
    details = state.state_details
    has_root_cause = state_has_upstream_cause(state)
    return UpstreamTaskError(
        f"Upstream task run '{details.task_run_id}' did not reach a 'COMPLETED' state.",
        upstream_flow_run_id=details.flow_run_id,
        upstream_task_run_id=details.task_run_id,
        upstream_state_type=state.type,
        upstream_state_name=state.name,
        root_cause_flow_run_id=(
            details.upstream_cause_flow_run_id
            if has_root_cause
            else details.flow_run_id
        ),
        root_cause_task_run_id=(
            details.upstream_cause_task_run_id
            if has_root_cause
            else details.task_run_id
        ),
        root_cause_state_type=(
            details.upstream_cause_state_type if has_root_cause else state.type
        ),
        root_cause_state_name=(
            details.upstream_cause_state_name if has_root_cause else state.name
        ),
    )


def not_ready_state_from_upstream_error(
    error: UpstreamTaskError,
) -> State[Any]:
    """Create a NotReady state retaining the rejected dependency's root cause."""
    return Pending(
        name="NotReady",
        message=str(error),
        state_details=StateDetails(
            upstream_cause_flow_run_id=error.root_cause_flow_run_id,
            upstream_cause_task_run_id=error.root_cause_task_run_id,
            upstream_cause_state_type=error.root_cause_state_type,
            upstream_cause_state_name=error.root_cause_state_name,
        ),
    )
