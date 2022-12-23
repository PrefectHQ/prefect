from prefect.testing.cli import invoke_and_assert
from prefect.testing.utilities import AsyncMock


def test_orion_status_healthy():
    invoke_and_assert(["orion", "status"], expected_output_contains="Healthy")


def test_orion_status_unhealthy(monkeypatch):
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


def test_orion_status_wait_arg(monkeypatch):
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

    invoke_and_assert(["orion", "status", "--wait"], expected_output_contains="Healthy")


def test_orion_status_timeout(monkeypatch):
    async def mock_api_healthcheck(*_):
        return Exception("All connection attempts failed")

    monkeypatch.setattr(
        "prefect.client.OrionClient.api_healthcheck", mock_api_healthcheck
    )
    invoke_and_assert(
        ["orion", "status", "--wait", "--timeout", "1"],
        expected_output_contains="Server did not respond",
    )
