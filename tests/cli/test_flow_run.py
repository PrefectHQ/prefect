from uuid import UUID, uuid4

import pytest

import prefect.exceptions
from prefect import flow
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
            expected_output_contains=f"Flow run '{before.id}' was succcessfully scheduled for cancellation.",
        )
        after = await orion_client.read_flow_run(before.id)
        assert before.state.name != after.state.name
        assert before.state.type != after.state.type
        assert after.state.name == "Cancelling"
        assert after.state.type == StateType.CANCELLED

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
            expected_output_contains=f"Flow run '{before.id}' was unable to be cancelled.",
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
