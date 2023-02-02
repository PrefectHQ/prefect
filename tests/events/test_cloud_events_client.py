from typing import AsyncGenerator, List, Optional
from uuid import UUID

import pytest
from websockets.exceptions import ConnectionClosed
from websockets.legacy.server import WebSocketServer, WebSocketServerProtocol, serve

from prefect.events import Event
from prefect.events.clients import PrefectCloudEventsClient


class Recorder:
    connections: int
    path: Optional[str]
    events: List[Event]

    def __init__(self):
        self.connections = 0
        self.path = None
        self.events = []


class Puppeteer:
    refuse_any_further_connections: bool
    hard_disconnect_after: Optional[UUID]

    def __init__(self):
        self.refuse_any_further_connections = False
        self.hard_disconnect_after = None


@pytest.fixture
def recorder() -> Recorder:
    return Recorder()


@pytest.fixture
def puppeteer() -> Puppeteer:
    return Puppeteer()


@pytest.fixture
async def events_server(
    unused_tcp_port: int, recorder: Recorder, puppeteer: Puppeteer
) -> AsyncGenerator[WebSocketServer, None]:
    server: WebSocketServer

    async def handler(socket: WebSocketServerProtocol, path: str) -> None:
        recorder.connections += 1
        if puppeteer.refuse_any_further_connections:
            raise ValueError("nope")

        recorder.path = path

        while True:
            try:
                message = await socket.recv()
            except ConnectionClosed:
                return

            event = Event.parse_raw(message)
            recorder.events.append(event)

            if puppeteer.hard_disconnect_after == event.id:
                raise ValueError("zonk")

    async with serve(handler, host="localhost", port=unused_tcp_port) as server:
        yield server


@pytest.fixture
def api_url(events_server: WebSocketServer, unused_tcp_port: int) -> str:
    return f"http://localhost:{unused_tcp_port}/accounts/A/workspaces/W"


async def test_cloud_client_can_connect_and_emit(
    api_url: str, example_event_1: Event, recorder: Recorder
):
    async with PrefectCloudEventsClient(api_url, "my-token") as client:
        await client.emit(example_event_1)

    assert recorder.connections == 1
    assert recorder.path == "/accounts/A/workspaces/W/events/in"
    assert recorder.events == [example_event_1]


async def test_reconnects_and_resends_after_hard_disconnect(
    api_url: str,
    example_event_1: Event,
    example_event_2: Event,
    example_event_3: Event,
    example_event_4: Event,
    example_event_5: Event,
    recorder: Recorder,
    puppeteer: Puppeteer,
):
    client = PrefectCloudEventsClient(api_url, "my-token", checkpoint_every=1)
    async with client:
        assert recorder.connections == 1

        await client.emit(example_event_1)

        puppeteer.hard_disconnect_after = example_event_2.id
        await client.emit(example_event_2)

        await client.emit(example_event_3)
        await client.emit(example_event_4)
        await client.emit(example_event_5)

    assert recorder.connections == 2
    assert recorder.events == [
        example_event_1,
        example_event_2,
        example_event_3,
        example_event_3,  # resent due to the hard disconnect after event 2
        example_event_4,
        example_event_5,
    ]


@pytest.mark.parametrize("attempts", [4, 1, 0])
async def test_gives_up_after_a_certain_amount_of_tries(
    api_url: str,
    example_event_1: Event,
    example_event_2: Event,
    example_event_3: Event,
    recorder: Recorder,
    puppeteer: Puppeteer,
    attempts: int,
):
    client = PrefectCloudEventsClient(
        api_url, "my-token", checkpoint_every=1, reconnection_attempts=attempts
    )
    async with client:
        assert recorder.connections == 1

        await client.emit(example_event_1)

        puppeteer.hard_disconnect_after = example_event_2.id
        puppeteer.refuse_any_further_connections = True
        await client.emit(example_event_2)

        with pytest.raises(ConnectionClosed):
            await client.emit(example_event_3)

    assert recorder.connections == 1 + attempts
    assert recorder.events == [
        example_event_1,
        example_event_2,
    ]


async def test_giving_up_after_negative_one_tries_is_a_noop(
    api_url: str,
    example_event_1: Event,
    example_event_2: Event,
    example_event_3: Event,
    recorder: Recorder,
    puppeteer: Puppeteer,
):
    """This is a nonsensical configuration, but covers a branch of client.emit where
    the primary reconnection loop does nothing (not even sending events)"""
    client = PrefectCloudEventsClient(
        api_url, "my-token", checkpoint_every=1, reconnection_attempts=-1
    )
    async with client:
        assert recorder.connections == 1

        await client.emit(example_event_1)

        puppeteer.hard_disconnect_after = example_event_2.id
        puppeteer.refuse_any_further_connections = True
        await client.emit(example_event_2)

        await client.emit(example_event_3)

    assert recorder.connections == 1
    assert recorder.events == []
