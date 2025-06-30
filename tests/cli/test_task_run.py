from __future__ import annotations

from typing import Awaitable, Callable
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from click.testing import Result

from prefect import flow, task
from prefect.cli.flow_run import LOGS_DEFAULT_PAGE_SIZE
from prefect.cli.task_run import LOGS_WITH_LIMIT_FLAG_DEFAULT_NUM_LOGS
from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.actions import LogCreate
from prefect.client.schemas.objects import TaskRun
from prefect.exceptions import ObjectNotFound
from prefect.settings import PREFECT_UI_URL, temporary_settings
from prefect.states import Completed, Late, Running, Scheduled
from prefect.testing.cli import invoke_and_assert
from prefect.types._datetime import now
from prefect.utilities.asyncutils import run_sync_in_worker_thread


@task(name="hello")
def hello_task():
    return "Hello!"


@task(name="goodbye")
def goodbye_task():
    return "Goodbye"


@flow
def test_flow():
    hello_task()
    goodbye_task()


def assert_task_runs_in_result(
    result: Result, expected: list[TaskRun], unexpected: list[TaskRun] | None = None
):
    output = result.stdout.strip()

    # When running in tests the output of the columns in the table are
    # truncated, so this only asserts that the first 20 characters of each
    # task run's id is in the output.

    for task_run in expected:
        id_start = str(task_run.id)[:20]
        assert id_start in output

    if unexpected:
        for task_run in unexpected:
            id_start = str(task_run.id)[:20]
            assert id_start not in output, f"{task_run} should not be in the output"


async def assert_task_run_is_deleted(prefect_client: PrefectClient, task_run_id: UUID):
    """
    Make sure that the task run created for our CLI test is actually deleted.
    """
    with pytest.raises(ObjectNotFound):
        await prefect_client.read_task_run(task_run_id)


@pytest.fixture
async def scheduled_task_run(prefect_client: PrefectClient) -> TaskRun:
    flow_run = await prefect_client.create_flow_run(flow=test_flow)
    task_run = await prefect_client.create_task_run(
        task=hello_task,
        name="scheduled_task_run",
        flow_run_id=flow_run.id,
        state=Scheduled(),
        dynamic_key="0",
    )
    return task_run


@pytest.fixture
async def completed_task_run(prefect_client: PrefectClient) -> TaskRun:
    flow_run = await prefect_client.create_flow_run(flow=test_flow)
    task_run = await prefect_client.create_task_run(
        task=hello_task,
        name="completed_task_run",
        flow_run_id=flow_run.id,
        state=Completed(),
        dynamic_key="0",
    )
    return task_run


@pytest.fixture
async def running_task_run(prefect_client: PrefectClient) -> TaskRun:
    flow_run = await prefect_client.create_flow_run(flow=test_flow)
    task_run = await prefect_client.create_task_run(
        task=goodbye_task,
        name="running_task_run",
        flow_run_id=flow_run.id,
        state=Running(),
        dynamic_key="0",
    )
    return task_run


@pytest.fixture
async def late_task_run(prefect_client: PrefectClient) -> TaskRun:
    flow_run = await prefect_client.create_flow_run(flow=test_flow)
    task_run = await prefect_client.create_task_run(
        task=goodbye_task,
        name="late_task_run",
        flow_run_id=flow_run.id,
        state=Late(),
        dynamic_key="0",
    )
    return task_run


def test_inspect_task_run_not_found():
    missing_task_run_id = uuid4()
    invoke_and_assert(
        command=["task-run", "inspect", str(missing_task_run_id)],
        expected_output_contains=f"Task run '{missing_task_run_id}' not found!",
        expected_code=1,
    )


@pytest.fixture
def mock_webbrowser(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    mock = MagicMock()
    monkeypatch.setattr("prefect.cli.task_run.webbrowser", mock)
    return mock


def test_inspect_task_run_with_web_flag(
    completed_task_run: TaskRun, mock_webbrowser: MagicMock
):
    invoke_and_assert(
        command=["task-run", "inspect", str(completed_task_run.id), "--web"],
        expected_code=0,
        expected_output_contains=f"Opened task run {completed_task_run.id!r} in browser.",
    )

    mock_webbrowser.open_new_tab.assert_called_once()
    call_args = mock_webbrowser.open_new_tab.call_args[0][0]
    assert f"/runs/task-run/{completed_task_run.id}" in call_args


def test_inspect_task_run_with_web_flag_no_ui_url(
    completed_task_run: TaskRun, mock_webbrowser: MagicMock
):
    with temporary_settings({PREFECT_UI_URL: ""}):
        invoke_and_assert(
            command=["task-run", "inspect", str(completed_task_run.id), "--web"],
            expected_code=1,
            expected_output_contains="Failed to generate URL for task run. Make sure PREFECT_UI_URL is configured.",
        )

    mock_webbrowser.open_new_tab.assert_not_called()


def test_inspect_task_run_with_json_output(completed_task_run: TaskRun):
    """Test task-run inspect command with JSON output flag."""
    import json

    result = invoke_and_assert(
        command=["task-run", "inspect", str(completed_task_run.id), "--output", "json"],
        expected_code=0,
    )

    # Parse JSON output and verify it's valid JSON
    output_data = json.loads(result.stdout.strip())

    # Verify key fields are present
    assert "id" in output_data
    assert "name" in output_data
    assert "state" in output_data
    assert output_data["id"] == str(completed_task_run.id)


def test_ls_no_args(
    scheduled_task_run: TaskRun,
    completed_task_run: TaskRun,
    running_task_run: TaskRun,
    late_task_run: TaskRun,
):
    result = invoke_and_assert(
        command=["task-run", "ls"],
        expected_code=0,
    )

    assert_task_runs_in_result(
        result,
        [
            scheduled_task_run,
            completed_task_run,
            running_task_run,
            late_task_run,
        ],
    )


def test_ls_task_name_filter(
    scheduled_task_run: TaskRun,
    completed_task_run: TaskRun,
    running_task_run: TaskRun,
    late_task_run: TaskRun,
):
    result = invoke_and_assert(
        command=[
            "task-run",
            "ls",
            "--task-run-name",
            late_task_run.name,
        ],
        expected_code=0,
    )

    assert_task_runs_in_result(
        result,
        expected=[late_task_run],
        unexpected=[scheduled_task_run, completed_task_run, running_task_run],
    )


def test_ls_state_type_filter(
    scheduled_task_run: TaskRun,
    completed_task_run: TaskRun,
    running_task_run: TaskRun,
    late_task_run: TaskRun,
):
    result = invoke_and_assert(
        command=[
            "task-run",
            "ls",
            "--state-type",
            "COMPLETED",
            "--state-type",
            "RUNNING",
        ],
        expected_code=0,
    )

    assert_task_runs_in_result(
        result,
        expected=[running_task_run, completed_task_run],
        unexpected=[scheduled_task_run, late_task_run],
    )


def test_ls_state_type_filter_invalid_raises():
    invoke_and_assert(
        command=["task-run", "ls", "--state-type", "invalid"],
        expected_code=2,
        expected_output_contains="Invalid value for",
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
    scheduled_task_run: TaskRun,
    completed_task_run: TaskRun,
    running_task_run: TaskRun,
    late_task_run: TaskRun,
    state_name: str,
):
    result = invoke_and_assert(
        command=["task-run", "ls", "--state", state_name],
        expected_code=0,
    )

    assert_task_runs_in_result(
        result,
        expected=[late_task_run],
        unexpected=[running_task_run, scheduled_task_run, completed_task_run],
    )


def test_ls_limit(
    scheduled_task_run: TaskRun,
    completed_task_run: TaskRun,
    running_task_run: TaskRun,
    late_task_run: TaskRun,
):
    result = invoke_and_assert(
        command=["task-run", "ls", "--limit", "2"],
        expected_code=0,
    )

    output = result.stdout.strip()

    found_count = 0
    for task_run in [
        scheduled_task_run,
        completed_task_run,
        running_task_run,
        late_task_run,
    ]:
        id_start = str(task_run.id)[:20]
        if id_start in output:
            found_count += 1

    assert found_count == 2


@pytest.fixture()
def task_run_factory(prefect_client: PrefectClient):
    async def create_task_run(num_logs: int) -> TaskRun:
        flow_run = await prefect_client.create_flow_run(flow=test_flow)
        task_run = await prefect_client.create_task_run(
            task=hello_task,
            name="test_task_run",
            flow_run_id=flow_run.id,
            dynamic_key="0",
        )

        logs = [
            LogCreate(
                name="prefect.task_runs",
                level=20,
                message=f"Log {i} from task_run {task_run.id}.",
                timestamp=now(),
                task_run_id=task_run.id,
            )
            for i in range(num_logs)
        ]
        await prefect_client.create_logs(logs)

        return task_run

    return create_task_run


class TestTaskRunLogs:
    async def test_when_num_logs_greater_than_page_size_then_pagination(
        self, task_run_factory: Callable[[int], Awaitable[TaskRun]]
    ):
        # Given
        task_run = await task_run_factory(LOGS_DEFAULT_PAGE_SIZE)

        # When/Then
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "task-run",
                "logs",
                str(task_run.id),
            ],
            expected_code=0,
            expected_output_contains=[
                f"Task run '{task_run.name}' - Log {i} from task_run {task_run.id}."
                for i in range(LOGS_WITH_LIMIT_FLAG_DEFAULT_NUM_LOGS)
            ],
        )

    async def test_when_task_run_not_found_then_exit_with_error(self):
        # Given
        bad_id = str(uuid4())

        # When/Then
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "task-run",
                "logs",
                bad_id,
            ],
            expected_code=1,
            expected_output_contains=f"task run '{bad_id}' not found!\n",
        )

    async def test_when_num_logs_smaller_than_page_size_with_head_then_no_pagination(
        self, task_run_factory: Callable[[int], Awaitable[TaskRun]]
    ):
        # Given
        task_run = await task_run_factory(LOGS_DEFAULT_PAGE_SIZE + 1)

        # When/Then
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "task-run",
                "logs",
                str(task_run.id),
                "--head",
                "--num-logs",
                "10",
            ],
            expected_code=0,
            expected_output_contains=[
                f"Task run '{task_run.name}' - Log {i} from task_run {task_run.id}."
                for i in range(10)
            ],
            expected_line_count=10,
        )

    async def test_when_num_logs_greater_than_page_size_with_head_then_pagination(
        self, task_run_factory: Callable[[int], Awaitable[TaskRun]]
    ):
        # Given
        task_run = await task_run_factory(LOGS_DEFAULT_PAGE_SIZE + 1)

        # When/Then
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "task-run",
                "logs",
                str(task_run.id),
                "--head",
                "--num-logs",
                str(LOGS_DEFAULT_PAGE_SIZE + 1),
            ],
            expected_code=0,
            expected_output_contains=[
                f"Task run '{task_run.name}' - Log {i} from task_run {task_run.id}."
                for i in range(LOGS_DEFAULT_PAGE_SIZE + 1)
            ],
            expected_line_count=LOGS_DEFAULT_PAGE_SIZE + 1,
        )

    async def test_default_head_returns_default_num_logs(
        self, task_run_factory: Callable[[int], Awaitable[TaskRun]]
    ):
        # Given
        task_run = await task_run_factory(LOGS_DEFAULT_PAGE_SIZE + 1)

        # When/Then
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "task-run",
                "logs",
                str(task_run.id),
                "--head",
            ],
            expected_code=0,
            expected_output_contains=[
                f"Task run '{task_run.name}' - Log {i} from task_run {task_run.id}."
                for i in range(LOGS_WITH_LIMIT_FLAG_DEFAULT_NUM_LOGS)
            ],
            expected_line_count=LOGS_WITH_LIMIT_FLAG_DEFAULT_NUM_LOGS,
        )

    async def test_h_and_n_shortcuts_for_head_and_num_logs(
        self, task_run_factory: Callable[[int], Awaitable[TaskRun]]
    ):
        # Given
        task_run = await task_run_factory(LOGS_DEFAULT_PAGE_SIZE + 1)

        # When/Then
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "task-run",
                "logs",
                str(task_run.id),
                "-h",
                "-n",
                "10",
            ],
            expected_code=0,
            expected_output_contains=[
                f"Task run '{task_run.name}' - Log {i} from task_run {task_run.id}."
                for i in range(10)
            ],
            expected_line_count=10,
        )

    async def test_num_logs_passed_standalone_returns_num_logs(
        self, task_run_factory: Callable[[int], Awaitable[TaskRun]]
    ):
        # Given
        task_run = await task_run_factory(LOGS_DEFAULT_PAGE_SIZE + 1)

        # When/Then
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "task-run",
                "logs",
                str(task_run.id),
                "--num-logs",
                "10",
            ],
            expected_code=0,
            expected_output_contains=[
                f"Task run '{task_run.name}' - Log {i} from task_run {task_run.id}."
                for i in range(10)
            ],
            expected_line_count=10,
        )

    @pytest.mark.skip(reason="we need to disable colors for this test to pass")
    async def test_when_num_logs_is_smaller_than_one_then_exit_with_error(
        self, task_run_factory: Callable[[int], Awaitable[TaskRun]]
    ):
        # Given
        task_run = await task_run_factory(LOGS_DEFAULT_PAGE_SIZE + 1)

        # When/Then
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "task-run",
                "logs",
                str(task_run.id),
                "--num-logs",
                "0",
            ],
            expected_code=2,
            expected_output_contains="Invalid value for '--num-logs' / '-n': 0 is not in the range x>=1.",
        )

    async def test_when_num_logs_passed_with_reverse_param_and_num_logs(
        self, task_run_factory: Callable[[int], Awaitable[TaskRun]]
    ):
        # Given
        task_run = await task_run_factory(LOGS_DEFAULT_PAGE_SIZE + 1)

        # When/Then
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "task-run",
                "logs",
                str(task_run.id),
                "--num-logs",
                "10",
                "--reverse",
            ],
            expected_code=0,
            expected_output_contains=[
                f"Task run '{task_run.name}' - Log {i} from task_run {task_run.id}."
                for i in range(LOGS_DEFAULT_PAGE_SIZE, LOGS_DEFAULT_PAGE_SIZE - 10, -1)
            ],
            expected_line_count=10,
        )

    async def test_passing_head_and_tail_raises(
        self, task_run_factory: Callable[[int], Awaitable[TaskRun]]
    ):
        # Given
        task_run = await task_run_factory(LOGS_DEFAULT_PAGE_SIZE + 1)

        # When/Then
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "task-run",
                "logs",
                str(task_run.id),
                "--tail",
                "--num-logs",
                "10",
                "--head",
            ],
            expected_code=1,
            expected_output_contains="Please provide either a `head` or `tail` option but not both.",
        )

    async def test_default_tail_returns_default_num_logs(
        self, task_run_factory: Callable[[int], Awaitable[TaskRun]]
    ):
        # Given
        task_run = await task_run_factory(LOGS_DEFAULT_PAGE_SIZE + 1)

        # When/Then
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=["task-run", "logs", str(task_run.id), "-t"],
            expected_code=0,
            expected_output_contains=[
                f"Task run '{task_run.name}' - Log {i} from task_run {task_run.id}."
                for i in range(LOGS_DEFAULT_PAGE_SIZE - 9, LOGS_DEFAULT_PAGE_SIZE)
            ],
            expected_line_count=20,
        )

    async def test_reverse_tail_with_num_logs(
        self, task_run_factory: Callable[[int], Awaitable[TaskRun]]
    ):
        # Given
        task_run = await task_run_factory(LOGS_DEFAULT_PAGE_SIZE + 1)

        # When/Then
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "task-run",
                "logs",
                str(task_run.id),
                "--tail",
                "--num-logs",
                "10",
                "--reverse",
            ],
            expected_code=0,
            expected_output_contains=[
                f"Task run '{task_run.name}' - Log {i} from task_run {task_run.id}."
                for i in range(LOGS_DEFAULT_PAGE_SIZE, LOGS_DEFAULT_PAGE_SIZE - 10, -1)
            ],
            expected_line_count=10,
        )

    async def test_reverse_tail_returns_default_num_logs(
        self, task_run_factory: Callable[[int], Awaitable[TaskRun]]
    ):
        # Given
        task_run = await task_run_factory(LOGS_DEFAULT_PAGE_SIZE + 1)

        # When/Then
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "task-run",
                "logs",
                str(task_run.id),
                "--tail",
                "--reverse",
            ],
            expected_code=0,
            expected_output_contains=[
                f"Task run '{task_run.name}' - Log {i} from task_run {task_run.id}."
                for i in range(LOGS_DEFAULT_PAGE_SIZE, LOGS_DEFAULT_PAGE_SIZE - 20, -1)
            ],
            expected_line_count=20,
        )

    async def test_when_num_logs_greater_than_page_size_with_tail_outputs_correct_num_logs(
        self, task_run_factory: Callable[[int], Awaitable[TaskRun]]
    ):
        # Given
        num_logs = 300
        task_run = await task_run_factory(num_logs)

        # When/Then
        await run_sync_in_worker_thread(
            invoke_and_assert,
            command=[
                "task-run",
                "logs",
                str(task_run.id),
                "--tail",
                "--num-logs",
                "251",
            ],
            expected_code=0,
            expected_output_contains=[
                f"Task run '{task_run.name}' - Log {i} from task_run {task_run.id}."
                for i in range(num_logs - 250, num_logs)
            ],
            expected_line_count=251,
        )
