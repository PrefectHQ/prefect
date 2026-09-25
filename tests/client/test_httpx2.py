import ssl

import httpcore as legacy_httpcore
import httpx as legacy_httpx
import pytest
from httpx import Response as MockResponse
from respx import MockRouter

from prefect._internal.compatibility.httpx import httpcore, httpx
from prefect.client.base import PrefectHttpxAsyncClient, PrefectHttpxSyncClient
from prefect.client.cloud import get_cloud_client
from prefect.client.orchestration import get_client
from prefect.exceptions import PrefectHTTPStatusError
from prefect.settings import PREFECT_API_URL, temporary_settings


@pytest.mark.parametrize("sync_client", [False, True])
async def test_client_accepts_native_auth_timeout_and_transport(sync_client: bool):
    requests: list[httpx.Request] = []

    def handle_request(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json="Hello!")

    timeout = httpx.Timeout(11, connect=2, read=3, write=5, pool=7)
    settings = {
        "auth": httpx.BasicAuth("user", "password"),
        "timeout": timeout,
        "transport": httpx.MockTransport(handle_request),
    }
    with temporary_settings({PREFECT_API_URL: "https://api.example.test/api"}):
        if sync_client:
            with get_client(httpx_settings=settings, sync_client=True) as client:
                response = client.hello()
                assert client.api_url == httpx.URL("https://api.example.test/api/")
        else:
            async with get_client(httpx_settings=settings) as client:
                response = await client.hello()
                assert client.api_url == httpx.URL("https://api.example.test/api/")

    assert isinstance(response, httpx.Response)
    assert response.json() == "Hello!"
    assert len(requests) == 1
    request = requests[0]
    assert isinstance(request, httpx.Request)
    assert request.url == httpx.URL("https://api.example.test/api/hello")
    assert request.headers["Authorization"] == "Basic dXNlcjpwYXNzd29yZA=="
    assert request.extensions["timeout"] == timeout.as_dict()


@pytest.mark.parametrize("sync_client", [False, True])
async def test_mocked_status_errors_preserve_response_details(
    sync_client: bool, respx_mock: MockRouter
):
    route = respx_mock.get("https://api.example.test/api/hello").respond(
        418, json={"detail": "The server is a teapot"}
    )

    with (
        temporary_settings({PREFECT_API_URL: "https://api.example.test/api"}),
        pytest.raises(httpx.HTTPStatusError) as error,
    ):
        if sync_client:
            with get_client(sync_client=True) as client:
                client.hello()
        else:
            async with get_client() as client:
                await client.hello()

    assert route.call_count == 1
    assert isinstance(error.value, PrefectHTTPStatusError)
    assert isinstance(error.value.request, httpx.Request)
    assert isinstance(error.value.response, httpx.Response)
    assert error.value.response.status_code == 418
    assert error.value.response.json() == {"detail": "The server is a teapot"}


@pytest.mark.parametrize("sync_client", [False, True])
async def test_clients_retry_rate_limits(sync_client: bool, respx_mock: MockRouter):
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
    assert isinstance(response, httpx.Response)
    assert response.json() == "Hello!"


async def test_cloud_raw_request_returns_native_response(respx_mock: MockRouter):
    respx_mock.get("https://cloud.example.test/api/probe").respond(
        200, json={"working": True}
    )

    async with get_cloud_client(host="https://cloud.example.test/api") as client:
        response = await client.raw_request("GET", "/probe")

    assert isinstance(response, httpx.Response)
    assert response.json() == {"working": True}


@pytest.mark.parametrize("sync_client", [False, True])
async def test_client_preserves_legacy_certificate_roots(sync_client: bool):
    expected = legacy_httpx.create_ssl_context(trust_env=False)
    if sync_client:
        with PrefectHttpxSyncClient(trust_env=False) as client:
            actual = client._transport._pool._ssl_context
    else:
        async with PrefectHttpxAsyncClient(trust_env=False) as client:
            actual = client._transport._pool._ssl_context

    assert type(actual) is ssl.SSLContext
    assert actual.verify_mode == ssl.CERT_REQUIRED
    assert actual.check_hostname is True
    assert actual.get_ca_certs(binary_form=True) == expected.get_ca_certs(
        binary_form=True
    )


@pytest.mark.parametrize("sync_client", [False, True])
@pytest.mark.parametrize("verify", [False, True])
async def test_client_preserves_explicit_tls_verification(
    sync_client: bool, verify: bool
):
    if sync_client:
        with PrefectHttpxSyncClient(verify=verify, trust_env=False) as client:
            context = client._transport._pool._ssl_context
    else:
        async with PrefectHttpxAsyncClient(verify=verify, trust_env=False) as client:
            context = client._transport._pool._ssl_context

    assert context.verify_mode == (ssl.CERT_REQUIRED if verify else ssl.CERT_NONE)
    assert context.check_hostname is verify


@pytest.mark.parametrize("sync_client", [False, True])
async def test_custom_transport_does_not_evaluate_ignored_tls_settings(
    sync_client: bool,
):
    settings = {
        "transport": httpx.MockTransport(lambda request: httpx.Response(200)),
        "verify": "/nonexistent/ignored-ca.pem",
    }
    if sync_client:
        with PrefectHttpxSyncClient(**settings) as client:
            response = client.get("https://api.example.test/")
    else:
        async with PrefectHttpxAsyncClient(**settings) as client:
            response = await client.get("https://api.example.test/")
    assert response.status_code == 200


@pytest.mark.parametrize("sync_client", [False, True])
@pytest.mark.parametrize("proxy_source", ["argument", "environment"])
async def test_https_proxy_preserves_legacy_certificate_roots(
    sync_client: bool, proxy_source: str, monkeypatch: pytest.MonkeyPatch
):
    proxy_url = "https://proxy.example.test:8443"
    if proxy_source == "environment":
        monkeypatch.setenv("HTTPS_PROXY", proxy_url)
        monkeypatch.setenv("NO_PROXY", "")
        settings = {}
    else:
        settings = {"proxy": proxy_url, "trust_env": False}
    destination = httpx.URL("https://api.example.test/")
    if sync_client:
        with PrefectHttpxSyncClient(**settings) as client:
            pool = client._transport_for_url(destination)._pool
    else:
        async with PrefectHttpxAsyncClient(**settings) as client:
            pool = client._transport_for_url(destination)._pool

    # The underlying pool selects its backend's default at connect time when
    # no explicit proxy context was supplied.
    actual = pool._proxy_ssl_context or httpcore.default_ssl_context()
    expected = legacy_httpcore.default_ssl_context()
    assert type(actual) is ssl.SSLContext
    assert actual.get_ca_certs(binary_form=True) == expected.get_ca_certs(
        binary_form=True
    )


@pytest.mark.parametrize("sync_client", [False, True])
@pytest.mark.parametrize("custom_context", [False, True])
async def test_https_proxy_preserves_caller_configuration(
    sync_client: bool, custom_context: bool
):
    context = ssl.create_default_context() if custom_context else None
    proxy = httpx.Proxy("https://proxy.example.test:8443", ssl_context=context)
    destination = httpx.URL("https://api.example.test/")
    if sync_client:
        with PrefectHttpxSyncClient(proxy=proxy, trust_env=False) as client:
            actual = client._transport_for_url(destination)._pool._proxy_ssl_context
    else:
        async with PrefectHttpxAsyncClient(proxy=proxy, trust_env=False) as client:
            actual = client._transport_for_url(destination)._pool._proxy_ssl_context
    assert proxy.ssl_context is context
    if custom_context:
        assert actual is context
