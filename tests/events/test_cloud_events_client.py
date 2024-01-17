from unittest import mock

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


async def test_handles_api_url_with_trailing_slash(
    events_api_url: str, example_event_1: Event, recorder: Recorder
):
    # Regression test for https://github.com/PrefectHQ/prefect/issues/9662
    # where a configuration that has a trailing slash on the PREFECT_API_URL
    # would cause the client to fail to connect with a 403 as the path would
    # contain a double slash, ie: `wss:api.prefect.cloud/...//events/in`

    events_api_url += "/"
    async with PrefectCloudEventsClient(events_api_url, "my-token") as client:
        await client.emit(example_event_1)

    assert recorder.connections == 1
    assert recorder.path == "/accounts/A/workspaces/W/events/in"
    assert recorder.events == [example_event_1]


async def test_recovers_from_temporary_error_reconnecting(
    events_api_url: str,
    example_event_1: Event,
    example_event_2: Event,
    example_event_3: Event,
    recorder: Recorder,
    puppeteer: Puppeteer,
):
    """Regression test for an error where the client encountered assertion errors in
    PrefectCloudEventsClient._emit because the websocket was None"""
    client = PrefectCloudEventsClient(
        events_api_url, "my-token", checkpoint_every=1, reconnection_attempts=3
    )
    async with client:
        assert recorder.connections == 1

        puppeteer.hard_disconnect_after = example_event_1.id
        await client.emit(example_event_1)

        # Emulate an error happening during reconnection that may leave the websocket
        # as None.  This may not be the exact cause of the trouble, but it emulates the
        # same condition the client saw
        assert client._connect is not None
        with mock.patch.object(
            client._connect, "__aexit__", side_effect=ValueError("newp")
        ):
            with pytest.raises(ValueError, match="newp"):
                await client.emit(example_event_2)

        assert recorder.connections == 1

        # The condition we're testing for is that the client can recover from the
        # websocket being None, so make sure that we've created that condition here
        assert not client._websocket

        # We're not going to make the server refuse connections, so we should expect the
        # client to automatically reconnect and continue emitting events

        await client.emit(example_event_3)

    assert recorder.connections == 1 + 1  # initial, reconnect
    assert recorder.events == [
        example_event_1,
        example_event_2,
        example_event_3,
    ]


async def test_recovers_from_long_lasting_error_reconnecting(
    events_api_url: str,
    example_event_1: Event,
    example_event_2: Event,
    example_event_3: Event,
    recorder: Recorder,
    puppeteer: Puppeteer,
):
    """Regression test for an error where the client encountered assertion errors in
    PrefectCloudEventsClient._emit because the websocket was None"""
    client = PrefectCloudEventsClient(
        events_api_url, "my-token", checkpoint_every=1, reconnection_attempts=3
    )
    async with client:
        assert recorder.connections == 1

        puppeteer.hard_disconnect_after = example_event_1.id
        await client.emit(example_event_1)

        # Emulate an error happening during reconnection that may leave the websocket
        # as None.  This may not be the exact cause of the trouble, but it emulates the
        # same condition the client saw
        assert client._connect is not None
        with mock.patch.object(
            client._connect, "__aexit__", side_effect=ValueError("newp")
        ):
            with pytest.raises(ValueError, match="newp"):
                await client.emit(example_event_2)

        assert recorder.connections == 1

        # The condition we're testing for is that the client can recover from the
        # websocket being None, so make sure that we've created that condition here
        assert not client._websocket

        # This is what makes it "long-lasting", that the server will start refusing any
        # further connections, so we should expect up to N attempts to reconnect before
        # raising the underlying error
        puppeteer.refuse_any_further_connections = True
        with pytest.raises(ConnectionClosed):
            await client.emit(example_event_3)

    assert recorder.connections == 1 + 1 + 3  # initial, reconnect, three more attempts
    assert recorder.events == [
        example_event_1,
        # event 2 never made it because we cause that error during reconnection
        # event 3 never made it because we told the server to refuse future connects
    ]
