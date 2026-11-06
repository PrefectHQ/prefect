import os
import signal
import sys
from pathlib import Path
from unittest.mock import MagicMock, create_autospec
from uuid import UUID, uuid4

import pytest
from prefect_aws.microvm import supervisor
from prefect_aws.microvm.payload import RunHookPayload

from prefect.client.orchestration import SyncPrefectClient
from prefect.client.schemas.objects import FlowRun, State
from prefect.client.schemas.responses import (
    OrchestrationResult,
    SetStateStatus,
    StateAcceptDetails,
    StateRejectDetails,
)
from prefect.engine import _drive_run_flow_result
from prefect.flow_engine import (
    _run_flow_from_runtime_entrypoint,
    load_flow_and_flow_run,
    run_flow,
)
from prefect.states import Completed, Crashed, Failed, Running, StateType

pytestmark = [
    pytest.mark.skipif(sys.platform == "win32", reason="The MicroVM entrypoint forks."),
    pytest.mark.filterwarnings(
        "ignore:This process .* is multi-threaded:DeprecationWarning"
    ),
]

FLOW_RUN_ID = UUID("a3d9b1f2-6c4e-4e8a-b5d7-1f2e3c4d5a6b")


def make_payload(**overrides: object) -> RunHookPayload:
    fields: dict[str, object] = {"v": 1, "flow_run_id": FLOW_RUN_ID}
    fields.update(overrides)
    return RunHookPayload.model_validate(fields)


def flow_run_in(state: State) -> FlowRun:
    return FlowRun(id=FLOW_RUN_ID, flow_id=uuid4(), state=state)


def orchestration_result(status: SetStateStatus) -> OrchestrationResult:
    details = (
        StateAcceptDetails()
        if status == SetStateStatus.ACCEPT
        else StateRejectDetails(reason="rejected for the test")
    )
    return OrchestrationResult(state=None, status=status, details=details)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    mock_client = create_autospec(SyncPrefectClient, instance=True)
    mock_client.__enter__.return_value = mock_client
    mock_client.read_flow_run.return_value = flow_run_in(Running())
    mock_client.set_flow_run_state.return_value = orchestration_result(
        SetStateStatus.ACCEPT
    )
    calls: list[str] = []
    refresh_settings = MagicMock(side_effect=lambda: calls.append("refresh"))

    def get_client(**kwargs: object) -> MagicMock:
        calls.append("get_client")
        assert kwargs == {"sync_client": True}
        return mock_client

    monkeypatch.setattr(supervisor, "refresh_global_settings_context", refresh_settings)
    monkeypatch.setattr(supervisor, "get_client", get_client)
    mock_client.setup_calls = calls
    return mock_client


def child_exits_with(code: int):
    def run_in_child(payload: RunHookPayload) -> None:
        if code:
            raise SystemExit(code)

    return run_in_child


def child_raises(payload: RunHookPayload) -> None:
    raise RuntimeError("flow code failed")


def child_is_killed(payload: RunHookPayload) -> None:
    os.kill(os.getpid(), signal.SIGKILL)


def proposed_states(client: MagicMock) -> list[tuple[State, bool]]:
    return [
        (call.args[1], call.kwargs.get("force", False))
        for call in client.set_flow_run_state.call_args_list
    ]


def test_child_exit_0_reports_nothing(
    monkeypatch: pytest.MonkeyPatch, client: MagicMock
):
    monkeypatch.setattr(supervisor, "execute_flow_run", child_exits_with(0))

    assert supervisor.supervise_flow_run(make_payload()) == 0

    client.read_flow_run.assert_not_called()
    client.set_flow_run_state.assert_not_called()


def test_child_nonzero_exit_proposes_crashed(
    monkeypatch: pytest.MonkeyPatch, client: MagicMock
):
    monkeypatch.setattr(supervisor, "execute_flow_run", child_exits_with(3))

    assert supervisor.supervise_flow_run(make_payload()) == 1

    # The parent's settings predate the API URL and key that `/run` set.
    assert client.setup_calls == ["refresh", "get_client"]
    client.read_flow_run.assert_called_once_with(FLOW_RUN_ID)
    [(state, force)] = proposed_states(client)
    assert state.type == StateType.CRASHED
    assert state.message == "Flow run process exited with code 3."
    assert force is False
    assert client.set_flow_run_state.call_args.args[0] == FLOW_RUN_ID


def test_child_exception_proposes_crashed(
    monkeypatch: pytest.MonkeyPatch, client: MagicMock
):
    monkeypatch.setattr(supervisor, "execute_flow_run", child_raises)

    assert supervisor.supervise_flow_run(make_payload()) == 1

    [(state, _)] = proposed_states(client)
    assert state.message == "Flow run process exited with code 1."


def test_child_killed_by_signal_proposes_crashed(
    monkeypatch: pytest.MonkeyPatch, client: MagicMock
):
    monkeypatch.setattr(supervisor, "execute_flow_run", child_is_killed)

    assert supervisor.supervise_flow_run(make_payload()) == 1

    [(state, force)] = proposed_states(client)
    assert state.type == StateType.CRASHED
    assert state.message == "Flow run process was killed by signal 9."
    assert force is False


@pytest.mark.parametrize("final_state", [Completed(), Failed(), Crashed()])
def test_run_already_final_is_not_moved(
    monkeypatch: pytest.MonkeyPatch, client: MagicMock, final_state: State
):
    monkeypatch.setattr(supervisor, "execute_flow_run", child_exits_with(1))
    client.read_flow_run.return_value = flow_run_in(final_state)

    assert supervisor.supervise_flow_run(make_payload()) == 1

    client.read_flow_run.assert_called_once_with(FLOW_RUN_ID)
    client.set_flow_run_state.assert_not_called()


@pytest.mark.parametrize("status", [SetStateStatus.REJECT, SetStateStatus.WAIT])
def test_crashed_is_forced_only_after_the_plain_proposal_is_not_accepted(
    monkeypatch: pytest.MonkeyPatch, client: MagicMock, status: SetStateStatus
):
    monkeypatch.setattr(supervisor, "execute_flow_run", child_is_killed)
    client.set_flow_run_state.side_effect = [
        orchestration_result(status),
        orchestration_result(SetStateStatus.ACCEPT),
    ]

    assert supervisor.supervise_flow_run(make_payload()) == 1

    assert [force for _, force in proposed_states(client)] == [False, True]
    assert all(state.type == StateType.CRASHED for state, _ in proposed_states(client))


def test_failed_crash_report_still_exits_1(
    monkeypatch: pytest.MonkeyPatch, client: MagicMock
):
    monkeypatch.setattr(supervisor, "execute_flow_run", child_exits_with(1))
    client.read_flow_run.side_effect = ConnectionError("API unreachable")

    assert supervisor.supervise_flow_run(make_payload()) == 1


def test_entrypoint_payload_runs_the_runtime_entrypoint_in_working_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    monkeypatch.chdir(Path.cwd())
    run_from_entrypoint = create_autospec(_run_flow_from_runtime_entrypoint)
    monkeypatch.setattr(
        supervisor, "_run_flow_from_runtime_entrypoint", run_from_entrypoint
    )
    seen_cwd: list[Path] = []
    run_from_entrypoint.side_effect = lambda *args: seen_cwd.append(Path.cwd())

    supervisor.execute_flow_run(
        make_payload(entrypoint="flows/etl.py:etl", working_dir=str(tmp_path))
    )

    run_from_entrypoint.assert_called_once_with(FLOW_RUN_ID, "flows/etl.py:etl")
    assert seen_cwd == [tmp_path.resolve()]


def test_null_entrypoint_loads_the_flow_from_the_flow_run(
    monkeypatch: pytest.MonkeyPatch,
):
    flow_run = flow_run_in(Running())
    flow = MagicMock(name="flow")
    load = create_autospec(load_flow_and_flow_run, return_value=(flow_run, flow))
    run = create_autospec(run_flow, return_value="run result")
    drive = create_autospec(_drive_run_flow_result)
    run_from_entrypoint = create_autospec(_run_flow_from_runtime_entrypoint)
    monkeypatch.setattr(supervisor, "load_flow_and_flow_run", load)
    monkeypatch.setattr(supervisor, "run_flow", run)
    monkeypatch.setattr(supervisor, "_drive_run_flow_result", drive)
    monkeypatch.setattr(
        supervisor, "_run_flow_from_runtime_entrypoint", run_from_entrypoint
    )

    supervisor.execute_flow_run(make_payload(entrypoint=None))

    load.assert_called_once_with(FLOW_RUN_ID)
    assert run.call_args.args == (flow,)
    assert run.call_args.kwargs["flow_run"] is flow_run
    drive.assert_called_once_with(flow, "run result")
    run_from_entrypoint.assert_not_called()
