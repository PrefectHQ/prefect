from prefect import OrionClient
from prefect.testing.cli import invoke_and_assert
from prefect.utilities.asyncutils import run_sync_in_worker_thread


def test_start_agent_with_no_args():
    invoke_and_assert(
        command=["agent", "start"],
        expected_output="No work queues provided!",
        expected_code=1,
    )


def test_start_agent_run_once():
    invoke_and_assert(
        command=["agent", "start", "--run-once", "-q", "test"],
        expected_code=0,
        expected_output_contains=["Agent started!", "Agent stopped!"],
    )


async def test_start_agent_creates_work_queue(orion_client: OrionClient):
    await run_sync_in_worker_thread(
        invoke_and_assert,
        command=["agent", "start", "--run-once", "-q", "test"],
        expected_code=0,
        expected_output_contains=["Agent stopped!", "Agent started!"],
    )

    queue = await orion_client.read_work_queue_by_name("test")
    assert queue
    assert queue.name == "test"


def test_start_agent_with_work_queue_and_tags():
    invoke_and_assert(
        command=["agent", "start", "hello", "-t", "blue"],
        expected_output_contains="Only one of `work_queues`, `match`, or `tags` can be provided.",
        expected_code=1,
    )

    invoke_and_assert(
        command=["agent", "start", "-q", "hello", "-t", "blue"],
        expected_output_contains="Only one of `work_queues`, `match`, or `tags` can be provided.",
        expected_code=1,
    )


def test_start_agent_with_regex_and_work_queue():
    invoke_and_assert(
        command=["agent", "start", "hello", "-m", "blue"],
        expected_output_contains="Only one of `work_queues`, `match`, or `tags` can be provided.",
        expected_code=1,
    )

    invoke_and_assert(
        command=["agent", "start", "-q", "hello", "--match", "blue"],
        expected_output_contains="Only one of `work_queues`, `match`, or `tags` can be provided.",
        expected_code=1,
    )
