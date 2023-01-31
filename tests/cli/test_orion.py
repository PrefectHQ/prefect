from typing import List
from unittest.mock import ANY

import pytest

import prefect
import prefect.cli.orion
from prefect.settings import PREFECT_ORION_API_KEEPALIVE_TIMEOUT, temporary_settings
from prefect.testing.cli import invoke_and_assert
from prefect.testing.utilities import AsyncMock


@pytest.fixture
def mock_run_process(monkeypatch: pytest.MonkeyPatch):
    def mark_as_started(*args, task_status, **kwargs):
        task_status.started()

    mock = AsyncMock(side_effect=mark_as_started)
    monkeypatch.setattr(prefect.cli.orion, "run_process", mock)
    yield mock


def test_start_no_options(mock_run_process: AsyncMock):
    invoke_and_assert(
        ["orion", "start"],
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
            "prefect.orion.api.server:create_app",
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
    with temporary_settings({PREFECT_ORION_API_KEEPALIVE_TIMEOUT: 100}):
        invoke_and_assert(["orion", "start"])

    mock_run_process.assert_awaited_once()
    command: List[str] = mock_run_process.call_args[1]["command"]
    assert "--timeout-keep-alive" in command
    assert command[command.index("--timeout-keep-alive") + 1] == "100"


def test_start_from_cli_with_keep_alive(mock_run_process: AsyncMock):
    invoke_and_assert(
        ["orion", "start", "--keep-alive-timeout", "100"],
        expected_output_contains=[
            "prefect config set PREFECT_API_URL=http://127.0.0.1:4200/api",
            "View the API reference documentation at http://127.0.0.1:4200/docs",
        ],
    )

    mock_run_process.assert_awaited_once()
    command: List[str] = mock_run_process.call_args[1]["command"]
    assert "--timeout-keep-alive" in command
    assert command[command.index("--timeout-keep-alive") + 1] == "100"


def test_orion_status_ephemeral_api():
    invoke_and_assert(
        ["orion", "status"],
        expected_output_contains="PREFECT_API_URL not set for the currently active profile",
    )


def test_orion_status_healthy(use_hosted_orion):
    invoke_and_assert(
        ["orion", "status"], expected_output_contains="Server is healthy!"
    )


def test_orion_status_unhealthy(monkeypatch, use_hosted_orion):
    async def mock_api_healthcheck(*args):
        return Exception("All connection attempts failed")

    monkeypatch.setattr(
        "prefect.client.OrionClient.api_healthcheck", mock_api_healthcheck
    )
    invoke_and_assert(
        ["orion", "status"],
        expected_output_contains="All connection attempts failed",
        expected_code=1,
    )


def test_orion_status_wait_arg(monkeypatch, use_hosted_orion):
    retry_response = "All connection attempts failed"
    mock_waiting_healthcheck = AsyncMock()

    monkeypatch.setattr(
        "prefect.client.OrionClient.api_healthcheck", mock_waiting_healthcheck
    )
    mock_waiting_healthcheck.side_effect = [
        retry_response,
        retry_response,
        retry_response,
        None,
    ]

    invoke_and_assert(
        ["orion", "status", "--wait"], expected_output_contains="Server is healthy!"
    )


def test_orion_status_timeout(monkeypatch, use_hosted_orion):
    async def mock_api_healthcheck(*_):
        return Exception("All connection attempts failed")

    monkeypatch.setattr(
        "prefect.client.OrionClient.api_healthcheck", mock_api_healthcheck
    )
    invoke_and_assert(
        ["orion", "status", "--wait", "--timeout", "1"],
        expected_output_contains="Server did not respond",
        expected_code=1,
    )


def test_ephemeral_api():
    invoke_and_assert(
        ["orion", "status"],
        expected_output_contains="PREFECT_API_URL not set for the currently active profile",
    )


def test_orion_status_healthy(use_hosted_orion):
    invoke_and_assert(
        ["orion", "status"], expected_output_contains="Server is healthy!"
    )


def test_orion_status_unhealthy(monkeypatch, use_hosted_orion):
    async def mock_api_healthcheck(*args):
        return Exception("All connection attempts failed")

    monkeypatch.setattr(
        "prefect.client.OrionClient.api_healthcheck", mock_api_healthcheck
    )
    invoke_and_assert(
        ["orion", "status"],
        expected_output_contains="All connection attempts failed",
        expected_code=1,
    )


def test_orion_status_wait_arg(monkeypatch, use_hosted_orion):
    retry_response = "All connection attempts failed"
    mock_waiting_healthcheck = AsyncMock()

    monkeypatch.setattr(
        "prefect.client.OrionClient.api_healthcheck", mock_waiting_healthcheck
    )
    mock_waiting_healthcheck.side_effect = [
        retry_response,
        retry_response,
        retry_response,
        None,
    ]

    invoke_and_assert(
        ["orion", "status", "--wait"], expected_output_contains="Server is healthy!"
    )


def test_orion_status_timeout(monkeypatch, use_hosted_orion):
    async def mock_api_healthcheck(*_):
        return Exception("All connection attempts failed")

    monkeypatch.setattr(
        "prefect.client.OrionClient.api_healthcheck", mock_api_healthcheck
    )
    invoke_and_assert(
        ["orion", "status", "--wait", "--timeout", "1"],
        expected_output_contains="Server did not respond",
        expected_code=1,
    )
