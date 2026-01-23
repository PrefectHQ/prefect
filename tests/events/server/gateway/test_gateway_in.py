from typing import Tuple
from unittest import mock

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
from starlette.status import WS_1002_PROTOCOL_ERROR, WS_1008_POLICY_VIOLATION
from starlette.testclient import WebSocketTestSession
from starlette.websockets import WebSocketDisconnect

from prefect.server.events import messaging
from prefect.server.events.schemas.events import Event
from prefect.server.events.storage import database
from prefect.settings import PREFECT_SERVER_API_AUTH_STRING, temporary_settings
from prefect.types._datetime import DateTime


@pytest.fixture(autouse=True)
def publish(monkeypatch: pytest.MonkeyPatch) -> mock.AsyncMock:
    mock_publish = mock.AsyncMock()
    monkeypatch.setattr("prefect.server.events.messaging.publish", mock_publish)
    return mock_publish


@pytest.fixture
async def stream_publish(
    monkeypatch: pytest.MonkeyPatch,
) -> Tuple[mock.MagicMock, mock.AsyncMock]:
    mock_create_publisher = mock.MagicMock(spec=messaging.create_event_publisher)
    mock_publish = mock.AsyncMock()
    mock_create_publisher.return_value.__aenter__.return_value.publish_event = (
        mock_publish
    )

    monkeypatch.setattr(
        "prefect.server.events.messaging.create_event_publisher", mock_create_publisher
    )

    return mock_publish


@pytest.fixture
async def write_events(monkeypatch: pytest.MonkeyPatch):
    mock_write_events = mock.AsyncMock(spec=database.write_events)
    monkeypatch.setattr(database, "write_events", mock_write_events)

    return mock_write_events


def test_streaming_requires_prefect_subprotocol_when_auth_configured(
    test_client: TestClient,
):
    """When PREFECT_SERVER_API_AUTH_STRING is set, the prefect subprotocol is required."""
    with temporary_settings(updates={PREFECT_SERVER_API_AUTH_STRING: "valid-token"}):
        with pytest.raises(WebSocketDisconnect) as exception:
            with test_client.websocket_connect("/api/events/in", subprotocols=[]):
                pass

        assert exception.value.code == WS_1002_PROTOCOL_ERROR


def test_streaming_requires_authentication_when_auth_configured(
    test_client: TestClient,
    event1: Event,
):
    """When PREFECT_SERVER_API_AUTH_STRING is set, an auth message is required."""
    with temporary_settings(updates={PREFECT_SERVER_API_AUTH_STRING: "valid-token"}):
        with pytest.raises(WebSocketDisconnect) as exception:
            with test_client.websocket_connect(
                "/api/events/in", subprotocols=["prefect"]
            ) as websocket:
                websocket.send_text(event1.model_dump_json())
                websocket.receive_text()

        assert exception.value.code == WS_1008_POLICY_VIOLATION
        assert exception.value.reason == "Expected 'auth' message"


def test_streaming_rejects_invalid_token(
    test_client: TestClient,
):
    with temporary_settings(updates={PREFECT_SERVER_API_AUTH_STRING: "valid-token"}):
        with pytest.raises(WebSocketDisconnect) as exception:
            with test_client.websocket_connect(
                "/api/events/in", subprotocols=["prefect"]
            ) as websocket:
                auth_message = {
                    "type": "auth",
                    "token": "invalid-token",
                }
                websocket.send_json(auth_message)
                websocket.receive_json()

        assert exception.value.code == WS_1008_POLICY_VIOLATION
        assert exception.value.reason == "Invalid token"


def test_streaming_rejects_missing_token(
    test_client: TestClient,
):
    with temporary_settings(updates={PREFECT_SERVER_API_AUTH_STRING: "valid-token"}):
        with pytest.raises(WebSocketDisconnect) as exception:
            with test_client.websocket_connect(
                "/api/events/in", subprotocols=["prefect"]
            ) as websocket:
                auth_message = {
                    "type": "auth",
                }
                websocket.send_json(auth_message)
                websocket.receive_json()

        assert exception.value.code == WS_1008_POLICY_VIOLATION
        assert exception.value.reason == "Auth required but no token provided"


def test_stream_events_in_without_auth(
    test_client: TestClient,
    frozen_time: DateTime,
    event1: Event,
    event2: Event,
    stream_publish: mock.AsyncMock,
):
    """When PREFECT_SERVER_API_AUTH_STRING is not set, connections work without auth."""
    websocket: WebSocketTestSession
    # When auth is not configured, no subprotocol or auth handshake is required
    with test_client.websocket_connect("/api/events/in") as websocket:
        websocket.send_text(event1.model_dump_json())
        websocket.send_text(event2.model_dump_json())

    server_events = [
        event1.receive(received=frozen_time),
        event2.receive(received=frozen_time),
    ]
    stream_publish.assert_has_awaits([mock.call(event) for event in server_events])


def test_stream_events_in_with_auth_string(
    test_client: TestClient,
    frozen_time: DateTime,
    event1: Event,
    event2: Event,
    stream_publish: mock.AsyncMock,
):
    with temporary_settings(updates={PREFECT_SERVER_API_AUTH_STRING: "valid-token"}):
        websocket: WebSocketTestSession
        with test_client.websocket_connect(
            "/api/events/in", subprotocols=["prefect"]
        ) as websocket:
            auth_message = {
                "type": "auth",
                "token": "valid-token",
            }
            websocket.send_json(auth_message)
            message = websocket.receive_json()
            assert message["type"] == "auth_success"

            websocket.send_text(event1.model_dump_json())
            websocket.send_text(event2.model_dump_json())

        server_events = [
            event1.receive(received=frozen_time),
            event2.receive(received=frozen_time),
        ]
        stream_publish.assert_has_awaits([mock.call(event) for event in server_events])


def test_post_events(
    test_client: TestClient,
    frozen_time: DateTime,
    event1: Event,
    event2: Event,
    publish: mock.AsyncMock,
):
    response = test_client.post(
        "/api/events",
        json=[
            event1.model_dump(mode="json"),
            event2.model_dump(mode="json"),
        ],
    )
    assert response.status_code == 204
    server_events = [
        event1.receive(received=frozen_time),
        event2.receive(received=frozen_time),
    ]
    publish.assert_awaited_once_with(server_events)


async def test_post_events_ephemeral(
    client: AsyncClient,
    event1: Event,
    event2: Event,
    monkeypatch: pytest.MonkeyPatch,
):
    pipeline_mock = mock.AsyncMock()
    monkeypatch.setattr(
        "prefect.server.events.pipeline.EventsPipeline.process_events", pipeline_mock
    )

    response = await client.post(
        # need to use the same base_url as the events client
        "http://ephemeral-prefect/api/events",
        json=[
            event1.model_dump(mode="json"),
            event2.model_dump(mode="json"),
        ],
    )
    assert response.status_code == 204
    pipeline_mock.assert_awaited_once_with([event1, event2])
