from typing import Optional, Type

import pytest
from websockets.exceptions import ConnectionClosed, ConnectionClosedError

from prefect.events import Event, get_events_subscriber
from prefect.events.clients import (
    PrefectCloudAccountEventSubscriber,
    PrefectCloudEventSubscriber,
    PrefectEventSubscriber,
)
from prefect.events.filters import EventFilter, EventNameFilter
from prefect.settings import (
    PREFECT_API_KEY,
    PREFECT_API_URL,
    PREFECT_CLOUD_API_URL,
    PREFECT_SERVER_ALLOW_EPHEMERAL_MODE,
    temporary_settings,
)
from prefect.testing.fixtures import Puppeteer, Recorder


@pytest.fixture
def ephemeral_settings():
    with temporary_settings(
        {
            PREFECT_API_URL: None,
            PREFECT_API_KEY: None,
            PREFECT_CLOUD_API_URL: "https://cloudy/api",
            PREFECT_SERVER_ALLOW_EPHEMERAL_MODE: True,
        }
    ):
        yield


@pytest.fixture
def server_settings():
    with temporary_settings(
        {
            PREFECT_API_URL: "https://locally/api",
            PREFECT_CLOUD_API_URL: "https://cloudy/api",
        }
    ):
        yield


async def test_constructs_server_client(server_settings):
    assert isinstance(get_events_subscriber(), PrefectEventSubscriber)


async def test_constructs_client_when_ephemeral_enabled(ephemeral_settings):
    assert isinstance(get_events_subscriber(), PrefectEventSubscriber)


def test_errors_when_missing_api_url_and_ephemeral_disabled():
    with temporary_settings(
        {
            PREFECT_API_URL: None,
            PREFECT_API_KEY: None,
            PREFECT_CLOUD_API_URL: "https://cloudy/api",
            PREFECT_SERVER_ALLOW_EPHEMERAL_MODE: False,
        }
    ):
        with pytest.raises(ValueError, match="PREFECT_API_URL"):
            get_events_subscriber()


@pytest.fixture
def cloud_settings():
    with temporary_settings(
        {
            PREFECT_API_URL: "https://cloudy/api/accounts/1/workspaces/2",
            PREFECT_CLOUD_API_URL: "https://cloudy/api",
            PREFECT_API_KEY: "howdy-doody",
        }
    ):
        yield


async def test_constructs_cloud_client(cloud_settings):
    assert isinstance(get_events_subscriber(), PrefectCloudEventSubscriber)


def pytest_generate_tests(metafunc: pytest.Metafunc):
    fixtures = set(metafunc.fixturenames)

    cloud_subscribers = [
        (
            PrefectCloudEventSubscriber,
            "/accounts/A/workspaces/W/events/out",
            "my-token",
        ),
        (PrefectCloudAccountEventSubscriber, "/accounts/A/events/out", "my-token"),
    ]
    subscribers = [
        # The base subscriber for OSS will just use the API URL, which is set to a
        # Cloud URL here, but it would usually be just /events/out
        (PrefectEventSubscriber, "/accounts/A/workspaces/W/events/out", None),
    ] + cloud_subscribers

    if "Subscriber" in fixtures:
        metafunc.parametrize("Subscriber,socket_path,token", subscribers)
    elif "CloudSubscriber" in fixtures:
        metafunc.parametrize("CloudSubscriber,socket_path,token", cloud_subscribers)


@pytest.fixture(autouse=True)
def api_setup(events_cloud_api_url: str):
    with temporary_settings(
        updates={
            PREFECT_API_URL: events_cloud_api_url,
            PREFECT_API_KEY: "my-token",
        }
    ):
        yield


async def test_subscriber_can_connect_with_defaults(
    Subscriber: Type[PrefectEventSubscriber],
    socket_path: str,
    token: Optional[str],
    example_event_1: Event,
    example_event_2: Event,
    recorder: Recorder,
    puppeteer: Puppeteer,
):
    puppeteer.token = token
    puppeteer.outgoing_events = [example_event_1, example_event_2]

    async with Subscriber() as subscriber:
        async for event in subscriber:
            recorder.events.append(event)

    assert recorder.connections == 1
    assert recorder.path == socket_path
    assert recorder.events == [example_event_1, example_event_2]
    assert recorder.token == puppeteer.token
    assert subscriber._filter
    assert recorder.filter == subscriber._filter


async def test_cloud_subscriber_complains_without_api_url_and_key(
    CloudSubscriber: Type[PrefectCloudEventSubscriber],
    socket_path: str,
    token: Optional[str],
    example_event_1: Event,
    example_event_2: Event,
    recorder: Recorder,
    puppeteer: Puppeteer,
):
    with temporary_settings(updates={PREFECT_API_KEY: "", PREFECT_API_URL: ""}):
        with pytest.raises(ValueError, match="must be provided or set"):
            CloudSubscriber()


async def test_subscriber_can_connect_and_receive_one_event(
    Subscriber: Type[PrefectEventSubscriber],
    socket_path: str,
    token: Optional[str],
    example_event_1: Event,
    example_event_2: Event,
    recorder: Recorder,
    puppeteer: Puppeteer,
):
    puppeteer.token = token
    puppeteer.outgoing_events = [example_event_1, example_event_2]

    filter = EventFilter(event=EventNameFilter(name=["example.event"]))

    async with Subscriber(
        filter=filter,
        reconnection_attempts=0,
    ) as subscriber:
        async for event in subscriber:
            recorder.events.append(event)

    assert recorder.connections == 1
    assert recorder.path == socket_path
    assert recorder.events == [example_event_1, example_event_2]
    assert recorder.token == puppeteer.token
    assert recorder.filter == filter


async def test_subscriber_specifying_negative_reconnects_gets_error(
    Subscriber: Type[PrefectEventSubscriber],
    socket_path: str,
    token: Optional[str],
    example_event_1: Event,
    example_event_2: Event,
    recorder: Recorder,
    puppeteer: Puppeteer,
):
    puppeteer.token = token
    puppeteer.outgoing_events = [example_event_1, example_event_2]

    filter = EventFilter(event=EventNameFilter(name=["example.event"]))

    with pytest.raises(ValueError, match="non-negative"):
        Subscriber(
            filter=filter,
            reconnection_attempts=-1,
        )

    assert recorder.connections == 0


async def test_subscriber_raises_on_invalid_auth_with_soft_denial(
    CloudSubscriber: Type[PrefectCloudEventSubscriber],
    socket_path: str,
    token: Optional[str],
    events_cloud_api_url: str,
    example_event_1: Event,
    example_event_2: Event,
    recorder: Recorder,
    puppeteer: Puppeteer,
):
    puppeteer.token = "my-token"
    puppeteer.outgoing_events = [example_event_1, example_event_2]

    filter = EventFilter(event=EventNameFilter(name=["example.event"]))

    with pytest.raises(Exception, match="Unable to authenticate"):
        subscriber = CloudSubscriber(
            events_cloud_api_url,
            "bogus",
            filter=filter,
            reconnection_attempts=0,
        )
        await subscriber.__aenter__()

    assert recorder.connections == 1
    assert recorder.path == socket_path
    assert recorder.token == "bogus"
    assert recorder.events == []


async def test_cloud_subscriber_raises_on_invalid_auth_with_hard_denial(
    CloudSubscriber: Type[PrefectCloudEventSubscriber],
    socket_path: str,
    token: Optional[str],
    events_cloud_api_url: str,
    example_event_1: Event,
    example_event_2: Event,
    recorder: Recorder,
    puppeteer: Puppeteer,
):
    puppeteer.hard_auth_failure = True
    puppeteer.token = "my-token"
    puppeteer.outgoing_events = [example_event_1, example_event_2]

    filter = EventFilter(event=EventNameFilter(name=["example.event"]))

    with pytest.raises(Exception, match="Unable to authenticate"):
        subscriber = CloudSubscriber(
            events_cloud_api_url,
            "bogus",
            filter=filter,
            reconnection_attempts=0,
        )
        await subscriber.__aenter__()

    assert recorder.connections == 1
    assert recorder.path == socket_path
    assert recorder.token == "bogus"
    assert recorder.events == []


async def test_subscriber_reconnects_on_hard_disconnects(
    Subscriber: Type[PrefectEventSubscriber],
    socket_path: str,
    token: Optional[str],
    example_event_1: Event,
    example_event_2: Event,
    recorder: Recorder,
    puppeteer: Puppeteer,
):
    puppeteer.token = token
    puppeteer.outgoing_events = [example_event_1, example_event_2]
    puppeteer.hard_disconnect_after = example_event_1.id

    filter = EventFilter(event=EventNameFilter(name=["example.event"]))

    async with Subscriber(
        filter=filter,
        reconnection_attempts=2,
    ) as subscriber:
        async for event in subscriber:
            recorder.events.append(event)

    assert recorder.connections == 2
    assert recorder.events == [example_event_1, example_event_2]


async def test_subscriber_gives_up_after_so_many_attempts(
    Subscriber: Type[PrefectEventSubscriber],
    socket_path: str,
    token: Optional[str],
    example_event_1: Event,
    example_event_2: Event,
    recorder: Recorder,
    puppeteer: Puppeteer,
):
    puppeteer.token = token
    puppeteer.outgoing_events = [example_event_1, example_event_2]
    puppeteer.hard_disconnect_after = example_event_1.id

    filter = EventFilter(event=EventNameFilter(name=["example.event"]))

    with pytest.raises(ConnectionClosedError):
        async with Subscriber(
            filter=filter,
            reconnection_attempts=4,
        ) as subscriber:
            async for event in subscriber:
                puppeteer.refuse_any_further_connections = True
                recorder.events.append(event)

    assert recorder.connections == 1 + 4


async def test_subscriber_skips_duplicate_events(
    Subscriber: Type[PrefectEventSubscriber],
    socket_path: str,
    token: Optional[str],
    example_event_1: Event,
    example_event_2: Event,
    recorder: Recorder,
    puppeteer: Puppeteer,
):
    puppeteer.token = token
    puppeteer.outgoing_events = [example_event_1, example_event_1, example_event_2]

    filter = EventFilter(event=EventNameFilter(name=["example.event"]))

    async with Subscriber(filter=filter) as subscriber:
        async for event in subscriber:
            recorder.events.append(event)

    assert recorder.events == [example_event_1, example_event_2]


async def test_subscriber_retries_on_connection_closed_during_initial_connection(
    Subscriber: Type[PrefectEventSubscriber],
    socket_path: str,
    token: Optional[str],
    example_event_1: Event,
    example_event_2: Event,
    recorder: Recorder,
    puppeteer: Puppeteer,
):
    """Test that __aenter__ retries on ConnectionClosed during initial connection."""
    puppeteer.token = token
    puppeteer.outgoing_events = [example_event_1, example_event_2]

    # Start with refusing connections, then allow after first attempt
    puppeteer.refuse_any_further_connections = True

    filter = EventFilter(event=EventNameFilter(name=["example.event"]))

    subscriber = Subscriber(
        filter=filter,
        reconnection_attempts=3,
    )

    # Mock _reconnect to fail twice then succeed
    original_reconnect = subscriber._reconnect
    call_count = 0

    async def mock_reconnect():
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            raise ConnectionClosed(None, None)
        puppeteer.refuse_any_further_connections = False
        return await original_reconnect()

    subscriber._reconnect = mock_reconnect

    async with subscriber:
        async for event in subscriber:
            recorder.events.append(event)

    assert call_count == 3  # Failed twice, succeeded on third attempt
    assert recorder.events == [example_event_1, example_event_2]


async def test_subscriber_retries_on_timeout_error_during_initial_connection(
    Subscriber: Type[PrefectEventSubscriber],
    socket_path: str,
    token: Optional[str],
    example_event_1: Event,
    example_event_2: Event,
    recorder: Recorder,
    puppeteer: Puppeteer,
):
    """Test that __aenter__ retries on TimeoutError during initial connection."""
    puppeteer.token = token
    puppeteer.outgoing_events = [example_event_1, example_event_2]

    filter = EventFilter(event=EventNameFilter(name=["example.event"]))

    subscriber = Subscriber(
        filter=filter,
        reconnection_attempts=3,
    )

    # Mock _reconnect to fail with TimeoutError twice then succeed
    original_reconnect = subscriber._reconnect
    call_count = 0

    async def mock_reconnect():
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            raise TimeoutError("Connection timed out")
        return await original_reconnect()

    subscriber._reconnect = mock_reconnect

    async with subscriber:
        async for event in subscriber:
            recorder.events.append(event)

    assert call_count == 3  # Failed twice, succeeded on third attempt
    assert recorder.events == [example_event_1, example_event_2]


async def test_subscriber_gives_up_after_exhausting_retries_during_initial_connection(
    Subscriber: Type[PrefectEventSubscriber],
    socket_path: str,
    token: Optional[str],
    recorder: Recorder,
    puppeteer: Puppeteer,
):
    """Test that __aenter__ propagates error after exhausting all retry attempts."""
    puppeteer.token = token

    filter = EventFilter(event=EventNameFilter(name=["example.event"]))

    subscriber = Subscriber(
        filter=filter,
        reconnection_attempts=2,
    )

    # Mock _reconnect to always fail
    call_count = 0

    async def mock_reconnect():
        nonlocal call_count
        call_count += 1
        raise ConnectionClosed(None, None)

    subscriber._reconnect = mock_reconnect

    with pytest.raises(ConnectionClosed):
        await subscriber.__aenter__()

    # Should have tried initial attempt + 2 retries = 3 total attempts
    assert call_count == 3


async def test_subscriber_initial_connection_does_not_retry_on_other_exceptions(
    Subscriber: Type[PrefectEventSubscriber],
    socket_path: str,
    token: Optional[str],
    recorder: Recorder,
    puppeteer: Puppeteer,
):
    """Test that __aenter__ does not retry on exceptions other than ConnectionClosed/TimeoutError."""
    puppeteer.token = token

    filter = EventFilter(event=EventNameFilter(name=["example.event"]))

    subscriber = Subscriber(
        filter=filter,
        reconnection_attempts=5,
    )

    # Mock _reconnect to fail with a different exception type
    call_count = 0

    async def mock_reconnect():
        nonlocal call_count
        call_count += 1
        raise ValueError("Configuration error")

    subscriber._reconnect = mock_reconnect

    with pytest.raises(ValueError, match="Configuration error"):
        await subscriber.__aenter__()

    # Should have only tried once since ValueError is not retried
    assert call_count == 1
