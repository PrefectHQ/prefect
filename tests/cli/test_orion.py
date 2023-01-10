from prefect.settings import PREFECT_API_URL, temporary_settings
from prefect.testing.cli import invoke_and_assert


def test_orion_status_healthy(monkeypatch):
    api_url = "http://127.0.0.1:4200/api"
    with temporary_settings({PREFECT_API_URL: api_url}):
        invoke_and_assert(
            ["orion", "status"], expected_output_contains="Server is healthy!"
        )


# def test_orion_status_unhealthy(monkeypatch):
#     async def mock_api_healthcheck(*args):
#         return Exception("All connection attempts failed")

#     monkeypatch.setattr(
#         "prefect.client.OrionClient.api_healthcheck", mock_api_healthcheck
#     )
#     invoke_and_assert(
#         ["orion", "status"],
#         expected_output_contains="All connection attempts failed",
#         expected_code=1,
#     )


# def test_orion_status_wait_arg(monkeypatch):
#     retry_response = "All connection attempts failed"
#     mock_waiting_healthcheck = AsyncMock()

#     monkeypatch.setattr(
#         "prefect.client.OrionClient.api_healthcheck", mock_waiting_healthcheck
#     )
#     mock_waiting_healthcheck.side_effect = [
#         retry_response,
#         retry_response,
#         retry_response,
#         None,
#     ]

#     invoke_and_assert(["orion", "status", "--wait"], expected_output_contains="Server is healthy!")


# def test_orion_status_timeout(monkeypatch):
#     async def mock_api_healthcheck(*_):
#         return Exception("All connection attempts failed")

#     monkeypatch.setattr(
#         "prefect.client.OrionClient.api_healthcheck", mock_api_healthcheck
#     )
#     invoke_and_assert(
#         ["orion", "status", "--wait", "--timeout", "1"],
#         expected_output_contains="Server did not respond", expected_code=1
#     )
