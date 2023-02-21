from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

import prefect.exceptions
from prefect import flow
from prefect.cli.flow_run import LOGS_WITH_LIMIT_FLAG_DEFAULT_NUM_LOGS
from prefect.server.schemas.actions import LogCreate
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
    StateType,
)
from prefect.testing.cli import invoke_and_assert
from prefect.utilities.asyncutils import run_sync_in_worker_thread, sync_compatible


@flow(name="hello")
def hello_flow():
    return "Hello!"


@flow(name="goodbye")
def goodbye_flow():
    return "Goodbye"


@sync_compatible
async def assert_flow_run_is_deleted(orion_client, flow_run_id: UUID):
    """
    Make sure that the flow run created for our CLI test is actually deleted.
    """
    with pytest.raises(prefect.exceptions.ObjectNotFound):
        await orion_client.read_flow_run(flow_run_id)


def assert_flow_runs_in_result(result, expected, unexpected=None):
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
async def scheduled_flow_run(orion_client):
    return await orion_client.create_flow_run(
        name="scheduled_flow_run", flow=hello_flow, state=Scheduled()
    )


@pytest.fixture
async def completed_flow_run(orion_client):
    return await orion_client.create_flow_run(
        name="completed_flow_run", flow=hello_flow, state=Completed()
    )


@pytest.fixture
async def running_flow_run(orion_client):
    return await orion_client.create_flow_run(
        name="running_flow_run", flow=goodbye_flow, state=Running()
    )


@pytest.fixture
async def late_flow_run(orion_client):
    return await orion_client.create_flow_run(
        name="late_flow_run", flow=goodbye_flow, state=Late()
    )


def test_delete_flow_run_fails_correctly():
    missing_flow_run_id = "ccb86ed0-e824-4d8b-b825-880401320e41"
    invoke_and_assert(
        command=["flow-run", "delete", missing_flow_run_id],
        expected_output_contains=f"Flow run '{missing_flow_run_id}' not found!",
        expected_code=1,
    )


def test_delete_flow_run_succeeds(orion_client, flow_run):
    invoke_and_assert(
        command=["flow-run", "delete", str(flow_run.id)],
        expected_output_contains=f"Successfully deleted flow run '{str(flow_run.id)}'.",
        expected_code=0,
    )

    assert_flow_run_is_deleted(orion_client, flow_run.id)


def test_ls_no_args(
    scheduled_flow_run,
    completed_flow_run,
    running_flow_run,
    late_flow_run,
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
    scheduled_flow_run,
    completed_flow_run,
    running_flow_run,
    late_flow_run,
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


def test_ls_state_type_filter(
    scheduled_flow_run,
    completed_flow_run,
    running_flow_run,
    late_flow_run,
):
    result = invoke_and_assert(
        command=[
            "flow-run",
            "ls",
            "--state-type",
            "COMPLETED",
            "--state-type",
            "RUNNING",
        ],
        expected_code=0,
    )

    assert_flow_runs_in_result(
        result,
        expected=[running_flow_run, completed_flow_run],
        unexpected=[scheduled_flow_run, late_flow_run],
    )


def test_ls_state_name_filter(
    scheduled_flow_run,
    completed_flow_run,
    running_flow_run,
    late_flow_run,
):
    result = invoke_and_assert(
        command=["flow-run", "ls", "--state", "Late"],
        expected_code=0,
    )

    assert_flow_runs_in_result(
        result,
        expected=[late_flow_run],
        unexpected=[running_flow_run, scheduled_flow_run, completed_flow_run],
    )


def test_ls_limit(
    scheduled_flow_run,
    completed_flow_run,
    running_flow_run,
    late_flow_run,
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
            Scheduled,
            Running,
            Late,
            Pending,
            AwaitingRetry,
            Retrying,
        ],
    )
    async def test_non_terminal_states_set_to_cancelled(self, orion_client, state):
        before = await orion_client.create_flow_run(
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
                f"Flow run '{before.id}' was succcessfully scheduled for cancellation."
            ),
        )
        after = await orion_client.read_flow_run(before.id)
        assert before.state.name != after.state.name
        assert before.state.type != after.state.type
        assert after.state.type == StateType.CANCELLING

    @pytest.mark.parametrize("state", [Completed, Failed, Crashed, Cancelled])
    async def test_cancelling_terminal_states_exits_with_error(
        self, orion_client, state
    ):
        before = await orion_client.create_flow_run(
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
        after = await orion_client.read_flow_run(before.id)

        assert after.state.name == before.state.name
        assert after.state.type == before.state.type

    def test_wrong_id_exits_with_error(self):
        bad_id = str(uuid4())
        res = invoke_and_assert(
            ["flow-run", "cancel", bad_id],
            expected_code=1,
            expected_output_contains=f"Flow run '{bad_id}' not found!\n",
        )


@pytest.fixture()
def flow_run_factory(orion_client):
    async def create_flow_run(num_logs: int):
        flow_run = await orion_client.create_flow_run(
            name="scheduled_flow_run", flow=hello_flow
        )

        logs = [
            LogCreate(
                name="prefect.flow_runs",
                level=20,
                message=f"Log {i} from flow_run {flow_run.id}.",
                timestamp=datetime.now(tz=timezone.utc),
                flow_run_id=flow_run.id,
            )
            for i in range(num_logs)
        ]
        await orion_client.create_logs(logs)

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
