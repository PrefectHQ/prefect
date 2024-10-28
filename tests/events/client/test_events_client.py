import logging
from typing import Type
from unittest import mock

import pytest
from websockets.exceptions import ConnectionClosed

from prefect.events import Event, get_events_client
from prefect.events.clients import (
    PrefectCloudEventsClient,
    PrefectEventsClient,
    get_events_subscriber,
)
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


async def test_constructs_client_when_ephemeral_enabled(ephemeral_settings):
    assert isinstance(get_events_client(), PrefectEventsClient)


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
            get_events_client()


@pytest.fixture
def server_settings():
    with temporary_settings(
        {
            PREFECT_API_URL: "https://locally/api",
            PREFECT_API_KEY: None,
            PREFECT_CLOUD_API_URL: "https://cloudy/api",
        }
    ):
        yield


async def test_constructs_server_client(server_settings):
    assert isinstance(get_events_client(), PrefectEventsClient)


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
    assert isinstance(get_events_client(), PrefectCloudEventsClient)


async def test_events_client_can_emit_when_ephemeral_enabled(
    example_event_1: Event, monkeypatch: pytest.MonkeyPatch, ephemeral_settings
):
    assert not PREFECT_API_URL.value()
    assert not PREFECT_API_KEY.value()

    async with get_events_subscriber() as events_subscriber:
        async with get_events_client() as events_client:
            await events_client.emit(example_event_1)

            async for event in events_subscriber:
                assert event == example_event_1
                break


def pytest_generate_tests(metafunc: pytest.Metafunc):
    fixtures = set(metafunc.fixturenames)

    if "Client" in fixtures:
        metafunc.parametrize(
            "Client",
            [PrefectEventsClient, PrefectCloudEventsClient],
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


async def test_events_client_can_connect_and_emit(
    events_api_url: str, example_event_1: Event, recorder: Recorder
):
    async with PrefectEventsClient(events_api_url) as client:
        await client.emit(example_event_1)

    assert recorder.connections == 1
    assert recorder.path == "/events/in"
    assert recorder.events == [example_event_1]


async def test_cloud_client_can_connect_and_emit(
    events_cloud_api_url: str, example_event_1: Event, recorder: Recorder
):
    async with PrefectCloudEventsClient(events_cloud_api_url, "my-token") as client:
        await client.emit(example_event_1)

    assert recorder.connections == 1
    assert recorder.path == "/accounts/A/workspaces/W/events/in"
    assert recorder.events == [example_event_1]


async def test_reconnects_and_resends_after_hard_disconnect(
    Client: Type[PrefectEventsClient],
    example_event_1: Event,
    example_event_2: Event,
    example_event_3: Event,
    example_event_4: Event,
    example_event_5: Event,
    recorder: Recorder,
    puppeteer: Puppeteer,
):
    client = Client(checkpoint_every=1)
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
    Client: Type[PrefectEventsClient],
    example_event_1: Event,
    example_event_2: Event,
    example_event_3: Event,
    recorder: Recorder,
    puppeteer: Puppeteer,
    attempts: int,
):
    client = Client(
        checkpoint_every=1,
        reconnection_attempts=attempts,
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
    Client: Type[PrefectEventsClient],
    example_event_1: Event,
    example_event_2: Event,
    example_event_3: Event,
    recorder: Recorder,
    puppeteer: Puppeteer,
):
    """This is a nonsensical configuration, but covers a branch of client.emit where
    the primary reconnection loop does nothing (not even sending events)"""
    client = Client(checkpoint_every=1, reconnection_attempts=-1)
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
    events_cloud_api_url: str, example_event_1: Event, recorder: Recorder
):
    # Regression test for https://github.com/PrefectHQ/prefect/issues/9662
    # where a configuration that has a trailing slash on the PREFECT_API_URL
    # would cause the client to fail to connect with a 403 as the path would
    # contain a double slash, ie: `wss:api.prefect.cloud/...//events/in`

    events_cloud_api_url += "/"
    async with PrefectEventsClient(events_cloud_api_url) as client:
        await client.emit(example_event_1)

    assert recorder.connections == 1
    assert recorder.path == "/accounts/A/workspaces/W/events/in"
    assert recorder.events == [example_event_1]


async def test_recovers_from_temporary_error_reconnecting(
    Client: Type[PrefectEventsClient],
    example_event_1: Event,
    example_event_2: Event,
    example_event_3: Event,
    recorder: Recorder,
    puppeteer: Puppeteer,
):
    """Regression test for an error where the client encountered assertion errors in
    PrefectEventsClient._emit because the websocket was None"""
    client = Client(checkpoint_every=1, reconnection_attempts=3)
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
    Client: Type[PrefectEventsClient],
    example_event_1: Event,
    example_event_2: Event,
    example_event_3: Event,
    recorder: Recorder,
    puppeteer: Puppeteer,
):
    """Regression test for an error where the client encountered assertion errors in
    PrefectEventsClient._emit because the websocket was None"""
    client = Client(checkpoint_every=1, reconnection_attempts=3)
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


async def test_events_client_warn_if_connect_fails(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    class MockConnect:
        async def __aenter__(self):
            raise Exception("Connection failed")

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    def mock_connect(*args, **kwargs):
        return MockConnect()

    monkeypatch.setattr("prefect.events.clients.connect", mock_connect)

    with caplog.at_level(logging.WARNING):
        with pytest.raises(Exception, match="Connection failed"):
            async with PrefectEventsClient("ws://localhost"):
                pass

    assert any(
        "Unable to connect to 'ws" in record.message for record in caplog.records
    )
