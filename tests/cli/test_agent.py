from unittest.mock import ANY

import prefect.cli.agent
from prefect import OrionClient
from prefect.settings import PREFECT_AGENT_PREFETCH_SECONDS, temporary_settings
from prefect.testing.cli import invoke_and_assert
from prefect.testing.utilities import MagicMock
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


def test_start_agent_with_prefetch_seconds(monkeypatch):
    mock_agent = MagicMock()
    monkeypatch.setattr(prefect.cli.agent, "OrionAgent", mock_agent)
    invoke_and_assert(
        command=[
            "agent",
            "start",
            "--prefetch-seconds",
            "30",
            "-q",
            "test",
            "--run-once",
        ],
        expected_code=0,
    )
    mock_agent.assert_called_once_with(
        work_queues=["test"],
        work_queue_prefix=ANY,
        prefetch_seconds=30,
        limit=None,
    )


def test_start_agent_with_prefetch_seconds_from_setting_by_default(monkeypatch):
    mock_agent = MagicMock()
    monkeypatch.setattr(prefect.cli.agent, "OrionAgent", mock_agent)
    with temporary_settings({PREFECT_AGENT_PREFETCH_SECONDS: 100}):
        invoke_and_assert(
            command=[
                "agent",
                "start",
                "-q",
                "test",
                "--run-once",
            ],
            expected_code=0,
        )
    mock_agent.assert_called_once_with(
        work_queues=ANY,
        work_queue_prefix=ANY,
        prefetch_seconds=100,
        limit=None,
    )


def test_start_agent_respects_work_queue_names(monkeypatch):
    mock_agent = MagicMock()
    monkeypatch.setattr(prefect.cli.agent, "OrionAgent", mock_agent)
    invoke_and_assert(
        command=["agent", "start", "-q", "a", "-q", "b", "--run-once"],
        expected_code=0,
    )
    mock_agent.assert_called_once_with(
        work_queues=["a", "b"],
        work_queue_prefix=[],
        prefetch_seconds=ANY,
        limit=None,
    )


def test_start_agent_respects_work_queue_prefixes(monkeypatch):
    mock_agent = MagicMock()
    monkeypatch.setattr(prefect.cli.agent, "OrionAgent", mock_agent)
    invoke_and_assert(
        command=["agent", "start", "-m", "a", "-m", "b", "--run-once"],
        expected_code=0,
    )
    mock_agent.assert_called_once_with(
        work_queues=[],
        work_queue_prefix=["a", "b"],
        prefetch_seconds=ANY,
        limit=None,
    )


def test_start_agent_respects_limit(monkeypatch):
    mock_agent = MagicMock()
    monkeypatch.setattr(prefect.cli.agent, "OrionAgent", mock_agent)
    invoke_and_assert(
        command=["agent", "start", "--limit", "10", "--run-once", "-q", "test"],
        expected_code=0,
    )
    mock_agent.assert_called_once_with(
        work_queues=["test"],
        work_queue_prefix=[],
        prefetch_seconds=ANY,
        limit=10,
    )


def test_start_agent_with_work_queue_match_and_work_queue():
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
