import pytest
from websockets.exceptions import ConnectionClosed

from prefect.events import Event
from prefect.events.clients import PrefectCloudEventsClient
from prefect.testing.fixtures import Puppeteer, Recorder


async def test_cloud_client_can_connect_and_emit(
    events_api_url: str, example_event_1: Event, recorder: Recorder
):
    async with PrefectCloudEventsClient(events_api_url, "my-token") as client:
        await client.emit(example_event_1)

    assert recorder.connections == 1
    assert recorder.path == "/accounts/A/workspaces/W/events/in"
    assert recorder.events == [example_event_1]


async def test_reconnects_and_resends_after_hard_disconnect(
    events_api_url: str,
    example_event_1: Event,
    example_event_2: Event,
    example_event_3: Event,
    example_event_4: Event,
    example_event_5: Event,
    recorder: Recorder,
    puppeteer: Puppeteer,
):
    client = PrefectCloudEventsClient(events_api_url, "my-token", checkpoint_every=1)
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
    events_api_url: str,
    example_event_1: Event,
    example_event_2: Event,
    example_event_3: Event,
    recorder: Recorder,
    puppeteer: Puppeteer,
    attempts: int,
):
    client = PrefectCloudEventsClient(
        events_api_url, "my-token", checkpoint_every=1, reconnection_attempts=attempts
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
    events_api_url: str,
    example_event_1: Event,
    example_event_2: Event,
    example_event_3: Event,
    recorder: Recorder,
    puppeteer: Puppeteer,
):
    """This is a nonsensical configuration, but covers a branch of client.emit where
    the primary reconnection loop does nothing (not even sending events)"""
    client = PrefectCloudEventsClient(
        events_api_url, "my-token", checkpoint_every=1, reconnection_attempts=-1
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
