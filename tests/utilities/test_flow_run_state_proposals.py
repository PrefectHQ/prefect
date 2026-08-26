from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID, uuid4

import pytest

from prefect.client.schemas import OrchestrationResult
from prefect.client.schemas.objects import StateDetails
from prefect.client.schemas.responses import (
    SetStateStatus,
    StateAbortDetails,
    StateAcceptDetails,
    StateRejectDetails,
    StateResponseDetails,
    StateWaitDetails,
)
from prefect.exceptions import Abort, Pause
from prefect.states import Paused, Pending, Running, State
from prefect.types._datetime import now
from prefect.utilities.flow_run_state_proposals import (
    FlowRunStateProposer,
    SyncFlowRunStateProposer,
)

Mode = Literal["async", "sync"]


@dataclass(frozen=True)
class RequestCall:
    flow_run_id: UUID | str
    state: State[Any]
    force: bool


class ScriptedStateRequest:
    def __init__(self, responses: list[OrchestrationResult[Any]]) -> None:
        self.responses = responses.copy()
        self.calls: list[RequestCall] = []

    def __call__(
        self,
        flow_run_id: UUID | str,
        state: State[Any],
        force: bool = False,
    ) -> OrchestrationResult[Any]:
        self.calls.append(RequestCall(flow_run_id, state, force))
        return self.responses.pop(0)


class ScriptedAsyncStateRequest:
    def __init__(self, responses: list[OrchestrationResult[Any]]) -> None:
        self.responses = responses.copy()
        self.calls: list[RequestCall] = []

    async def __call__(
        self,
        flow_run_id: UUID | str,
        state: State[Any],
        force: bool = False,
    ) -> OrchestrationResult[Any]:
        self.calls.append(RequestCall(flow_run_id, state, force))
        return self.responses.pop(0)


def orchestration_result(
    status: SetStateStatus,
    details: StateResponseDetails,
    state: State[Any] | None = None,
) -> OrchestrationResult[Any]:
    return OrchestrationResult(status=status, details=details, state=state)


async def propose_with_script(
    mode: Mode,
    responses: list[OrchestrationResult[Any]],
    flow_run_id: UUID,
    state: State[Any],
    *,
    force: bool = False,
) -> tuple[State[Any], list[RequestCall]]:
    if mode == "async":
        request = ScriptedAsyncStateRequest(responses)
        returned = await FlowRunStateProposer(request).propose(
            flow_run_id, state, force=force
        )
    else:
        request = ScriptedStateRequest(responses)
        returned = SyncFlowRunStateProposer(request).propose(
            flow_run_id, state, force=force
        )
    return returned, request.calls


@pytest.mark.parametrize("mode", ["async", "sync"])
async def test_waits_then_hydrates_accepted_state(mode: Mode):
    flow_run_id = uuid4()
    proposed = Running(message="client proposal", data={"result": 42})
    accepted = Running(
        id=uuid4(),
        timestamp=now("UTC"),
        state_details=StateDetails(flow_run_id=flow_run_id),
    )

    returned, calls = await propose_with_script(
        mode,
        [
            orchestration_result(
                SetStateStatus.WAIT,
                StateWaitDetails(delay_seconds=0, reason="try again"),
            ),
            orchestration_result(
                SetStateStatus.ACCEPT,
                StateAcceptDetails(),
                accepted,
            ),
        ],
        flow_run_id,
        proposed,
        force=True,
    )

    assert returned is proposed
    assert returned.id == accepted.id
    assert returned.timestamp == accepted.timestamp
    assert returned.state_details == accepted.state_details
    assert returned.message == "client proposal"
    assert returned.data == {"result": 42}
    assert calls == [
        RequestCall(flow_run_id, proposed, True),
        RequestCall(flow_run_id, proposed, True),
    ]


@pytest.mark.parametrize("mode", ["async", "sync"])
async def test_returns_server_state_when_proposal_is_rejected(mode: Mode):
    flow_run_id = uuid4()
    rejected = Pending(message="retry later")
    response = orchestration_result(
        SetStateStatus.REJECT,
        StateRejectDetails(reason="not ready"),
        rejected,
    )

    returned, calls = await propose_with_script(
        mode,
        [response],
        flow_run_id,
        Running(),
    )

    assert returned is response.state
    assert returned == rejected
    assert len(calls) == 1


@pytest.mark.parametrize("mode", ["async", "sync"])
@pytest.mark.parametrize(
    ("response", "expected_exception"),
    [
        (
            orchestration_result(
                SetStateStatus.REJECT,
                StateRejectDetails(reason="paused"),
                Paused(),
            ),
            Pause,
        ),
        (
            orchestration_result(
                SetStateStatus.ABORT,
                StateAbortDetails(reason="stop"),
            ),
            Abort,
        ),
    ],
)
async def test_raises_for_terminal_orchestration_instructions(
    mode: Mode,
    response: OrchestrationResult[Any],
    expected_exception: type[Exception],
):
    with pytest.raises(expected_exception):
        await propose_with_script(mode, [response], uuid4(), Running())


@pytest.mark.parametrize("mode", ["async", "sync"])
async def test_requires_flow_run_id_before_requesting_state(mode: Mode):
    response = orchestration_result(
        SetStateStatus.ACCEPT,
        StateAcceptDetails(),
        Running(),
    )

    with pytest.raises(ValueError, match="flow_run_id"):
        await propose_with_script(
            mode,
            [response],
            None,  # type: ignore[arg-type]
            Running(),
        )
