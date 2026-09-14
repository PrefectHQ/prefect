import httpx2
import pytest
from httpx import Response as MockResponse
from respx import MockRouter

from prefect.client.cloud import get_cloud_client
from prefect.client.orchestration import get_client
from prefect.exceptions import PrefectHTTPStatusError
from prefect.settings import PREFECT_API_URL, temporary_settings


@pytest.mark.parametrize("sync_client", [False, True])
async def test_client_accepts_httpx2_auth_timeout_and_transport(sync_client: bool):
    requests: list[httpx2.Request] = []

    def handle_request(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return httpx2.Response(200, json="Hello!")

    timeout = httpx2.Timeout(11, connect=2, read=3, write=5, pool=7)
    settings = {
        "auth": httpx2.BasicAuth("user", "password"),
        "timeout": timeout,
        "transport": httpx2.MockTransport(handle_request),
    }
    with temporary_settings({PREFECT_API_URL: "https://api.example.test/api"}):
        if sync_client:
            with get_client(httpx_settings=settings, sync_client=True) as client:
                response = client.hello()
                assert client.api_url == httpx2.URL("https://api.example.test/api/")
        else:
            async with get_client(httpx_settings=settings) as client:
                response = await client.hello()
                assert client.api_url == httpx2.URL("https://api.example.test/api/")

    assert isinstance(response, httpx2.Response)
    assert response.json() == "Hello!"
    assert len(requests) == 1
    request = requests[0]
    assert isinstance(request, httpx2.Request)
    assert request.url == httpx2.URL("https://api.example.test/api/hello")
    assert request.headers["Authorization"] == "Basic dXNlcjpwYXNzd29yZA=="
    assert request.extensions["timeout"] == timeout.as_dict()


@pytest.mark.parametrize("sync_client", [False, True])
async def test_mocked_httpx2_status_errors_preserve_response_details(
    sync_client: bool, respx_mock: MockRouter
):
    route = respx_mock.get("https://api.example.test/api/hello").respond(
        418, json={"detail": "The server is a teapot"}
    )

    with (
        temporary_settings({PREFECT_API_URL: "https://api.example.test/api"}),
        pytest.raises(httpx2.HTTPStatusError) as error,
    ):
        if sync_client:
            with get_client(sync_client=True) as client:
                client.hello()
        else:
            async with get_client() as client:
                await client.hello()

    assert route.call_count == 1
    assert isinstance(error.value, PrefectHTTPStatusError)
    assert isinstance(error.value.request, httpx2.Request)
    assert isinstance(error.value.response, httpx2.Response)
    assert error.value.response.status_code == 418
    assert error.value.response.json() == {"detail": "The server is a teapot"}


@pytest.mark.parametrize("sync_client", [False, True])
async def test_httpx2_clients_retry_rate_limits(
    sync_client: bool, respx_mock: MockRouter
):
    # RESPX converts these legacy response fixtures at the HTTPcore2 boundary.
    route = respx_mock.get("https://api.example.test/api/hello").mock(
        side_effect=[
            MockResponse(429, headers={"Retry-After": "0"}),
            MockResponse(200, json="Hello!"),
        ]
    )

    with temporary_settings({PREFECT_API_URL: "https://api.example.test/api"}):
        if sync_client:
            with get_client(sync_client=True) as client:
                response = client.hello()
        else:
            async with get_client() as client:
                response = await client.hello()

    assert route.call_count == 2
    assert isinstance(response, httpx2.Response)
    assert response.json() == "Hello!"


async def test_cloud_raw_request_returns_httpx2_response(respx_mock: MockRouter):
    respx_mock.get("https://cloud.example.test/api/probe").respond(
        200, json={"working": True}
    )

    async with get_cloud_client(host="https://cloud.example.test/api") as client:
        response = await client.raw_request("GET", "/probe")

    assert isinstance(response, httpx2.Response)
    assert response.json() == {"working": True}
