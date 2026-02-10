import json
from unittest.mock import AsyncMock, patch

import pytest

from prefect.settings import PREFECT_API_URL
from prefect.settings.context import temporary_settings
from prefect.testing.cli import invoke_and_assert


@pytest.fixture(autouse=True)
def set_api_url():
    with temporary_settings({PREFECT_API_URL: "http://localhost:4200/api"}):
        yield


def _extract_json(stdout: str) -> str:
    lines = stdout.strip().split("\n")
    json_lines = []
    in_json = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("{"):
            in_json = True
        if in_json:
            json_lines.append(line)
        if in_json and stripped.startswith("}"):
            break
    return "\n".join(json_lines)


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
    return patch(
        "prefect.client.orchestration.get_client",
        return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock),
            __aexit__=AsyncMock(return_value=False),
        ),
    )


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
            json_str = _extract_json(result.stdout)
            output = json.loads(json_str)
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
            json_str = _extract_json(result.stdout)
            output = json.loads(json_str)
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

        async def fake_sleep(seconds):
            pass

        with (
            _patch_get_client(mock),
            patch("asyncio.sleep", side_effect=fake_sleep),
        ):
            invoke_and_assert(
                command=["server", "status", "--wait", "--timeout", "1"],
                expected_output_contains="Timed out after 1 seconds",
                expected_code=1,
            )

    def test_status_wait_timeout_json_output(self):
        mock = _mock_client(healthy=False)

        async def fake_sleep(seconds):
            pass

        with (
            _patch_get_client(mock),
            patch("asyncio.sleep", side_effect=fake_sleep),
        ):
            result = invoke_and_assert(
                command=[
                    "server",
                    "status",
                    "--wait",
                    "--timeout",
                    "1",
                    "--output",
                    "json",
                ],
                expected_code=1,
            )
            json_str = _extract_json(result.stdout)
            output = json.loads(json_str)
            assert output["status"] == "timed_out"
            assert output["timeout"] == 1

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
