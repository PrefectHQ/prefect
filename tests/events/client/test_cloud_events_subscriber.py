import pytest
from websockets.exceptions import ConnectionClosedError

from prefect.events import Event
from prefect.events.clients import PrefectCloudEventSubscriber
from prefect.events.filters import EventFilter, EventNameFilter
from prefect.settings import PREFECT_API_KEY, PREFECT_API_URL, temporary_settings
from prefect.testing.fixtures import Puppeteer, Recorder


async def test_subscriber_can_connect_with_defaults(
    events_api_url: str,
    example_event_1: Event,
    example_event_2: Event,
    recorder: Recorder,
    puppeteer: Puppeteer,
):
    with temporary_settings(
        updates={PREFECT_API_KEY: "my-token", PREFECT_API_URL: events_api_url}
    ):
        puppeteer.token = "my-token"
        puppeteer.outgoing_events = [example_event_1, example_event_2]

        async with PrefectCloudEventSubscriber() as subscriber:
            async for event in subscriber:
                recorder.events.append(event)

        assert recorder.connections == 1
        assert recorder.path == "/accounts/A/workspaces/W/events/out"
        assert recorder.events == [example_event_1, example_event_2]
        assert recorder.token == "my-token"
        assert subscriber._filter
        assert recorder.filter == subscriber._filter


async def test_subscriber_complains_without_api_url_and_key(
    events_api_url: str,
    example_event_1: Event,
    example_event_2: Event,
    recorder: Recorder,
    puppeteer: Puppeteer,
):
    with temporary_settings(updates={PREFECT_API_KEY: "", PREFECT_API_URL: ""}):
        with pytest.raises(ValueError, match="must be provided or set"):
            PrefectCloudEventSubscriber()


async def test_subscriber_can_connect_and_receive_one_event(
    events_api_url: str,
    example_event_1: Event,
    example_event_2: Event,
    recorder: Recorder,
    puppeteer: Puppeteer,
):
    puppeteer.token = "my-token"
    puppeteer.outgoing_events = [example_event_1, example_event_2]

    filter = EventFilter(event=EventNameFilter(name=["example.event"]))

    async with PrefectCloudEventSubscriber(
        events_api_url,
        "my-token",
        filter,
        reconnection_attempts=0,
    ) as subscriber:
        async for event in subscriber:
            recorder.events.append(event)

    assert recorder.connections == 1
    assert recorder.path == "/accounts/A/workspaces/W/events/out"
    assert recorder.events == [example_event_1, example_event_2]
    assert recorder.token == "my-token"
    assert recorder.filter == filter


async def test_subscriber_raises_on_invalid_auth(
    events_api_url: str,
    example_event_1: Event,
    example_event_2: Event,
    recorder: Recorder,
    puppeteer: Puppeteer,
):
    puppeteer.token = "my-token"
    puppeteer.outgoing_events = [example_event_1, example_event_2]

    filter = EventFilter(event=EventNameFilter(name=["example.event"]))

    with pytest.raises(Exception, match="Unable to authenticate"):
        async with PrefectCloudEventSubscriber(
            events_api_url,
            "bogus",
            filter,
            reconnection_attempts=0,
        ) as subscriber:
            async for event in subscriber:
                recorder.events.append(event)

    assert recorder.connections == 1
    assert recorder.path == "/accounts/A/workspaces/W/events/out"
    assert recorder.token == "bogus"
    assert recorder.events == []


async def test_subscriber_reconnects_on_hard_disconnects(
    events_api_url: str,
    example_event_1: Event,
    example_event_2: Event,
    recorder: Recorder,
    puppeteer: Puppeteer,
):
    puppeteer.token = "my-token"
    puppeteer.outgoing_events = [example_event_1, example_event_2]
    puppeteer.hard_disconnect_after = example_event_1.id

    filter = EventFilter(event=EventNameFilter(name=["example.event"]))

    async with PrefectCloudEventSubscriber(
        events_api_url,
        "my-token",
        filter,
        reconnection_attempts=2,
    ) as subscriber:
        async for event in subscriber:
            recorder.events.append(event)

    assert recorder.connections == 2
    assert recorder.events == [example_event_1, example_event_2]


async def test_subscriber_gives_up_after_so_many_attempts(
    events_api_url: str,
    example_event_1: Event,
    example_event_2: Event,
    recorder: Recorder,
    puppeteer: Puppeteer,
):
    puppeteer.token = "my-token"
    puppeteer.outgoing_events = [example_event_1, example_event_2]
    puppeteer.hard_disconnect_after = example_event_1.id

    filter = EventFilter(event=EventNameFilter(name=["example.event"]))

    with pytest.raises(ConnectionClosedError):
        async with PrefectCloudEventSubscriber(
            events_api_url,
            "my-token",
            filter,
            reconnection_attempts=4,
        ) as subscriber:
            async for event in subscriber:
                puppeteer.refuse_any_further_connections = True
                recorder.events.append(event)

    assert recorder.connections == 1 + 4


async def test_subscriber_skips_duplicate_events(
    events_api_url: str,
    example_event_1: Event,
    example_event_2: Event,
    recorder: Recorder,
    puppeteer: Puppeteer,
):
    puppeteer.token = "my-token"
    puppeteer.outgoing_events = [example_event_1, example_event_1, example_event_2]

    filter = EventFilter(event=EventNameFilter(name=["example.event"]))

    async with PrefectCloudEventSubscriber(
        events_api_url,
        "my-token",
        filter,
    ) as subscriber:
        async for event in subscriber:
            recorder.events.append(event)

    assert recorder.events == [example_event_1, example_event_2]
