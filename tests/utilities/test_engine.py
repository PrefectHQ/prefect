from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

import prefect.utilities.engine as engine
from prefect._internal.uuid7 import uuid7
from prefect.client.schemas.objects import State, StateDetails
from prefect.client.schemas.responses import (
    OrchestrationResult,
    SetStateStatus,
    StateAbortDetails,
    StateAcceptDetails,
    StateRejectDetails,
    StateResponseDetails,
    StateWaitDetails,
)
from prefect.exceptions import Abort, Pause
from prefect.states import Paused, Pending, Running
from prefect.types._datetime import now


def _orchestration_result(
    status: SetStateStatus,
    details: StateResponseDetails,
    state: State[Any] | None = None,
) -> OrchestrationResult[Any]:
    return OrchestrationResult(state=state, status=status, details=details)


async def test_propose_state_with_result_hydrates_accepted_proposal():
    flow_run_id = uuid4()
    proposed_details = StateDetails(transition_id=uuid4())
    proposed = Running(
        message="client proposal",
        state_details=proposed_details,
        data={"typed": "payload"},
    )
    server_details = StateDetails(flow_run_id=flow_run_id, transition_id=uuid4())
    server_state = Running(
        id=uuid7(),
        timestamp=now("UTC"),
        message="server response",
        state_details=server_details,
    )
    details = StateAcceptDetails()
    result = _orchestration_result(SetStateStatus.ACCEPT, details, server_state)
    client = MagicMock()
    client.set_flow_run_state = AsyncMock(return_value=result)

    returned = await engine.propose_state_with_result(
        client, proposed, flow_run_id, force=True
    )

    assert returned is result
    assert returned.details is details
    assert returned.state is proposed
    assert proposed.id == server_state.id
    assert proposed.timestamp == server_state.timestamp
    assert proposed.state_details == server_details
    assert proposed.message == "client proposal"
    assert proposed.data == {"typed": "payload"}
    client.set_flow_run_state.assert_awaited_once_with(
        flow_run_id, proposed, force=True
    )


@pytest.mark.parametrize(
    ("status", "details", "server_state"),
    [
        (
            SetStateStatus.WAIT,
            StateWaitDetails(
                delay_seconds=2,
                reason="binding is not visible",
                max_wait_seconds=17,
            ),
            None,
        ),
        (
            SetStateStatus.REJECT,
            StateRejectDetails(reason="rejected"),
            Paused(),
        ),
        (
            SetStateStatus.ABORT,
            StateAbortDetails(reason="stale claim"),
            None,
        ),
    ],
)
async def test_propose_state_with_result_preserves_non_accept_outcomes(
    status: SetStateStatus,
    details: StateResponseDetails,
    server_state: State[Any] | None,
    monkeypatch: pytest.MonkeyPatch,
):
    flow_run_id = uuid4()
    proposed = Running()
    result = _orchestration_result(status, details, server_state)
    original_response_state = result.state
    client = MagicMock()
    client.set_flow_run_state = AsyncMock(return_value=result)
    sleep = AsyncMock()
    monkeypatch.setattr(engine.anyio, "sleep", sleep)

    returned = await engine.propose_state_with_result(
        client, proposed, flow_run_id, force=True
    )

    assert returned is result
    assert returned.details is details
    assert returned.state is original_response_state
    client.set_flow_run_state.assert_awaited_once_with(
        flow_run_id, proposed, force=True
    )
    sleep.assert_not_awaited()


def test_propose_state_with_result_sync_hydrates_one_accepted_attempt():
    flow_run_id = uuid4()
    proposed = Running(message="client proposal")
    server_state = Running(
        id=uuid7(),
        timestamp=now("UTC"),
        state_details=StateDetails(flow_run_id=flow_run_id),
    )
    result = _orchestration_result(
        SetStateStatus.ACCEPT,
        StateAcceptDetails(),
        server_state,
    )
    client = MagicMock()
    client.set_flow_run_state.return_value = result

    returned = engine.propose_state_with_result_sync(
        client, proposed, flow_run_id, force=True
    )

    assert returned is result
    assert returned.state is proposed
    assert proposed.id == server_state.id
    assert proposed.timestamp == server_state.timestamp
    assert proposed.state_details == server_state.state_details
    assert proposed.message == "client proposal"
    client.set_flow_run_state.assert_called_once_with(flow_run_id, proposed, force=True)


def test_propose_state_with_result_sync_preserves_wait_without_sleep(
    monkeypatch: pytest.MonkeyPatch,
):
    flow_run_id = uuid4()
    proposed = Running()
    details = StateWaitDetails(
        delay_seconds=2,
        reason="binding is not visible",
        max_wait_seconds=0,
    )
    result = _orchestration_result(SetStateStatus.WAIT, details)
    client = MagicMock()
    client.set_flow_run_state.return_value = result
    sleep = MagicMock()
    monkeypatch.setattr(engine.time, "sleep", sleep)

    returned = engine.propose_state_with_result_sync(client, proposed, flow_run_id)

    assert returned is result
    assert returned.details is details
    client.set_flow_run_state.assert_called_once_with(
        flow_run_id, proposed, force=False
    )
    sleep.assert_not_called()


async def test_propose_state_with_result_requires_flow_run_id():
    client = MagicMock()
    client.set_flow_run_state = AsyncMock()

    with pytest.raises(ValueError, match="flow_run_id"):
        await engine.propose_state_with_result(
            client,
            Running(),
            None,  # type: ignore[arg-type]
        )

    client.set_flow_run_state.assert_not_awaited()


def test_sync_state_proposal_entry_points_require_flow_run_id():
    client = MagicMock()

    with pytest.raises(ValueError, match="flow_run_id"):
        engine.propose_state_with_result_sync(
            client,
            Running(),
            None,  # type: ignore[arg-type]
        )

    with pytest.raises(ValueError, match="flow_run_id"):
        engine.propose_state_sync(
            client,
            Running(),
            None,  # type: ignore[arg-type]
        )

    client.set_flow_run_state.assert_not_called()


async def test_propose_state_retries_wait_through_client_seam(
    monkeypatch: pytest.MonkeyPatch,
):
    flow_run_id = uuid4()
    transition_id = uuid4()
    proposed = Pending(state_details=StateDetails(transition_id=transition_id))
    wait_result = _orchestration_result(
        SetStateStatus.WAIT,
        StateWaitDetails(delay_seconds=3, reason="wait", max_wait_seconds=30),
    )
    accepted_state = Pending(
        id=uuid7(),
        timestamp=now("UTC"),
        state_details=StateDetails(
            flow_run_id=flow_run_id,
            transition_id=transition_id,
        ),
    )
    accept_result = _orchestration_result(
        SetStateStatus.ACCEPT,
        StateAcceptDetails(),
        accepted_state,
    )
    client = MagicMock()
    client.set_flow_run_state = AsyncMock(side_effect=[wait_result, accept_result])
    sleep = AsyncMock()
    monkeypatch.setattr(engine.anyio, "sleep", sleep)

    state = await engine.propose_state(client, proposed, flow_run_id, force=True)

    assert state is proposed
    assert proposed.id == accepted_state.id
    assert proposed.state_details == accepted_state.state_details
    assert proposed.state_details.transition_id == transition_id
    assert client.set_flow_run_state.await_count == 2
    assert all(
        call.args[1] is proposed for call in client.set_flow_run_state.await_args_list
    )
    sleep.assert_awaited_once_with(3)


def test_propose_state_sync_retries_wait_through_client_seam(
    monkeypatch: pytest.MonkeyPatch,
):
    flow_run_id = uuid4()
    transition_id = uuid4()
    proposed = Pending(state_details=StateDetails(transition_id=transition_id))
    wait_result = _orchestration_result(
        SetStateStatus.WAIT,
        StateWaitDetails(delay_seconds=3, reason="wait", max_wait_seconds=30),
    )
    accepted_state = Pending(
        id=uuid7(),
        timestamp=now("UTC"),
        state_details=StateDetails(
            flow_run_id=flow_run_id,
            transition_id=transition_id,
        ),
    )
    accept_result = _orchestration_result(
        SetStateStatus.ACCEPT,
        StateAcceptDetails(),
        accepted_state,
    )
    client = MagicMock()
    client.set_flow_run_state.side_effect = [wait_result, accept_result]
    sleep = MagicMock()
    monkeypatch.setattr(engine.time, "sleep", sleep)

    state = engine.propose_state_sync(client, proposed, flow_run_id, force=True)

    assert state is proposed
    assert proposed.id == accepted_state.id
    assert proposed.state_details == accepted_state.state_details
    assert proposed.state_details.transition_id == transition_id
    assert client.set_flow_run_state.call_count == 2
    assert all(
        call.args[1] is proposed for call in client.set_flow_run_state.call_args_list
    )
    sleep.assert_called_once_with(3)


@pytest.mark.parametrize(
    ("result", "exception"),
    [
        (
            _orchestration_result(
                SetStateStatus.ABORT,
                StateAbortDetails(reason="stale claim"),
            ),
            Abort,
        ),
        (
            _orchestration_result(
                SetStateStatus.REJECT,
                StateRejectDetails(reason="paused"),
                Paused(),
            ),
            Pause,
        ),
    ],
)
async def test_propose_state_preserves_legacy_terminal_outcome_behavior(
    result: OrchestrationResult[Any],
    exception: type[Exception],
):
    client = MagicMock()
    client.set_flow_run_state = AsyncMock(return_value=result)
    proposed = Running()
    flow_run_id = uuid4()

    with pytest.raises(exception):
        await engine.propose_state(client, proposed, flow_run_id)

    client.set_flow_run_state.assert_awaited_once_with(
        flow_run_id, proposed, force=False
    )
