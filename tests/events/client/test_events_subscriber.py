from typing import Type

import pytest
from websockets.exceptions import ConnectionClosedError

from prefect.events import Event, get_events_subscriber
from prefect.events.clients import PrefectCloudEventSubscriber, PrefectEventSubscriber
from prefect.events.filters import EventFilter, EventNameFilter
from prefect.settings import (
    PREFECT_API_KEY,
    PREFECT_API_URL,
    PREFECT_CLOUD_API_URL,
    temporary_settings,
)
from prefect.testing.fixtures import Puppeteer, Recorder


def test_constructs_server_subscriber():
    with temporary_settings(
        {
            PREFECT_API_URL: "https://locally/api",
            PREFECT_CLOUD_API_URL: "https://cloudy/api",
        }
    ):
        assert isinstance(get_events_subscriber(), PrefectEventSubscriber)


def test_constructs_cloud_subscriber():
    with temporary_settings(
        {
            PREFECT_API_URL: "https://cloudy/api/accounts/1/workspaces/2",
            PREFECT_CLOUD_API_URL: "https://cloudy/api",
            PREFECT_API_KEY: "howdy-doody",
        }
    ):
        assert isinstance(get_events_subscriber(), PrefectCloudEventSubscriber)


def pytest_generate_tests(metafunc: pytest.Metafunc):
    fixtures = set(metafunc.fixturenames)

    if "Subscriber" in fixtures:
        metafunc.parametrize(
            "Subscriber",
            [PrefectEventSubscriber, PrefectCloudEventSubscriber],
        )


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
    events_cloud_api_url: str,
    example_event_1: Event,
    example_event_2: Event,
    recorder: Recorder,
    puppeteer: Puppeteer,
):
    puppeteer.token = "my-token" if Subscriber == PrefectCloudEventSubscriber else None
    puppeteer.outgoing_events = [example_event_1, example_event_2]

    async with Subscriber() as subscriber:
        async for event in subscriber:
            recorder.events.append(event)

    assert recorder.connections == 1
    assert recorder.path == "/accounts/A/workspaces/W/events/out"
    assert recorder.events == [example_event_1, example_event_2]
    assert recorder.token == puppeteer.token
    assert subscriber._filter
    assert recorder.filter == subscriber._filter


async def test_cloud_subscriber_complains_without_api_url_and_key(
    events_cloud_api_url: str,
    example_event_1: Event,
    example_event_2: Event,
    recorder: Recorder,
    puppeteer: Puppeteer,
):
    with temporary_settings(updates={PREFECT_API_KEY: "", PREFECT_API_URL: ""}):
        with pytest.raises(ValueError, match="must be provided or set"):
            PrefectCloudEventSubscriber()


async def test_subscriber_can_connect_and_receive_one_event(
    Subscriber: Type[PrefectEventSubscriber],
    events_cloud_api_url: str,
    example_event_1: Event,
    example_event_2: Event,
    recorder: Recorder,
    puppeteer: Puppeteer,
):
    puppeteer.token = "my-token" if Subscriber == PrefectCloudEventSubscriber else None
    puppeteer.outgoing_events = [example_event_1, example_event_2]

    filter = EventFilter(event=EventNameFilter(name=["example.event"]))

    async with Subscriber(
        filter=filter,
        reconnection_attempts=0,
    ) as subscriber:
        async for event in subscriber:
            recorder.events.append(event)

    assert recorder.connections == 1
    assert recorder.path == "/accounts/A/workspaces/W/events/out"
    assert recorder.events == [example_event_1, example_event_2]
    assert recorder.token == puppeteer.token
    assert recorder.filter == filter


async def test_subscriber_specifying_negative_reconnects_gets_error(
    Subscriber: Type[PrefectEventSubscriber],
    events_cloud_api_url: str,
    example_event_1: Event,
    example_event_2: Event,
    recorder: Recorder,
    puppeteer: Puppeteer,
):
    puppeteer.token = "my-token" if Subscriber == PrefectCloudEventSubscriber else None
    puppeteer.outgoing_events = [example_event_1, example_event_2]

    filter = EventFilter(event=EventNameFilter(name=["example.event"]))

    with pytest.raises(ValueError, match="non-negative"):
        Subscriber(
            filter=filter,
            reconnection_attempts=-1,
        )

    assert recorder.connections == 0


async def test_subscriber_raises_on_invalid_auth_with_soft_denial(
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
        subscriber = PrefectCloudEventSubscriber(
            events_cloud_api_url,
            "bogus",
            filter=filter,
            reconnection_attempts=0,
        )
        await subscriber.__aenter__()

    assert recorder.connections == 1
    assert recorder.path == "/accounts/A/workspaces/W/events/out"
    assert recorder.token == "bogus"
    assert recorder.events == []


async def test_cloud_subscriber_raises_on_invalid_auth_with_hard_denial(
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
        subscriber = PrefectCloudEventSubscriber(
            events_cloud_api_url,
            "bogus",
            filter=filter,
            reconnection_attempts=0,
        )
        await subscriber.__aenter__()

    assert recorder.connections == 1
    assert recorder.path == "/accounts/A/workspaces/W/events/out"
    assert recorder.token == "bogus"
    assert recorder.events == []


async def test_subscriber_reconnects_on_hard_disconnects(
    Subscriber: Type[PrefectEventSubscriber],
    example_event_1: Event,
    example_event_2: Event,
    recorder: Recorder,
    puppeteer: Puppeteer,
):
    puppeteer.token = "my-token" if Subscriber == PrefectCloudEventSubscriber else None
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
    example_event_1: Event,
    example_event_2: Event,
    recorder: Recorder,
    puppeteer: Puppeteer,
):
    puppeteer.token = "my-token" if Subscriber == PrefectCloudEventSubscriber else None
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
    example_event_1: Event,
    example_event_2: Event,
    recorder: Recorder,
    puppeteer: Puppeteer,
):
    puppeteer.token = "my-token" if Subscriber == PrefectCloudEventSubscriber else None
    puppeteer.outgoing_events = [example_event_1, example_event_1, example_event_2]

    filter = EventFilter(event=EventNameFilter(name=["example.event"]))

    async with Subscriber(
        filter=filter,
    ) as subscriber:
        async for event in subscriber:
            recorder.events.append(event)

    assert recorder.events == [example_event_1, example_event_2]
