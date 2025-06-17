import datetime
from contextlib import asynccontextmanager
from typing import AsyncGenerator, AsyncIterable
from uuid import uuid4

import pytest
from starlette.status import (
    WS_1002_PROTOCOL_ERROR,
    WS_1008_POLICY_VIOLATION,
)
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from prefect.server.schemas.core import Log
from prefect.server.schemas.filters import LogFilter, LogFilterLevel
from prefect.types._datetime import now


@pytest.fixture
def stream_mock(
    monkeypatch: pytest.MonkeyPatch,
):
    """Mock the logs stream to return test logs"""

    # Create sample logs
    sample_log1 = Log(
        id=uuid4(),
        name="test.logger",
        level=20,
        message="Test message 1",
        timestamp=now("UTC"),
        flow_run_id=uuid4(),
        task_run_id=uuid4(),
    )

    sample_log2 = Log(
        id=uuid4(),
        name="test.logger2",
        level=40,
        message="Test message 2",
        timestamp=now("UTC") + datetime.timedelta(seconds=1),
        flow_run_id=uuid4(),
        task_run_id=None,
    )

    @asynccontextmanager
    async def mock_stream(
        filter: LogFilter,
    ) -> AsyncGenerator[AsyncIterable[Log], None]:
        assert isinstance(filter, LogFilter)

        async def _fake_stream() -> AsyncGenerator[Log, None]:
            yield sample_log1
            yield sample_log2

        yield _fake_stream()

    monkeypatch.setattr("prefect.server.logs.stream.logs", mock_stream)


@pytest.fixture
def default_liberal_filter() -> LogFilter:
    """A filter that should match most logs"""
    return LogFilter(
        level=LogFilterLevel(ge_=1)  # Very low threshold
    )


def test_streaming_requires_prefect_subprotocol(
    test_client: TestClient,
    default_liberal_filter: LogFilter,
):
    """Test that websocket requires prefect subprotocol"""
    with pytest.raises(WebSocketDisconnect) as exception:
        with test_client.websocket_connect("api/logs/out", subprotocols=[]):
            pass

    assert exception.value.code == WS_1002_PROTOCOL_ERROR


def test_streaming_requires_authentication(
    test_client: TestClient,
    default_liberal_filter: LogFilter,
):
    """Test that websocket requires authentication"""
    with pytest.raises(WebSocketDisconnect) as exception:
        with test_client.websocket_connect(
            "api/logs/out", subprotocols=["prefect"]
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
    test_client: TestClient,
    default_liberal_filter: LogFilter,
    stream_mock: None,
):
    """Test that websocket requires a filter message after auth"""
    with pytest.raises(WebSocketDisconnect) as exception:
        with test_client.websocket_connect(
            "api/logs/out",
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
                "type": "what?",  # Wrong type
                "filter": default_liberal_filter.model_dump(mode="json"),
            }
            websocket.send_json(filter_message)

            websocket.receive_json()  # will prompt the server-side disconnection

    assert exception.value.code == WS_1002_PROTOCOL_ERROR
    assert exception.value.reason == "Expected 'filter' message"


async def test_streaming_requires_a_valid_filter(
    monkeypatch: pytest.MonkeyPatch,
    test_client: TestClient,
    default_liberal_filter: LogFilter,
    stream_mock: None,
):
    """Test that websocket requires a valid filter"""
    with pytest.raises(WebSocketDisconnect) as exception:
        with test_client.websocket_connect(
            "api/logs/out",
            subprotocols=["prefect"],
        ) as websocket:
            auth_message = {
                "type": "auth",
                "token": "my-token",
            }
            websocket.send_json(auth_message)
            message = websocket.receive_json()  # Auth success response
            assert message["type"] == "auth_success"

            filter_message = {"type": "filter", "filter": "invalid_filter"}
            websocket.send_json(filter_message)

            websocket.receive_json()  # will prompt the server-side disconnection

    assert exception.value.code == WS_1002_PROTOCOL_ERROR
    assert exception.value.reason.startswith("Invalid filter:")


async def test_successful_log_streaming(
    monkeypatch: pytest.MonkeyPatch,
    test_client: TestClient,
    default_liberal_filter: LogFilter,
    stream_mock: None,
):
    """Test successful log streaming"""
    with test_client.websocket_connect(
        "api/logs/out",
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
        }
        websocket.send_json(filter_message)

        # Should receive the first log
        log_message = websocket.receive_json()
        assert log_message["type"] == "log"
        assert "log" in log_message
        received_log = Log.model_validate(log_message["log"])
        assert received_log.message == "Test message 1"

        # Should receive the second log
        log_message = websocket.receive_json()
        assert log_message["type"] == "log"
        assert "log" in log_message
        received_log = Log.model_validate(log_message["log"])
        assert received_log.message == "Test message 2"
