from typing import Any
from uuid import uuid4

import pytest

from prefect.client.schemas.objects import StateDetails, StateType
from prefect.exceptions import UpstreamTaskError
from prefect.states import Cancelled, Completed, Crashed, Failed, Pending, State
from prefect.utilities.annotations import allow_failure
from prefect.utilities.engine import resolve_inputs, resolve_inputs_sync


def dependency_state(case: str) -> State[Any]:
    state_details = StateDetails(task_run_id=uuid4())

    if case == "completed":
        return Completed(data="completed", state_details=state_details)
    if case == "failed":
        return Failed(data=ValueError("failed"), state_details=state_details)
    if case == "cancelled":
        return Cancelled(state_details=state_details)
    if case == "crashed":
        return Crashed(state_details=state_details)
    if case == "legacy_not_ready":
        return Pending(name="NotReady", state_details=state_details)

    cause_type = {
        "failed_not_ready": StateType.FAILED,
        "cancelled_not_ready": StateType.CANCELLED,
        "crashed_not_ready": StateType.CRASHED,
    }[case]
    return Pending(
        name="NotReady",
        state_details=StateDetails(
            task_run_id=state_details.task_run_id,
            upstream_cause_task_run_id=uuid4(),
            upstream_cause_state_type=cause_type,
            upstream_cause_state_name=cause_type.value.capitalize(),
        ),
    )


@pytest.mark.parametrize(
    "case,include_blocked,allowed",
    [
        ("completed", True, True),
        ("failed", True, True),
        ("cancelled", True, False),
        ("crashed", True, False),
        ("failed_not_ready", True, True),
        ("cancelled_not_ready", True, False),
        ("crashed_not_ready", True, False),
        ("legacy_not_ready", True, True),
        ("completed", False, True),
        ("failed", False, True),
        ("cancelled", False, False),
        ("crashed", False, False),
        ("failed_not_ready", False, False),
        ("cancelled_not_ready", False, False),
        ("crashed_not_ready", False, False),
        ("legacy_not_ready", False, False),
    ],
)
class TestDependencyResolutionPolicy:
    def test_sync_resolver(self, case: str, include_blocked: bool, allowed: bool):
        state = dependency_state(case)
        parameters = {"value": allow_failure(state, include_blocked=include_blocked)}

        if not allowed:
            with pytest.raises(UpstreamTaskError):
                resolve_inputs_sync(parameters)
            return

        resolved = resolve_inputs_sync(parameters)
        if case == "completed":
            assert resolved == {"value": "completed"}
        elif case == "failed":
            assert isinstance(resolved["value"], ValueError)
        else:
            assert resolved == {"value": None}

    async def test_async_resolver(
        self, case: str, include_blocked: bool, allowed: bool
    ):
        state = dependency_state(case)
        parameters = {"value": allow_failure(state, include_blocked=include_blocked)}

        if not allowed:
            with pytest.raises(UpstreamTaskError):
                await resolve_inputs(parameters)
            return

        resolved = await resolve_inputs(parameters)
        if case == "completed":
            assert resolved == {"value": "completed"}
        elif case == "failed":
            assert isinstance(resolved["value"], ValueError)
        else:
            assert resolved == {"value": None}


def test_upstream_error_retains_immediate_and_root_metadata():
    immediate_task_run_id = uuid4()
    root_task_run_id = uuid4()
    state = Pending(
        name="NotReady",
        state_details=StateDetails(
            task_run_id=immediate_task_run_id,
            upstream_cause_task_run_id=root_task_run_id,
            upstream_cause_state_type=StateType.FAILED,
            upstream_cause_state_name="Failed",
        ),
    )

    with pytest.raises(UpstreamTaskError) as exc_info:
        resolve_inputs_sync({"value": allow_failure(state, include_blocked=False)})

    assert str(exc_info.value) == (
        f"Upstream task run '{immediate_task_run_id}' did not reach a"
        " 'COMPLETED' state."
    )
    assert exc_info.value.upstream_task_run_id == immediate_task_run_id
    assert exc_info.value.upstream_state_type == StateType.PENDING
    assert exc_info.value.upstream_state_name == "NotReady"
    assert exc_info.value.root_cause_task_run_id == root_task_run_id
    assert exc_info.value.root_cause_state_type == StateType.FAILED
    assert exc_info.value.root_cause_state_name == "Failed"
