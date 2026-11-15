import json
import ssl
from collections.abc import Sequence
from unittest.mock import patch
from uuid import uuid4

import pytest
from websockets.asyncio.server import ServerConnection, serve
from websockets.typing import Subprotocol

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
    subscription = Subscription(
        model=TaskRun,
        path="/api/task_runs/subscriptions/scheduled",
        keys=["test.task"],
        base_url="https://api.example.com",
    )

    # Verify SSL context is configured for wss:// URL
    with patch("prefect._internal.websockets.connect") as mock_connect:
        subscription._new_connect()

    _, kwargs = mock_connect.call_args
    ssl_context = kwargs["ssl"]
    assert isinstance(ssl_context, ssl.SSLContext)
    assert ssl_context.check_hostname is True
    assert ssl_context.verify_mode == ssl.CERT_REQUIRED


def test_subscription_uses_websocket_connect_with_insecure_ssl():
    """Test that Subscription respects insecure SSL mode setting"""
    with temporary_settings({PREFECT_API_TLS_INSECURE_SKIP_VERIFY: True}):
        subscription = Subscription(
            model=TaskRun,
            path="/api/task_runs/subscriptions/scheduled",
            keys=["test.task"],
            base_url="https://api.example.com",
        )

        # Verify SSL context is configured with insecure mode
        with patch("prefect._internal.websockets.connect") as mock_connect:
            subscription._new_connect()

        _, kwargs = mock_connect.call_args
        ssl_context = kwargs["ssl"]
        assert not ssl_context.check_hostname
        assert ssl_context.verify_mode == ssl.CERT_NONE


def test_subscription_no_ssl_for_http():
    """Test that Subscription doesn't add SSL for http:// URLs"""
    subscription = Subscription(
        model=TaskRun,
        path="/api/task_runs/subscriptions/scheduled",
        keys=["test.task"],
        base_url="http://localhost:4200",
    )

    # Verify SSL is not configured for http:// URLs
    with patch("prefect._internal.websockets.connect") as mock_connect:
        subscription._new_connect()

    _, kwargs = mock_connect.call_args
    assert "ssl" not in kwargs


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
        connector = subscription._new_connect()
        assert connector.additional_headers == {
            "X-Custom-Header": "test-value",
            "Authorization": "Bearer token",
        }


def test_subscription_empty_custom_headers_doesnt_break():
    """Test that empty custom headers don't cause issues"""
    with temporary_settings({PREFECT_CLIENT_CUSTOM_HEADERS: {}}):
        subscription = Subscription(
            model=TaskRun,
            path="/api/task_runs/subscriptions/scheduled",
            keys=["test.task"],
            base_url="https://api.example.com",
        )

        # Should create a connector successfully without errors
        assert subscription._new_connect() is not None


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

        # Verify the connector the subscription builds carries the custom headers
        connector = subscription._new_connect()
        assert connector.additional_headers == {"X-Test-Header": "integration-test"}


async def test_subscription_reconnects_after_the_server_drops_the_connection():
    """Regression test for websockets 17, which raises ``RuntimeError: connect()
    isn't reentrant`` when a connection object that was already entered is entered
    again.

    The subscription must close the previous connection and build a fresh one
    instead of re-entering the stored connection object.
    """
    task_run_1 = TaskRun(flow_run_id=uuid4(), task_key="test.task", dynamic_key="0")
    task_run_2 = TaskRun(flow_run_id=uuid4(), task_key="test.task", dynamic_key="1")

    connections = 0

    async def handler(websocket: ServerConnection) -> None:
        nonlocal connections
        connections += 1

        auth = json.loads(await websocket.recv())
        assert auth["type"] == "auth"
        await websocket.send(json.dumps({"type": "auth_success"}))

        subscribe = json.loads(await websocket.recv())
        assert subscribe["type"] == "subscribe"

        await websocket.send(
            task_run_1.model_dump_json()
            if connections == 1
            else task_run_2.model_dump_json()
        )
        assert json.loads(await websocket.recv()) == {"type": "ack"}

        if connections == 1:
            # Drop the connection abnormally so the client has to reconnect.
            raise ValueError("zonk")

    def select_subprotocol(
        connection: ServerConnection, subprotocols: Sequence[Subprotocol]
    ) -> Subprotocol | None:
        return Subprotocol("prefect") if "prefect" in subprotocols else None

    async with serve(
        handler,
        host="localhost",
        port=0,
        select_subprotocol=select_subprotocol,
    ) as server:
        port = server.sockets[0].getsockname()[1]
        subscription = Subscription(
            model=TaskRun,
            path="/api/task_runs/subscriptions/scheduled",
            keys=["test.task"],
            base_url=f"http://localhost:{port}",
        )

        received = [await anext(subscription), await anext(subscription)]

    assert connections == 2
    assert [run.id for run in received] == [task_run_1.id, task_run_2.id]
