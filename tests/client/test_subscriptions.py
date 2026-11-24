import ssl
from unittest.mock import patch

import pytest
from websockets.asyncio.client import connect
from websockets.asyncio.server import ServerConnection, serve

from prefect.client.schemas import TaskRun
from prefect.client.subscriptions import Subscription
from prefect.settings import (
    PREFECT_API_TLS_INSECURE_SKIP_VERIFY,
    PREFECT_CLIENT_CUSTOM_HEADERS,
    temporary_settings,
)

pytestmark = pytest.mark.clear_db


def test_subscription_uses_websocket_connect_with_ssl_for_wss():
    """Test that Subscription creates a connector with SSL context for wss:// URLs"""
    with patch("prefect._internal.websockets.connect", wraps=connect) as mock_connect:
        subscription = Subscription(
            model=TaskRun,
            path="/api/task_runs/subscriptions/scheduled",
            keys=["test.task"],
            base_url="https://api.example.com",
        )

    # Verify the connection is configured
    assert subscription._connect is not None
    # Verify SSL context is configured for wss:// URL
    ssl_context = mock_connect.call_args.kwargs["ssl"]
    assert isinstance(ssl_context, ssl.SSLContext)
    assert ssl_context.check_hostname is True
    assert ssl_context.verify_mode == ssl.CERT_REQUIRED


def test_subscription_uses_websocket_connect_with_insecure_ssl():
    """Test that Subscription respects insecure SSL mode setting"""
    with (
        temporary_settings({PREFECT_API_TLS_INSECURE_SKIP_VERIFY: True}),
        patch("prefect._internal.websockets.connect", wraps=connect) as mock_connect,
    ):
        Subscription(
            model=TaskRun,
            path="/api/task_runs/subscriptions/scheduled",
            keys=["test.task"],
            base_url="https://api.example.com",
        )

        # Verify SSL context is configured with insecure mode
        ssl_context = mock_connect.call_args.kwargs["ssl"]
        assert not ssl_context.check_hostname
        assert ssl_context.verify_mode == ssl.CERT_NONE


def test_subscription_no_ssl_for_http():
    """Test that Subscription doesn't add SSL for http:// URLs"""
    with patch("prefect._internal.websockets.connect", wraps=connect) as mock_connect:
        Subscription(
            model=TaskRun,
            path="/api/task_runs/subscriptions/scheduled",
            keys=["test.task"],
            base_url="http://localhost:4200",
        )

    # Verify SSL is not configured for http:// URLs
    assert "ssl" not in mock_connect.call_args.kwargs


def test_subscription_uses_custom_headers_from_settings():
    """Test that Subscription respects custom headers from settings"""
    custom_headers = {"X-Custom-Header": "test-value", "Authorization": "Bearer token"}

    with temporary_settings({PREFECT_CLIENT_CUSTOM_HEADERS: custom_headers}):
        subscription = Subscription(
            model=TaskRun,
            path="/api/task_runs/subscriptions/scheduled",
            keys=["test.task"],
            base_url="https://api.example.com",
        )

        # Verify custom headers are added
        assert subscription._connect.additional_headers is not None
        assert (
            subscription._connect.additional_headers["X-Custom-Header"] == "test-value"
        )
        assert (
            subscription._connect.additional_headers["Authorization"] == "Bearer token"
        )


def test_subscription_empty_custom_headers_doesnt_break():
    """Test that empty custom headers don't cause issues"""
    with temporary_settings({PREFECT_CLIENT_CUSTOM_HEADERS: {}}):
        subscription = Subscription(
            model=TaskRun,
            path="/api/task_runs/subscriptions/scheduled",
            keys=["test.task"],
            base_url="https://api.example.com",
        )

        # Should create successfully without errors
        assert subscription._connect is not None


def test_subscription_url_conversion_http_to_ws():
    """Test that Subscription properly converts HTTP URL to WebSocket URL"""
    subscription = Subscription(
        model=TaskRun,
        path="/api/task_runs/subscriptions/scheduled",
        keys=["test.task"],
        base_url="http://localhost:4200",
    )

    assert (
        subscription.subscription_url
        == "ws://localhost:4200/api/task_runs/subscriptions/scheduled"
    )


def test_subscription_url_conversion_https_to_wss():
    """Test that Subscription properly converts HTTPS URL to WSS URL"""
    subscription = Subscription(
        model=TaskRun,
        path="/api/task_runs/subscriptions/scheduled",
        keys=["test.task"],
        base_url="https://api.example.com",
    )

    assert (
        subscription.subscription_url
        == "wss://api.example.com/api/task_runs/subscriptions/scheduled"
    )


@pytest.mark.usefixtures("hosted_api_server")
async def test_subscription_integration_with_custom_headers(hosted_api_server: str):
    """Integration test verifying Subscription works with custom headers"""
    custom_headers = {"X-Test-Header": "integration-test"}

    with temporary_settings({PREFECT_CLIENT_CUSTOM_HEADERS: custom_headers}):
        subscription = Subscription(
            model=TaskRun,
            path="/api/task_runs/subscriptions/scheduled",
            keys=["test.task"],
            base_url=hosted_api_server,
        )

        # Verify the subscription can be created with custom headers
        # The actual connection happens in _ensure_connected, which we're not testing here
        # but we verify the connector is properly configured
        assert subscription._connect is not None
        assert (
            subscription._connect.additional_headers["X-Test-Header"]
            == "integration-test"
        )


async def test_subscription_reconnects_after_server_disconnect():
    task_run = TaskRun(task_key="test.task", dynamic_key="0")
    connections = 0

    async def handler(websocket: ServerConnection) -> None:
        nonlocal connections
        connections += 1
        await websocket.recv()  # auth
        await websocket.send('{"type":"auth_success"}')
        await websocket.recv()  # subscribe
        if connections == 1:
            await websocket.close(code=1011)
        else:
            await websocket.send(task_run.model_dump_json())
            await websocket.recv()  # ack

    async with serve(handler, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        subscription = Subscription(
            model=TaskRun,
            path="/api/task_runs/subscriptions/scheduled",
            keys=["test.task"],
            base_url=f"http://127.0.0.1:{port}",
        )
        try:
            assert await anext(subscription) == task_run
            assert connections == 2
        finally:
            await subscription._connect.__aexit__(None, None, None)
