from __future__ import annotations

import os
import signal
import subprocess
from time import sleep
from typing import Any, Awaitable, Callable
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import anyio
import pytest

import prefect.exceptions
from prefect import __development_base_path__, flow
from prefect.cli.flow_run import LOGS_WITH_LIMIT_FLAG_DEFAULT_NUM_LOGS
from prefect.client.orchestration import PrefectClient, SyncPrefectClient
from prefect.client.schemas.actions import LogCreate
from prefect.client.schemas.objects import FlowRun
from prefect.deployments.runner import RunnerDeployment
from prefect.settings import PREFECT_UI_URL, temporary_settings
from prefect.settings.context import get_current_settings
from prefect.states import (
    AwaitingRetry,
    Cancelled,
    Completed,
    Crashed,
    Failed,
    Late,
    Pending,
    Retrying,
    Running,
    Scheduled,
    State,
    StateType,
)
from prefect.testing.cli import invoke_and_assert
from prefect.types._datetime import now
from prefect.utilities.asyncutils import run_sync_in_worker_thread


@flow(name="hello")
def hello_flow():
    return "Hello!"


@flow(name="goodbye")
def goodbye_flow():
    return "Goodbye"


@flow()
def tired_flow():
    print("I am so tired...")

    for _ in range(100):
        print("zzzzz...")
        sleep(5)


async def assert_flow_run_is_deleted(prefect_client: PrefectClient, flow_run_id: UUID):
    """
    Make sure that the flow run created for our CLI test is actually deleted.
    """
    with pytest.raises(prefect.exceptions.ObjectNotFound):
        await prefect_client.read_flow_run(flow_run_id)


def assert_flow_run_is_deleted_sync(
    prefect_client: SyncPrefectClient, flow_run_id: UUID
):
    """
    Make sure that the flow run created for our CLI test is actually deleted.
    """
    with pytest.raises(prefect.exceptions.ObjectNotFound):
        prefect_client.read_flow_run(flow_run_id)


def assert_flow_runs_in_result(result: Any, expected: Any, unexpected: Any = None):
    output = result.stdout.strip()

    # When running in tests the output of the columns in the table are
    # truncated, so this only asserts that the first 20 characters of each
    # flow run's id is in the output.

    for flow_run in expected:
        id_start = str(flow_run.id)[:20]
        assert id_start in output

    if unexpected:
        for flow_run in unexpected:
            id_start = str(flow_run.id)[:20]
            assert id_start not in output, f"{flow_run} should not be in the output"


@pytest.fixture
async def scheduled_flow_run(prefect_client: PrefectClient) -> FlowRun:
    return await prefect_client.create_flow_run(
        name="scheduled_flow_run", flow=hello_flow, state=Scheduled()
    )


@pytest.fixture
async def completed_flow_run(prefect_client: PrefectClient) -> FlowRun:
    return await prefect_client.create_flow_run(
        name="completed_flow_run", flow=hello_flow, state=Completed()
    )


@pytest.fixture
async def running_flow_run(prefect_client: PrefectClient) -> FlowRun:
    return await prefect_client.create_flow_run(
        name="running_flow_run", flow=goodbye_flow, state=Running()
    )


@pytest.fixture
async def late_flow_run(prefect_client: PrefectClient) -> FlowRun:
    return await prefect_client.create_flow_run(
        name="late_flow_run", flow=goodbye_flow, state=Late()
    )


def test_delete_flow_run_fails_correctly():
    missing_flow_run_id = "ccb86ed0-e824-4d8b-b825-880401320e41"
    invoke_and_assert(
        command=["flow-run", "delete", missing_flow_run_id],
        user_input="y",
        expected_output_contains=f"Flow run '{missing_flow_run_id}' not found!",
        expected_code=1,
    )


def test_delete_flow_run_succeeds(
    sync_prefect_client: SyncPrefectClient, flow_run: FlowRun
):
    invoke_and_assert(
        command=["flow-run", "delete", str(flow_run.id)],
        user_input="y",
        expected_output_contains=f"Successfully deleted flow run '{str(flow_run.id)}'.",
        expected_code=0,
    )

    assert_flow_run_is_deleted_sync(sync_prefect_client, flow_run.id)


@pytest.fixture
def mock_webbrowser(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    mock = MagicMock()
    monkeypatch.setattr("prefect.cli.flow_run.webbrowser", mock)
    return mock


def test_inspect_flow_run_with_web_flag(flow_run: FlowRun, mock_webbrowser: MagicMock):
    invoke_and_assert(
        command=["flow-run", "inspect", str(flow_run.id), "--web"],
        expected_code=0,
        expected_output_contains=f"Opened flow run {flow_run.id!r} in browser.",
    )

    mock_webbrowser.open_new_tab.assert_called_once()
    call_args = mock_webbrowser.open_new_tab.call_args[0][0]
    assert f"/runs/flow-run/{flow_run.id}" in call_args


def test_inspect_flow_run_with_web_flag_no_ui_url(
    flow_run: FlowRun, mock_webbrowser: MagicMock
):
    with temporary_settings({PREFECT_UI_URL: ""}):
        invoke_and_assert(
            command=["flow-run", "inspect", str(flow_run.id), "--web"],
            expected_code=1,
            expected_output_contains="Failed to generate URL for flow run. Make sure PREFECT_UI_URL is configured.",
        )

    mock_webbrowser.open_new_tab.assert_not_called()


def test_inspect_flow_run_with_json_output(flow_run: FlowRun):
    """Test flow-run inspect command with JSON output flag."""
    import json

    result = invoke_and_assert(
        command=["flow-run", "inspect", str(flow_run.id), "--output", "json"],
        expected_code=0,
    )

    # Parse JSON output and verify it's valid JSON
    output_data = json.loads(result.stdout.strip())

    # Verify key fields are present
    assert "id" in output_data
    assert "name" in output_data
    assert "state" in output_data
    assert output_data["id"] == str(flow_run.id)


def test_ls_no_args(
    scheduled_flow_run: FlowRun,
    completed_flow_run: FlowRun,
    running_flow_run: FlowRun,
    late_flow_run: FlowRun,
):
    result = invoke_and_assert(
        command=["flow-run", "ls"],
        expected_code=0,
    )

    assert_flow_runs_in_result(
        result,
        [
            scheduled_flow_run,
            completed_flow_run,
            running_flow_run,
            late_flow_run,
        ],
    )


def test_ls_flow_name_filter(
    scheduled_flow_run: FlowRun,
    completed_flow_run: FlowRun,
    running_flow_run: FlowRun,
    late_flow_run: FlowRun,
):
    result = invoke_and_assert(
        command=["flow-run", "ls", "--flow-name", "goodbye"],
        expected_code=0,
    )

    assert_flow_runs_in_result(
        result,
        expected=[running_flow_run, late_flow_run],
        unexpected=[scheduled_flow_run, completed_flow_run],
    )


@pytest.mark.parametrize(
    "state_type_1, state_type_2",
    [
        ("completed", "running"),
        ("COMPLETED", "RUNNING"),
        ("Completed", "Running"),
    ],
)
def test_ls_state_type_filter(
    scheduled_flow_run: FlowRun,
    completed_flow_run: FlowRun,
    running_flow_run: FlowRun,
    late_flow_run: FlowRun,
    state_type_1: str,
    state_type_2: str,
):
    result = invoke_and_assert(
        command=[
            "flow-run",
            "ls",
            "--state-type",
            state_type_1,
            "--state-type",
            state_type_2,
        ],
        expected_code=0,
    )

    assert_flow_runs_in_result(
        result,
        expected=[running_flow_run, completed_flow_run],
        unexpected=[scheduled_flow_run, late_flow_run],
    )


def test_ls_state_type_filter_invalid_raises():
    invoke_and_assert(
        command=["flow-run", "ls", "--state-type", "invalid"],
        expected_code=1,
        expected_output_contains=(
            "Invalid state type. Options are SCHEDULED, PENDING, RUNNING, COMPLETED, FAILED, CANCELLED, CRASHED, PAUSED, CANCELLING."
        ),
    )


@pytest.mark.parametrize(
    "state_name",
    [
        "Late",
        "LATE",
        "late",
    ],
)
def test_ls_state_name_filter(
    scheduled_flow_run: FlowRun,
    completed_flow_run: FlowRun,
    running_flow_run: FlowRun,
    late_flow_run: FlowRun,
    state_name: str,
):
    result = invoke_and_assert(
        command=["flow-run", "ls", "--state", state_name],
        expected_code=0,
    )

    assert_flow_runs_in_result(
        result,
        expected=[late_flow_run],
        unexpected=[running_flow_run, scheduled_flow_run, completed_flow_run],
    )


def test_ls_state_name_filter_unofficial_state_warns(caplog):
    invoke_and_assert(
        command=["flow-run", "ls", "--state", "MyCustomState"],
        expected_code=0,
        expected_output_contains=("No flow runs found.",),
    )

    assert (
        "State name 'MyCustomState' is not one of the official Prefect state names"
        in caplog.text
    )


def test_ls_limit(
    scheduled_flow_run: FlowRun,
    completed_flow_run: FlowRun,
    running_flow_run: FlowRun,
    late_flow_run: FlowRun,
):
    result = invoke_and_assert(
        command=["flow-run", "ls", "--limit", "2"],
        expected_code=0,
    )

    output = result.stdout.strip()

    found_count = 0
    for flow_run in [
        scheduled_flow_run,
        completed_flow_run,
        running_flow_run,
        late_flow_run,
    ]:
        id_start = str(flow_run.id)[:20]
        if id_start in output:
            found_count += 1

    assert found_count == 2


class TestCancelFlowRun:
    @pytest.mark.parametrize(
        "state",
        [
            Running,
            Pending,
            Retrying,
        ],
    )
    async def test_non_terminal_states_set_to_cancelling(
        self, prefect_client: PrefectClient, state: State
    ):
        """Should set the state of the flow to Cancelling. Does not include Scheduled
        states, because they should be set to Cancelled instead.
        """
        before = await prefect_client.create_flow_run(
            name="scheduled_flow_run", flow=hello_flow, state=state()
        )
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "flow-run",
                "cancel",
                str(before.id),
            ],
            expected_code=0,
            expected_output_contains=(
                f"Flow run '{before.id}' was successfully scheduled for cancellation."
            ),
        )
        after = await prefect_client.read_flow_run(before.id)
        assert before.state.name != after.state.name
        assert before.state.type != after.state.type
        assert after.state.type == StateType.CANCELLING

    @pytest.mark.parametrize(
        "state",
        [
            Scheduled,
            AwaitingRetry,
            Late,
        ],
    )
    async def test_scheduled_states_set_to_cancelled(
        self, prefect_client: PrefectClient, state: State
    ):
        """Should set the state of the flow run to Cancelled."""
        before = await prefect_client.create_flow_run(
            name="scheduled_flow_run", flow=hello_flow, state=state()
        )
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "flow-run",
                "cancel",
                str(before.id),
            ],
            expected_code=0,
            expected_output_contains=(
                f"Flow run '{before.id}' was successfully scheduled for cancellation."
            ),
        )
        after = await prefect_client.read_flow_run(before.id)
        assert before.state.name != after.state.name
        assert before.state.type != after.state.type
        assert after.state.type == StateType.CANCELLED

    @pytest.mark.parametrize("state", [Completed, Failed, Crashed, Cancelled])
    async def test_cancelling_terminal_states_exits_with_error(
        self, prefect_client: PrefectClient, state: State
    ):
        before = await prefect_client.create_flow_run(
            name="scheduled_flow_run", flow=hello_flow, state=state()
        )
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "flow-run",
                "cancel",
                str(before.id),
            ],
            expected_code=1,
            expected_output_contains=(
                f"Flow run '{before.id}' was unable to be cancelled."
            ),
        )
        after = await prefect_client.read_flow_run(before.id)

        assert after.state.name == before.state.name
        assert after.state.type == before.state.type

    def test_wrong_id_exits_with_error(self):
        bad_id = str(uuid4())
        invoke_and_assert(
            ["flow-run", "cancel", bad_id],
            expected_code=1,
            expected_output_contains=f"Flow run '{bad_id}' not found!\n",
        )


@pytest.fixture()
def flow_run_factory(
    prefect_client: PrefectClient,
) -> Callable[[int], Awaitable[FlowRun]]:
    async def create_flow_run(num_logs: int) -> FlowRun:
        flow_run = await prefect_client.create_flow_run(
            name="scheduled_flow_run", flow=hello_flow
        )

        logs = [
            LogCreate(
                name="prefect.flow_runs",
                level=20,
                message=f"Log {i} from flow_run {flow_run.id}.",
                timestamp=now(),
                flow_run_id=flow_run.id,
            )
            for i in range(num_logs)
        ]
        await prefect_client.create_logs(logs)

        return flow_run

    return create_flow_run


class TestFlowRunLogs:
    LOGS_DEFAULT_PAGE_SIZE = 200

    async def test_when_num_logs_smaller_than_page_size_then_no_pagination(
        self, flow_run_factory
    ):
        # Given
        flow_run = await flow_run_factory(num_logs=self.LOGS_DEFAULT_PAGE_SIZE - 1)

        # When/Then
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "flow-run",
                "logs",
                str(flow_run.id),
            ],
            expected_code=0,
            expected_output_contains=[
                f"Flow run '{flow_run.name}' - Log {i} from flow_run {flow_run.id}."
                for i in range(self.LOGS_DEFAULT_PAGE_SIZE - 1)
            ],
        )

    async def test_when_num_logs_greater_than_page_size_then_pagination(
        self, flow_run_factory
    ):
        # Given
        flow_run = await flow_run_factory(num_logs=self.LOGS_DEFAULT_PAGE_SIZE + 1)

        # When/Then
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "flow-run",
                "logs",
                str(flow_run.id),
            ],
            expected_code=0,
            expected_output_contains=[
                f"Flow run '{flow_run.name}' - Log {i} from flow_run {flow_run.id}."
                for i in range(self.LOGS_DEFAULT_PAGE_SIZE + 1)
            ],
        )

    async def test_when_flow_run_not_found_then_exit_with_error(self, flow_run_factory):
        # Given
        bad_id = str(uuid4())

        # When/Then
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "flow-run",
                "logs",
                bad_id,
            ],
            expected_code=1,
            expected_output_contains=f"Flow run '{bad_id}' not found!\n",
        )

    async def test_when_num_logs_smaller_than_page_size_with_head_then_no_pagination(
        self, flow_run_factory
    ):
        # Given
        flow_run = await flow_run_factory(num_logs=self.LOGS_DEFAULT_PAGE_SIZE + 1)

        # When/Then
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "flow-run",
                "logs",
                str(flow_run.id),
                "--head",
                "--num-logs",
                "10",
            ],
            expected_code=0,
            expected_output_contains=[
                f"Flow run '{flow_run.name}' - Log {i} from flow_run {flow_run.id}."
                for i in range(10)
            ],
            expected_line_count=10,
        )

    async def test_when_num_logs_greater_than_page_size_with_head_then_pagination(
        self, flow_run_factory
    ):
        # Given
        flow_run = await flow_run_factory(num_logs=self.LOGS_DEFAULT_PAGE_SIZE + 1)

        # When/Then
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "flow-run",
                "logs",
                str(flow_run.id),
                "--head",
                "--num-logs",
                self.LOGS_DEFAULT_PAGE_SIZE + 1,
            ],
            expected_code=0,
            expected_output_contains=[
                f"Flow run '{flow_run.name}' - Log {i} from flow_run {flow_run.id}."
                for i in range(self.LOGS_DEFAULT_PAGE_SIZE + 1)
            ],
            expected_line_count=self.LOGS_DEFAULT_PAGE_SIZE + 1,
        )

    async def test_when_num_logs_greater_than_page_size_with_head_outputs_correct_num_logs(
        self, flow_run_factory
    ):
        flow_run = await flow_run_factory(num_logs=self.LOGS_DEFAULT_PAGE_SIZE + 50)

        # When/Then
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "flow-run",
                "logs",
                str(flow_run.id),
                "--head",
                "--num-logs",
                self.LOGS_DEFAULT_PAGE_SIZE + 50,
            ],
            expected_code=0,
            expected_output_contains=[
                f"Flow run '{flow_run.name}' - Log {i} from flow_run {flow_run.id}."
                for i in range(self.LOGS_DEFAULT_PAGE_SIZE + 50)
            ],
            expected_line_count=self.LOGS_DEFAULT_PAGE_SIZE + 50,
        )

    async def test_default_head_returns_default_num_logs(self, flow_run_factory):
        # Given
        flow_run = await flow_run_factory(num_logs=self.LOGS_DEFAULT_PAGE_SIZE + 1)

        # When/Then
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "flow-run",
                "logs",
                str(flow_run.id),
                "--head",
            ],
            expected_code=0,
            expected_output_contains=[
                f"Flow run '{flow_run.name}' - Log {i} from flow_run {flow_run.id}."
                for i in range(LOGS_WITH_LIMIT_FLAG_DEFAULT_NUM_LOGS)
            ],
            expected_line_count=LOGS_WITH_LIMIT_FLAG_DEFAULT_NUM_LOGS,
        )

    async def test_h_and_n_shortcuts_for_head_and_num_logs(self, flow_run_factory):
        # Given
        flow_run = await flow_run_factory(num_logs=self.LOGS_DEFAULT_PAGE_SIZE + 1)

        # When/Then
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "flow-run",
                "logs",
                str(flow_run.id),
                "-h",
                "-n",
                "10",
            ],
            expected_code=0,
            expected_output_contains=[
                f"Flow run '{flow_run.name}' - Log {i} from flow_run {flow_run.id}."
                for i in range(10)
            ],
            expected_line_count=10,
        )

    async def test_num_logs_passed_standalone_returns_num_logs(self, flow_run_factory):
        # Given
        flow_run = await flow_run_factory(num_logs=self.LOGS_DEFAULT_PAGE_SIZE + 1)

        # When/Then
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "flow-run",
                "logs",
                str(flow_run.id),
                "--num-logs",
                "10",
            ],
            expected_code=0,
            expected_output_contains=[
                f"Flow run '{flow_run.name}' - Log {i} from flow_run {flow_run.id}."
                for i in range(10)
            ],
            expected_line_count=10,
        )

    @pytest.mark.skip(reason="we need to disable colors for this test to pass")
    async def test_when_num_logs_is_smaller_than_one_then_exit_with_error(
        self, flow_run_factory
    ):
        # Given
        flow_run = await flow_run_factory(num_logs=self.LOGS_DEFAULT_PAGE_SIZE + 1)

        # When/Then
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "flow-run",
                "logs",
                str(flow_run.id),
                "--num-logs",
                "0",
            ],
            expected_code=2,
            expected_output_contains=(
                "Invalid value for '--num-logs' / '-n': 0 is not in the range x>=1."
            ),
        )

    async def test_when_num_logs_passed_with_reverse_param_and_num_logs(
        self, flow_run_factory
    ):
        # Given
        flow_run = await flow_run_factory(num_logs=self.LOGS_DEFAULT_PAGE_SIZE + 1)

        # When/Then
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "flow-run",
                "logs",
                str(flow_run.id),
                "--num-logs",
                "10",
                "--reverse",
            ],
            expected_code=0,
            expected_output_contains=[
                f"Flow run '{flow_run.name}' - Log {i} from flow_run {flow_run.id}."
                for i in range(
                    self.LOGS_DEFAULT_PAGE_SIZE, self.LOGS_DEFAULT_PAGE_SIZE - 10, -1
                )
            ],
            expected_line_count=10,
        )

    async def test_passing_head_and_tail_raises(self, flow_run_factory):
        # Given
        flow_run = await flow_run_factory(num_logs=self.LOGS_DEFAULT_PAGE_SIZE + 1)

        # When/Then
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "flow-run",
                "logs",
                str(flow_run.id),
                "--tail",
                "--num-logs",
                "10",
                "--head",
            ],
            expected_code=1,
            expected_output_contains=(
                "Please provide either a `head` or `tail` option but not both."
            ),
        )

    async def test_default_tail_returns_default_num_logs(self, flow_run_factory):
        # Given
        flow_run = await flow_run_factory(num_logs=self.LOGS_DEFAULT_PAGE_SIZE + 1)

        # When/Then
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=["flow-run", "logs", str(flow_run.id), "-t"],
            expected_code=0,
            expected_output_contains=[
                f"Flow run '{flow_run.name}' - Log {i} from flow_run {flow_run.id}."
                for i in range(
                    self.LOGS_DEFAULT_PAGE_SIZE - 9, self.LOGS_DEFAULT_PAGE_SIZE
                )
            ],
            expected_line_count=20,
        )

    async def test_reverse_tail_with_num_logs(self, flow_run_factory):
        # Given
        flow_run = await flow_run_factory(num_logs=self.LOGS_DEFAULT_PAGE_SIZE + 1)

        # When/Then
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "flow-run",
                "logs",
                str(flow_run.id),
                "--tail",
                "--num-logs",
                "10",
                "--reverse",
            ],
            expected_code=0,
            expected_output_contains=[
                f"Flow run '{flow_run.name}' - Log {i} from flow_run {flow_run.id}."
                for i in range(
                    self.LOGS_DEFAULT_PAGE_SIZE, self.LOGS_DEFAULT_PAGE_SIZE - 10, -1
                )
            ],
            expected_line_count=10,
        )

    async def test_reverse_tail_returns_default_num_logs(self, flow_run_factory):
        # Given
        flow_run = await flow_run_factory(num_logs=self.LOGS_DEFAULT_PAGE_SIZE + 1)

        # When/Then
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "flow-run",
                "logs",
                str(flow_run.id),
                "--tail",
                "--reverse",
            ],
            expected_code=0,
            expected_output_contains=[
                f"Flow run '{flow_run.name}' - Log {i} from flow_run {flow_run.id}."
                for i in range(
                    self.LOGS_DEFAULT_PAGE_SIZE, self.LOGS_DEFAULT_PAGE_SIZE - 20, -1
                )
            ],
            expected_line_count=20,
        )

    async def test_when_num_logs_greater_than_page_size_with_tail_outputs_correct_num_logs(
        self, flow_run_factory
    ):
        # Given
        num_logs = 300
        flow_run = await flow_run_factory(num_logs=num_logs)

        # When/Then
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "flow-run",
                "logs",
                str(flow_run.id),
                "--tail",
                "--num-logs",
                "251",
            ],
            expected_code=0,
            expected_output_contains=[
                f"Flow run '{flow_run.name}' - Log {i} from flow_run {flow_run.id}."
                for i in range(num_logs - 250, num_logs)
            ],
            expected_line_count=251,
        )


class TestFlowRunExecute:
    async def test_execute_flow_run_via_argument(self, prefect_client: PrefectClient):
        deployment_id = await RunnerDeployment.from_entrypoint(
            entrypoint=f"{__development_base_path__}/tests/cli/test_flow_run.py:hello_flow",
            name="test",
        ).apply()

        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=["flow-run", "execute", str(flow_run.id)],
            expected_code=0,
        )

        flow_run = await prefect_client.read_flow_run(flow_run.id)
        assert flow_run.state.is_completed()

    async def test_execute_flow_run_via_environment_variable(
        self, prefect_client: PrefectClient, monkeypatch
    ):
        deployment = RunnerDeployment.from_entrypoint(
            entrypoint=f"{__development_base_path__}/tests/cli/test_flow_run.py:hello_flow",
            name="test",
        )
        deployment_id = await deployment.apply()

        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )

        monkeypatch.setenv("PREFECT__FLOW_RUN_ID", str(flow_run.id))

        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=["flow-run", "execute"],
            expected_code=0,
        )

        flow_run = await prefect_client.read_flow_run(flow_run.id)
        assert flow_run.state.is_completed()


class TestSignalHandling:
    @pytest.mark.parametrize("sigterm_handling", ["reschedule", None])
    async def test_flow_run_execute_sigterm_handling(
        self,
        monkeypatch: pytest.MonkeyPatch,
        prefect_client: PrefectClient,
        sigterm_handling: str | None,
    ):
        if sigterm_handling is not None:
            monkeypatch.setenv(
                "PREFECT_FLOW_RUN_EXECUTE_SIGTERM_BEHAVIOR", sigterm_handling
            )

        # Create a flow run that will take a while to run
        deployment_id = await (await tired_flow.to_deployment(__file__)).apply()

        flow_run = await prefect_client.create_flow_run_from_deployment(
            deployment_id=deployment_id
        )

        # Run the flow run in a new process with a Runner
        popen = subprocess.Popen(
            [
                "prefect",
                "flow-run",
                "execute",
                str(flow_run.id),
            ],
            env=get_current_settings().to_environment_variables(exclude_unset=True)
            | os.environ,
        )

        assert popen.pid is not None

        # Wait for the flow run to start
        while True:
            await anyio.sleep(0.5)
            flow_run = await prefect_client.read_flow_run(flow_run_id=flow_run.id)
            assert flow_run.state
            if flow_run.state.is_running():
                break

        # Send the SIGTERM signal
        popen.terminate()

        # Wait for the process to exit
        return_code = popen.wait(timeout=10)

        flow_run = await prefect_client.read_flow_run(flow_run_id=flow_run.id)
        assert flow_run.state

        if sigterm_handling == "reschedule":
            assert flow_run.state.is_scheduled(), (
                "The flow run should have been rescheduled"
            )
            assert return_code == 0, "The process should have exited with a 0 exit code"
        else:
            assert flow_run.state.is_running(), (
                "The flow run should be stuck in running"
            )
            assert return_code == -signal.SIGTERM.value, (
                "The process should have exited with a SIGTERM exit code"
            )
