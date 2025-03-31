import datetime
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, AsyncIterable

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.status import (
    WS_1002_PROTOCOL_ERROR,
    WS_1008_POLICY_VIOLATION,
)
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from prefect.server.events.filters import (
    EventFilter,
    EventOccurredFilter,
    EventOrder,
)
from prefect.server.events.schemas.events import ReceivedEvent
from prefect.server.events.storage import database
from prefect.types._datetime import DateTime, now


@pytest.fixture
def stream_mock(
    monkeypatch: pytest.MonkeyPatch,
    received_event1: ReceivedEvent,
    received_event2: ReceivedEvent,
):
    @asynccontextmanager
    async def mock_stream(
        filter: EventFilter,
    ) -> AsyncGenerator[AsyncIterable[ReceivedEvent], None]:
        assert isinstance(filter, EventFilter)

        async def _fake_stream() -> AsyncGenerator[ReceivedEvent, None]:
            yield received_event1
            yield received_event2

        yield _fake_stream()

    monkeypatch.setattr("prefect.server.api.events.stream.events", mock_stream)


@pytest.fixture
def backfill_mock(
    monkeypatch: pytest.MonkeyPatch,
    old_event1: ReceivedEvent,
    old_event2: ReceivedEvent,
    received_event1: ReceivedEvent,
):
    async def mock_query_events(
        *,
        session: None = None,
        filter: EventFilter,
        page_size: int = 0,
    ) -> tuple[list[ReceivedEvent], Any, Any]:
        assert isinstance(session, AsyncSession)

        assert isinstance(filter, EventFilter)

        assert page_size > 0

        assert filter.order == EventOrder.ASC

        return [old_event1, old_event2, received_event1], 3, None

    monkeypatch.setattr(
        database,
        "query_events",
        mock_query_events,
    )


@pytest.fixture
def default_liberal_filter() -> EventFilter:
    return EventFilter(
        occurred=EventOccurredFilter(
            since=now("UTC"),
            until=now("UTC") + datetime.timedelta(days=365),
        )
    )


def test_streaming_requires_prefect_subprotocol(
    test_client: TestClient,
    default_liberal_filter: EventFilter,
):
    with pytest.raises(WebSocketDisconnect) as exception:
        with test_client.websocket_connect("api/events/out", subprotocols=[]):
            pass

    assert exception.value.code == WS_1002_PROTOCOL_ERROR


def test_streaming_requires_authentication(
    test_client: TestClient,
    default_liberal_filter: EventFilter,
):
    with pytest.raises(WebSocketDisconnect) as exception:
        with test_client.websocket_connect(
            "api/events/out", subprotocols=["prefect"]
        ) as websocket:
            # The first message must be an auth message, otherwise the server
            # will disconnect the websocket.
            message = {
                "type": "filter",
                "filter": default_liberal_filter.model_dump(mode="json"),
            }
            websocket.send_json(message)
            websocket.receive_json()

    assert exception.value.code == WS_1008_POLICY_VIOLATION
    assert exception.value.reason == "Expected 'auth' message"


async def test_streaming_requires_a_filter(
    monkeypatch: pytest.MonkeyPatch,
    frozen_time: DateTime,
    test_client: TestClient,
    default_liberal_filter: EventFilter,
    old_event1: ReceivedEvent,
    old_event2: ReceivedEvent,
    received_event1: ReceivedEvent,
    received_event2: ReceivedEvent,
    backfill_mock: None,
    stream_mock: None,
):
    with pytest.raises(WebSocketDisconnect) as exception:
        with test_client.websocket_connect(
            "api/events/out",
            subprotocols=["prefect"],
        ) as websocket:
            auth_message = {
                "type": "auth",
                "token": "my-token",
            }
            websocket.send_json(auth_message)
            message = websocket.receive_json()  # Auth success response
            assert message["type"] == "auth_success"

            filter_message = {
                "type": "what?",
                "filter": default_liberal_filter.model_dump(mode="json"),
            }
            websocket.send_json(filter_message)

            websocket.receive_json()  # will prompt the server-side disconnection

    assert exception.value.code == WS_1002_PROTOCOL_ERROR
    assert exception.value.reason == "Expected 'filter' message"


async def test_streaming_requires_a_valid_filter(
    monkeypatch: pytest.MonkeyPatch,
    frozen_time: DateTime,
    test_client: TestClient,
    default_liberal_filter: EventFilter,
    old_event1: ReceivedEvent,
    old_event2: ReceivedEvent,
    received_event1: ReceivedEvent,
    received_event2: ReceivedEvent,
    backfill_mock: None,
    stream_mock: None,
):
    with pytest.raises(WebSocketDisconnect) as exception:
        with test_client.websocket_connect(
            "api/events/out",
            subprotocols=["prefect"],
        ) as websocket:
            auth_message = {
                "type": "auth",
                "token": "my-token",
            }
            websocket.send_json(auth_message)
            message = websocket.receive_json()  # Auth success response
            assert message["type"] == "auth_success"

            filter_message = {"type": "filter", "filter": "jankystank"}
            websocket.send_json(filter_message)

            websocket.receive_json()  # will prompt the server-side disconnection

    assert exception.value.code == WS_1002_PROTOCOL_ERROR
    assert exception.value.reason.startswith("Invalid filter: 1 validation error")


async def test_user_may_decline_a_backfill(
    monkeypatch: pytest.MonkeyPatch,
    frozen_time: DateTime,
    test_client: TestClient,
    default_liberal_filter: EventFilter,
    old_event1: ReceivedEvent,
    old_event2: ReceivedEvent,
    received_event1: ReceivedEvent,
    received_event2: ReceivedEvent,
    backfill_mock: None,
    stream_mock: None,
):
    with test_client.websocket_connect(
        "api/events/out",
        subprotocols=["prefect"],
    ) as websocket:
        auth_message = {
            "type": "auth",
            "token": "my-token",
        }
        websocket.send_json(auth_message)
        message = websocket.receive_json()  # Auth success response
        assert message["type"] == "auth_success"

        filter_message = {
            "type": "filter",
            "filter": default_liberal_filter.model_dump(mode="json"),
            "backfill": False,
        }
        websocket.send_json(filter_message)

        event_message = websocket.receive_json()
        assert event_message["type"] == "event"
        assert ReceivedEvent.model_validate(event_message["event"]) == received_event1

        event_message = websocket.receive_json()
        assert event_message["type"] == "event"
        assert ReceivedEvent.model_validate(event_message["event"]) == received_event2


async def test_user_may_explicitly_request_a_backfill(
    monkeypatch: pytest.MonkeyPatch,
    frozen_time: DateTime,
    test_client: TestClient,
    default_liberal_filter: EventFilter,
    old_event1: ReceivedEvent,
    old_event2: ReceivedEvent,
    received_event1: ReceivedEvent,
    received_event2: ReceivedEvent,
    backfill_mock: None,
    stream_mock: None,
):
    with test_client.websocket_connect(
        "api/events/out",
        subprotocols=["prefect"],
    ) as websocket:
        auth_message = {
            "type": "auth",
            "token": "my-token",
        }
        websocket.send_json(auth_message)
        message = websocket.receive_json()  # Auth success response
        assert message["type"] == "auth_success"

        filter_message = {
            "type": "filter",
            "filter": default_liberal_filter.model_dump(mode="json"),
            "backfill": True,
        }
        websocket.send_json(filter_message)

        event_message = websocket.receive_json()
        assert event_message["type"] == "event"
        assert ReceivedEvent.model_validate(event_message["event"]) == old_event1

        event_message = websocket.receive_json()
        assert event_message["type"] == "event"
        assert ReceivedEvent.model_validate(event_message["event"]) == old_event2

        event_message = websocket.receive_json()
        assert event_message["type"] == "event"
        assert ReceivedEvent.model_validate(event_message["event"]) == received_event1

        event_message = websocket.receive_json()
        assert event_message["type"] == "event"
        assert ReceivedEvent.model_validate(event_message["event"]) == received_event2
