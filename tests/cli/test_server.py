from typing import List
from unittest.mock import ANY

import pytest

import prefect
import prefect.cli.server
from prefect.settings import PREFECT_SERVER_API_KEEPALIVE_TIMEOUT, temporary_settings
from prefect.testing.cli import invoke_and_assert
from prefect.testing.utilities import AsyncMock


@pytest.fixture
def mock_run_process(monkeypatch: pytest.MonkeyPatch):
    def mark_as_started(*args, task_status, **kwargs):
        task_status.started()

    mock = AsyncMock(side_effect=mark_as_started)
    monkeypatch.setattr(prefect.cli.server, "run_process", mock)
    yield mock


@pytest.mark.parametrize("command_group", ["orion", "server"])
def test_start_no_options(mock_run_process: AsyncMock, command_group: str):
    invoke_and_assert(
        [command_group, "start"],
        expected_output_contains=[
            "prefect config set PREFECT_API_URL=http://127.0.0.1:4200/api",
            "View the API reference documentation at http://127.0.0.1:4200/docs",
        ],
    )
    mock_run_process.assert_awaited_once_with(
        command=[
            "uvicorn",
            "--app-dir",
            f'"{prefect.__module_path__.parent}"',  # note, wrapped in double quotes
            "--factory",
            "prefect.server.api.server:create_app",
            "--host",
            "127.0.0.1",
            "--port",
            "4200",
            "--timeout-keep-alive",
            "5",
        ],
        env=ANY,
        stream_output=True,
        task_status=ANY,
    )


def test_start_with_keep_alive_from_setting(mock_run_process: AsyncMock):
    with temporary_settings({PREFECT_SERVER_API_KEEPALIVE_TIMEOUT: 100}):
        invoke_and_assert(["server", "start"])

    mock_run_process.assert_awaited_once()
    command: List[str] = mock_run_process.call_args[1]["command"]
    assert "--timeout-keep-alive" in command
    assert command[command.index("--timeout-keep-alive") + 1] == "100"


def test_start_from_cli_with_keep_alive(mock_run_process: AsyncMock):
    invoke_and_assert(
        ["server", "start", "--keep-alive-timeout", "100"],
        expected_output_contains=[
            "prefect config set PREFECT_API_URL=http://127.0.0.1:4200/api",
            "View the API reference documentation at http://127.0.0.1:4200/docs",
        ],
    )

    mock_run_process.assert_awaited_once()
    command: List[str] = mock_run_process.call_args[1]["command"]
    assert "--timeout-keep-alive" in command
    assert command[command.index("--timeout-keep-alive") + 1] == "100"
