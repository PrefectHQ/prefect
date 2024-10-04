import asyncio
import json
import os
import socket
import sys
from contextlib import contextmanager
from typing import AsyncGenerator, Generator, List, Optional, Union
from unittest import mock
from uuid import UUID

import anyio
import httpx
import pendulum
import pytest
from starlette.status import WS_1008_POLICY_VIOLATION
from websockets.exceptions import ConnectionClosed
from websockets.legacy.server import WebSocketServer, WebSocketServerProtocol, serve

from prefect.events import Event
from prefect.events.clients import (
    AssertingEventsClient,
    AssertingPassthroughEventsClient,
)
from prefect.events.filters import EventFilter
from prefect.events.worker import EventsWorker
from prefect.server.api.server import SubprocessASGIServer
from prefect.server.events.pipeline import EventsPipeline
from prefect.settings import (
    PREFECT_API_URL,
    PREFECT_SERVER_ALLOW_EPHEMERAL_MODE,
    PREFECT_SERVER_CSRF_PROTECTION_ENABLED,
    get_current_settings,
    temporary_settings,
)
from prefect.testing.utilities import AsyncMock
from prefect.utilities.asyncutils import sync_compatible
from prefect.utilities.processutils import open_process


@pytest.fixture(autouse=True)
def add_prefect_loggers_to_caplog(caplog):
    import logging

    logger = logging.getLogger("prefect")
    logger.propagate = True

    try:
        yield
    finally:
        logger.propagate = False


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


@pytest.fixture(scope="session")
async def hosted_api_server(unused_tcp_port_factory):
    """
    Runs an instance of the Prefect API server in a subprocess instead of the using the
    ephemeral application.

    Uses the same database as the rest of the tests.

    Yields:
        The API URL
    """
    port = unused_tcp_port_factory()
    print(f"Running hosted API server on port {port}")

    # Will connect to the same database as normal test clients
    settings = get_current_settings().to_environment_variables(exclude_unset=True)
    async with open_process(
        command=[
            "uvicorn",
            "--factory",
            "prefect.server.api.server:create_app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "info",
        ],
        stdout=sys.stdout,
        stderr=sys.stderr,
        env={
            **os.environ,
            **settings,
        },
    ) as process:
        api_url = f"http://localhost:{port}/api"

        # Wait for the server to be ready
        async with httpx.AsyncClient() as client:
            response = None
            with anyio.move_on_after(20):
                while True:
                    try:
                        response = await client.get(api_url + "/health")
                    except httpx.ConnectError:
                        pass
                    else:
                        if response.status_code == 200:
                            break
                    await anyio.sleep(0.1)
            if response:
                response.raise_for_status()
            if not response:
                raise RuntimeError(
                    "Timed out while attempting to connect to hosted test Prefect API."
                )

        # Yield to the consuming tests
        yield api_url

        # Then shutdown the process
        try:
            process.terminate()

            # Give the process a 10 second grace period to shutdown
            for _ in range(10):
                if process.returncode is not None:
                    break
                await anyio.sleep(1)
            else:
                # Kill the process if it is not shutdown in time
                process.kill()

        except ProcessLookupError:
            pass


@pytest.fixture(autouse=True)
def use_hosted_api_server(hosted_api_server):
    """
    Sets `PREFECT_API_URL` to the test session's hosted API endpoint.
    """
    with temporary_settings(
        {
            PREFECT_API_URL: hosted_api_server,
            PREFECT_SERVER_CSRF_PROTECTION_ENABLED: False,
        }
    ):
        yield hosted_api_server


@pytest.fixture
def disable_hosted_api_server():
    """
    Disables the hosted API server by setting `PREFECT_API_URL` to `None`.
    """
    with temporary_settings(
        {
            PREFECT_API_URL: None,
        }
    ):
        yield hosted_api_server


@pytest.fixture
def enable_ephemeral_server(disable_hosted_api_server):
    """
    Enables the ephemeral server by setting `PREFECT_SERVER_ALLOW_EPHEMERAL_MODE` to `True`.
    """
    with temporary_settings(
        {
            PREFECT_SERVER_ALLOW_EPHEMERAL_MODE: True,
        }
    ):
        yield hosted_api_server

    SubprocessASGIServer().stop()


@pytest.fixture
def mock_anyio_sleep(monkeypatch):
    """
    Mock sleep used to not actually sleep but to set the current time to now + sleep
    delay seconds while still yielding to other tasks in the event loop.

    Provides "assert_sleeps_for" context manager which asserts a sleep time occurred
    within the context while using the actual runtime of the context as a tolerance.
    """
    original_now = pendulum.now
    original_sleep = anyio.sleep
    time_shift = 0.0

    async def callback(delay_in_seconds):
        nonlocal time_shift
        time_shift += float(delay_in_seconds)
        # Preserve yield effects of sleep
        await original_sleep(0)

    def latest_now(*args):
        # Fast-forwards the time by the total sleep time
        return original_now(*args).add(
            # Ensure we retain float precision
            seconds=int(time_shift),
            microseconds=(time_shift - int(time_shift)) * 1000000,
        )

    monkeypatch.setattr("pendulum.now", latest_now)

    sleep = AsyncMock(side_effect=callback)
    monkeypatch.setattr("anyio.sleep", sleep)

    @contextmanager
    def assert_sleeps_for(
        seconds: Union[int, float], extra_tolerance: Union[int, float] = 0
    ):
        """
        Assert that sleep was called for N seconds during the duration of the context.
        The runtime of the code during the context of the duration is used as an
        upper tolerance to account for sleeps that start based on a time. This is less
        brittle than attempting to freeze the current time.

        If an integer is provided, the upper tolerance will be rounded up to the nearest
        integer. If a float is provided, the upper tolerance will be a float.

        An optional extra tolerance may be provided to account for any other issues.
        This will be applied symmetrically.
        """
        run_t0 = original_now().timestamp()
        sleep_t0 = time_shift
        yield
        run_t1 = original_now().timestamp()
        sleep_t1 = time_shift
        runtime = run_t1 - run_t0
        if isinstance(seconds, int):
            # Round tolerance up to the nearest integer if input is an int
            runtime = int(runtime) + 1
        sleeptime = sleep_t1 - sleep_t0
        assert (
            sleeptime - float(extra_tolerance)
            <= seconds
            <= sleeptime + runtime + extra_tolerance
        ), (
            f"Sleep was called for {sleeptime}; expected {seconds} with tolerance of"
            f" +{runtime + extra_tolerance}, -{extra_tolerance}"
        )

    sleep.assert_sleeps_for = assert_sleeps_for

    return sleep


class Recorder:
    connections: int
    path: Optional[str]
    events: List[Event]
    token: Optional[str]
    filter: Optional[EventFilter]

    def __init__(self):
        self.connections = 0
        self.path = None
        self.events = []


class Puppeteer:
    token: Optional[str]

    hard_auth_failure: bool
    refuse_any_further_connections: bool
    hard_disconnect_after: Optional[UUID]

    outgoing_events: List[Event]

    def __init__(self):
        self.hard_auth_failure = False
        self.refuse_any_further_connections = False
        self.hard_disconnect_after = None
        self.outgoing_events = []


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

    async def handler(socket: WebSocketServerProtocol) -> None:
        path = socket.path
        recorder.connections += 1
        if puppeteer.refuse_any_further_connections:
            raise ValueError("nope")

        recorder.path = path

        if path.endswith("/events/in"):
            await incoming_events(socket)
        elif path.endswith("/events/out"):
            await outgoing_events(socket)

    async def incoming_events(socket: WebSocketServerProtocol):
        while True:
            try:
                message = await socket.recv()
            except ConnectionClosed:
                return

            event = Event.model_validate_json(message)
            recorder.events.append(event)

            if puppeteer.hard_disconnect_after == event.id:
                raise ValueError("zonk")

    async def outgoing_events(socket: WebSocketServerProtocol):
        # 1. authentication
        auth_message = json.loads(await socket.recv())

        assert auth_message["type"] == "auth"
        recorder.token = auth_message["token"]
        if puppeteer.token != recorder.token:
            if not puppeteer.hard_auth_failure:
                await socket.send(
                    json.dumps({"type": "auth_failure", "reason": "nope"})
                )
            await socket.close(WS_1008_POLICY_VIOLATION)
            return

        await socket.send(json.dumps({"type": "auth_success"}))

        # 2. filter
        filter_message = json.loads(await socket.recv())
        assert filter_message["type"] == "filter"
        recorder.filter = EventFilter.model_validate(filter_message["filter"])

        # 3. send events
        for event in puppeteer.outgoing_events:
            await socket.send(
                json.dumps(
                    {
                        "type": "event",
                        "event": event.model_dump(mode="json"),
                    }
                )
            )
            if puppeteer.hard_disconnect_after == event.id:
                puppeteer.hard_disconnect_after = None
                raise ValueError("zonk")

    async with serve(handler, host="localhost", port=unused_tcp_port) as server:
        yield server


@pytest.fixture
def events_api_url(events_server: WebSocketServer, unused_tcp_port: int) -> str:
    return f"http://localhost:{unused_tcp_port}"


@pytest.fixture
def events_cloud_api_url(events_server: WebSocketServer, unused_tcp_port: int) -> str:
    return f"http://localhost:{unused_tcp_port}/accounts/A/workspaces/W"


@pytest.fixture
def mock_should_emit_events(monkeypatch) -> mock.Mock:
    m = mock.Mock()
    m.return_value = True
    monkeypatch.setattr("prefect.events.utilities.should_emit_events", m)
    return m


@pytest.fixture
def asserting_events_worker(monkeypatch) -> Generator[EventsWorker, None, None]:
    worker = EventsWorker.instance(AssertingEventsClient)
    # Always yield the asserting worker when new instances are retrieved
    monkeypatch.setattr(EventsWorker, "instance", lambda *_: worker)
    try:
        yield worker
    finally:
        worker.drain()


@pytest.fixture
def asserting_and_emitting_events_worker(
    monkeypatch,
) -> Generator[EventsWorker, None, None]:
    worker = EventsWorker.instance(AssertingPassthroughEventsClient)
    # Always yield the asserting worker when new instances are retrieved
    monkeypatch.setattr(EventsWorker, "instance", lambda *_: worker)
    try:
        yield worker
    finally:
        worker.drain()


@pytest.fixture
async def events_pipeline(asserting_events_worker: EventsWorker):
    class AssertingEventsPipeline(EventsPipeline):
        @sync_compatible
        async def process_events(
            self,
            dequeue_events: bool = True,
            min_events: int = 0,
            timeout: int = 10,
        ):
            async def wait_for_min_events():
                while len(asserting_events_worker._client.events) < min_events:
                    await asyncio.sleep(0.1)

            if min_events:
                try:
                    await asyncio.wait_for(wait_for_min_events(), timeout=timeout)
                except TimeoutError:
                    raise TimeoutError(
                        f"Timed out waiting for {min_events} events after {timeout} seconds. Only observed {len(asserting_events_worker._client.events)} events."
                    )
            else:
                asserting_events_worker.wait_until_empty()

            if dequeue_events:
                events = asserting_events_worker._client.pop_events()
            else:
                events = asserting_events_worker._client.events

            messages = self.events_to_messages(events)
            await self.process_messages(messages)

    yield AssertingEventsPipeline()


@pytest.fixture
async def emitting_events_pipeline(asserting_and_emitting_events_worker: EventsWorker):
    class AssertingAndEmittingEventsPipeline(EventsPipeline):
        @sync_compatible
        async def process_events(self):
            asserting_and_emitting_events_worker.wait_until_empty()
            events = asserting_and_emitting_events_worker._client.pop_events()

            messages = self.events_to_messages(events)
            await self.process_messages(messages)

    yield AssertingAndEmittingEventsPipeline()


@pytest.fixture
def reset_worker_events(asserting_events_worker: EventsWorker):
    yield
    assert isinstance(asserting_events_worker._client, AssertingEventsClient)
    asserting_events_worker._client.events = []
