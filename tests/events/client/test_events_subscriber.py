from typing import Optional, Type

import pytest
from websockets.exceptions import ConnectionClosedError

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
    PREFECT_EXPERIMENTAL_EVENTS,
    temporary_settings,
)
from prefect.testing.fixtures import Puppeteer, Recorder


@pytest.fixture
def no_viable_settings():
    with temporary_settings(
        {
            PREFECT_API_URL: "https://locally/api",
            PREFECT_CLOUD_API_URL: "https://cloudy/api",
            PREFECT_EXPERIMENTAL_EVENTS: False,
        }
    ):
        yield


async def test_raises_when_no_viable_client(no_viable_settings):
    with pytest.raises(RuntimeError, match="does not support events"):
        get_events_subscriber()


@pytest.fixture
def server_settings():
    with temporary_settings(
        {
            PREFECT_API_URL: "https://locally/api",
            PREFECT_CLOUD_API_URL: "https://cloudy/api",
            PREFECT_EXPERIMENTAL_EVENTS: True,
        }
    ):
        yield


async def test_constructs_server_client(server_settings):
    assert isinstance(get_events_subscriber(), PrefectEventSubscriber)


@pytest.fixture
def cloud_settings():
    with temporary_settings(
        {
            PREFECT_API_URL: "https://cloudy/api/accounts/1/workspaces/2",
            PREFECT_CLOUD_API_URL: "https://cloudy/api",
            PREFECT_API_KEY: "howdy-doody",
            PREFECT_EXPERIMENTAL_EVENTS: False,
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
