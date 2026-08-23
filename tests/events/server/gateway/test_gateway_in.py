import json
import logging
from typing import Tuple
from unittest import mock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
from starlette.status import WS_1002_PROTOCOL_ERROR, WS_1008_POLICY_VIOLATION
from starlette.testclient import WebSocketTestSession
from starlette.websockets import WebSocketDisconnect

from prefect.server.events import messaging
from prefect.server.events.schemas.events import Event, RelatedResource
from prefect.server.events.storage import database
from prefect.settings import (
    PREFECT_SERVER_API_AUTH_STRING,
    PREFECT_SERVER_EVENTS_MAXIMUM_RELATED_RESOURCES,
    temporary_settings,
)
from prefect.types._datetime import DateTime

pytestmark = pytest.mark.clear_db


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


def test_streaming_requires_prefect_subprotocol_when_auth_configured(
    test_client: TestClient,
):
    """The prefect subprotocol is required when auth is configured."""
    with temporary_settings(updates={PREFECT_SERVER_API_AUTH_STRING: "valid-token"}):
        with pytest.raises(WebSocketDisconnect) as exception:
            with test_client.websocket_connect("/api/events/in", subprotocols=[]):
                pass

        assert exception.value.code == WS_1002_PROTOCOL_ERROR


def test_streaming_accepts_legacy_clients_without_auth(
    test_client: TestClient,
    frozen_time: DateTime,
    event1: Event,
    stream_publish: mock.AsyncMock,
):
    """When auth is not configured, old clients without prefect subprotocol are accepted."""
    websocket: WebSocketTestSession
    with test_client.websocket_connect("/api/events/in", subprotocols=[]) as websocket:
        # Legacy mode: no auth handshake, just send events directly
        websocket.send_text(event1.model_dump_json())

    server_events = [event1.receive(received=frozen_time)]
    stream_publish.assert_has_awaits([mock.call(event) for event in server_events])


def test_streaming_requires_authentication(
    test_client: TestClient,
    event1: Event,
):
    """An auth message is always required as the first message."""
    with pytest.raises(WebSocketDisconnect) as exception:
        with test_client.websocket_connect(
            "/api/events/in", subprotocols=["prefect"]
        ) as websocket:
            websocket.send_text(event1.model_dump_json())
            websocket.receive_text()

    assert exception.value.code == WS_1008_POLICY_VIOLATION
    assert exception.value.reason == "Expected 'auth' message"


def test_stream_events_in_without_auth_configured(
    test_client: TestClient,
    frozen_time: DateTime,
    event1: Event,
    event2: Event,
    stream_publish: mock.AsyncMock,
):
    """When PREFECT_SERVER_API_AUTH_STRING is not set, any token is accepted."""
    websocket: WebSocketTestSession
    with test_client.websocket_connect(
        "/api/events/in", subprotocols=["prefect"]
    ) as websocket:
        auth_message = {
            "type": "auth",
            "token": None,
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


def test_stream_events_in_drops_an_unparseable_event_and_keeps_the_stream_open(
    test_client: TestClient,
    frozen_time: DateTime,
    event1: Event,
    event2: Event,
    stream_publish: mock.AsyncMock,
    caplog: pytest.LogCaptureFixture,
):
    """A single event the server cannot accept must not take the connection --
    and therefore every event sent after it -- down with it.

    Previously the `ValidationError` from `Event.model_validate_json` escaped the
    receive loop and closed the websocket. Clients treat that as a transient
    disconnect, so the refused event was silently lost along with everything the
    client sent before it noticed."""
    websocket: WebSocketTestSession
    with (
        caplog.at_level(logging.WARNING, logger="prefect.server.api.events"),
        test_client.websocket_connect(
            "/api/events/in", subprotocols=["prefect"]
        ) as websocket,
    ):
        websocket.send_json({"type": "auth", "token": None})
        assert websocket.receive_json()["type"] == "auth_success"

        websocket.send_text(event1.model_dump_json())
        # `event` is a required field, so this cannot be validated into an Event.
        websocket.send_text(json.dumps({"resource": {"prefect.resource.id": "x"}}))
        websocket.send_text(event2.model_dump_json())

    # The two good events either side of it still arrived.
    stream_publish.assert_has_awaits(
        [
            mock.call(event1.receive(received=frozen_time)),
            mock.call(event2.receive(received=frozen_time)),
        ]
    )
    assert stream_publish.await_count == 2

    # And the server said something about the one it dropped.
    assert any(
        "could not be validated" in record.message for record in caplog.records
    ), "dropping an unparseable event should be logged"


def test_stream_events_in_drops_an_oversized_event_and_keeps_the_stream_open(
    test_client: TestClient,
    frozen_time: DateTime,
    event1: Event,
    event2: Event,
    stream_publish: mock.AsyncMock,
):
    """The case from the original report: an event carrying more related resources
    than the server permits. It is refused, and the stream survives it."""
    maximum = PREFECT_SERVER_EVENTS_MAXIMUM_RELATED_RESOURCES.value()
    oversized = event1.model_copy(
        update={
            "id": uuid4(),
            "related": [
                RelatedResource.model_validate(
                    {
                        "prefect.resource.id": f"related.{index}",
                        "prefect.resource.role": "related",
                    }
                )
                for index in range(maximum + 1)
            ],
        }
    )

    websocket: WebSocketTestSession
    with test_client.websocket_connect(
        "/api/events/in", subprotocols=["prefect"]
    ) as websocket:
        websocket.send_json({"type": "auth", "token": None})
        assert websocket.receive_json()["type"] == "auth_success"

        websocket.send_text(event1.model_dump_json())
        websocket.send_text(oversized.model_dump_json(warnings=False))
        websocket.send_text(event2.model_dump_json())

    stream_publish.assert_has_awaits(
        [
            mock.call(event1.receive(received=frozen_time)),
            mock.call(event2.receive(received=frozen_time)),
        ]
    )
    assert stream_publish.await_count == 2


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
