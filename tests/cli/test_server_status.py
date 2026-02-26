import json
from unittest.mock import AsyncMock, patch

import pytest

from prefect.settings import PREFECT_API_URL
from prefect.settings.context import temporary_settings
from prefect.testing.cli import invoke_and_assert

_SERVER_MOD = "prefect.cli.server"


@pytest.fixture(autouse=True)
def set_api_url():
    with temporary_settings({PREFECT_API_URL: "http://localhost:4200/api"}):
        yield


def _mock_client(healthy: bool = True, server_version: str = "3.0.0"):
    mock = AsyncMock()
    if healthy:
        mock.api_healthcheck = AsyncMock(return_value=None)
        mock.api_version = AsyncMock(return_value=server_version)
    else:
        mock.api_healthcheck = AsyncMock(
            return_value=ConnectionError("Connection refused")
        )
    return mock


def _patch_get_client(mock):
    """Patch get_client for the server status command."""
    mock_ctx = AsyncMock(
        __aenter__=AsyncMock(return_value=mock),
        __aexit__=AsyncMock(return_value=False),
    )
    return patch("prefect.client.orchestration.get_client", return_value=mock_ctx)


class TestServerStatus:
    def test_status_healthy_server(self):
        mock = _mock_client(healthy=True, server_version="3.0.0")
        with _patch_get_client(mock):
            invoke_and_assert(
                command=["server", "status"],
                expected_output_contains=[
                    "Server is available",
                    "http://localhost:4200/api",
                    "3.0.0",
                ],
                expected_code=0,
            )

    def test_status_unhealthy_server(self):
        mock = _mock_client(healthy=False)
        with _patch_get_client(mock):
            invoke_and_assert(
                command=["server", "status"],
                expected_output_contains="Server is not available",
                expected_code=1,
            )

    def test_status_healthy_server_json_output(self):
        mock = _mock_client(healthy=True, server_version="3.0.0")
        with _patch_get_client(mock):
            result = invoke_and_assert(
                command=["server", "status", "--output", "json"],
                expected_code=0,
            )
            output = json.loads(result.stdout.strip())
            assert output["status"] == "available"
            assert output["api_url"] == "http://localhost:4200/api"
            assert output["server_version"] == "3.0.0"

    def test_status_unhealthy_server_json_output(self):
        mock = _mock_client(healthy=False)
        with _patch_get_client(mock):
            result = invoke_and_assert(
                command=["server", "status", "--output", "json"],
                expected_code=1,
            )
            output = json.loads(result.stdout.strip())
            assert output["status"] == "unavailable"
            assert "error" in output

    def test_status_invalid_output_format(self):
        mock = _mock_client(healthy=True)
        with _patch_get_client(mock):
            invoke_and_assert(
                command=["server", "status", "--output", "xml"],
                expected_output_contains="Only 'json' output format is supported.",
                expected_code=1,
            )

    def test_status_wait_succeeds_immediately(self):
        mock = _mock_client(healthy=True, server_version="3.0.0")
        with _patch_get_client(mock):
            invoke_and_assert(
                command=["server", "status", "--wait"],
                expected_output_contains="Server is available",
                expected_code=0,
            )

    def test_status_wait_succeeds_after_retries(self):
        mock = _mock_client(healthy=True, server_version="3.0.0")
        healthcheck_results = iter(
            [
                ConnectionError("Connection refused"),
                ConnectionError("Connection refused"),
                None,
            ]
        )

        async def healthcheck_side_effect():
            return next(healthcheck_results)

        mock.api_healthcheck = AsyncMock(side_effect=healthcheck_side_effect)
        with _patch_get_client(mock):
            invoke_and_assert(
                command=["server", "status", "--wait", "--timeout", "30"],
                expected_output_contains="Server is available",
                expected_code=0,
            )

    def test_status_wait_timeout(self):
        mock = _mock_client(healthy=False)
        monotonic_values = iter([0.0, 0.5, 5.1])

        async def fake_sleep(seconds):
            pass

        with (
            _patch_get_client(mock),
            patch(f"{_SERVER_MOD}.asyncio.sleep", side_effect=fake_sleep),
            patch(f"{_SERVER_MOD}._monotonic", side_effect=monotonic_values),
        ):
            invoke_and_assert(
                command=["server", "status", "--wait", "--timeout", "5"],
                expected_output_contains="Timed out after 5 seconds",
                expected_code=1,
            )

    def test_status_wait_timeout_json_output(self):
        mock = _mock_client(healthy=False)
        monotonic_values = iter([0.0, 0.5, 5.1])

        async def fake_sleep(seconds):
            pass

        with (
            _patch_get_client(mock),
            patch(f"{_SERVER_MOD}.asyncio.sleep", side_effect=fake_sleep),
            patch(f"{_SERVER_MOD}._monotonic", side_effect=monotonic_values),
        ):
            result = invoke_and_assert(
                command=[
                    "server",
                    "status",
                    "--wait",
                    "--timeout",
                    "5",
                    "--output",
                    "json",
                ],
                expected_code=1,
            )
            output = json.loads(result.stdout.strip())
            assert output["status"] == "timed_out"
            assert output["timeout"] == 5

    def test_status_version_fetch_failure(self):
        mock = _mock_client(healthy=True)
        mock.api_version = AsyncMock(side_effect=Exception("version error"))
        with _patch_get_client(mock):
            invoke_and_assert(
                command=["server", "status"],
                expected_output_contains="Server is available",
                expected_output_does_not_contain="Server version",
                expected_code=0,
            )

    def test_status_no_api_url_configured(self):
        mock = _mock_client(healthy=True)
        with (
            _patch_get_client(mock),
            temporary_settings({PREFECT_API_URL: None}),
        ):
            invoke_and_assert(
                command=["server", "status"],
                expected_output_contains="No API URL configured",
                expected_code=1,
            )
