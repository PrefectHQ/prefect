import logging
import ssl
from typing import Type
from uuid import UUID

import pytest
from websockets.exceptions import ConnectionClosedError

from prefect.events import Event, get_events_client
from prefect.events.clients import (
    PrefectCloudEventsClient,
    PrefectEventsClient,
    get_events_subscriber,
)
from prefect.settings import (
    PREFECT_API_AUTH_STRING,
    PREFECT_API_KEY,
    PREFECT_API_TLS_INSECURE_SKIP_VERIFY,
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


def assert_recorded_events_in_order(recorder: Recorder, events: list[Event]):
    seen_ids: set[UUID] = set()
    unique_events: list[Event] = []
    for event in recorder.events:
        if event.id not in seen_ids:
            seen_ids.add(event.id)
            unique_events.append(event)

    assert unique_events == events


@pytest.mark.usefixtures("ephemeral_settings")
async def test_constructs_client_when_ephemeral_enabled():
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


@pytest.mark.usefixtures("ephemeral_settings")
async def test_prefect_api_tls_insecure_skip_verify_setting_set_to_true(
    monkeypatch: pytest.MonkeyPatch,
):
    with temporary_settings(
        updates={
            PREFECT_API_TLS_INSECURE_SKIP_VERIFY: True,
            PREFECT_API_URL: "https://my-self-hosted-thing",
            PREFECT_SERVER_ALLOW_EPHEMERAL_MODE: False,
        }
    ):
        client = get_events_client()

    ssl_ctx = client._connect._kwargs["ssl"]

    # Verify it's an SSL context with the correct insecure settings
    assert isinstance(ssl_ctx, ssl.SSLContext)
    assert ssl_ctx.verify_mode == ssl.CERT_NONE
    assert ssl_ctx.check_hostname is False


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


@pytest.mark.usefixtures("server_settings")
async def test_constructs_server_client():
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


@pytest.mark.usefixtures("cloud_settings")
async def test_constructs_cloud_client():
    assert isinstance(get_events_client(), PrefectCloudEventsClient)


@pytest.mark.usefixtures("ephemeral_settings")
async def test_events_client_can_emit_when_ephemeral_enabled(example_event_1: Event):
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
    assert_recorded_events_in_order(
        recorder,
        [
            example_event_1,
            example_event_2,
            example_event_3,
            example_event_4,
            example_event_5,
        ],
    )


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

        with pytest.raises(ConnectionClosedError):
            await client.emit(example_event_2)
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

        # Set the websocket to None. This may not be the exact situation that
        # the client saw, but it emulates the same condition
        client._websocket = None

        # We're not going to make the server refuse connections, so we should expect the
        # client to automatically reconnect and continue emitting events
        await client.emit(example_event_2)

        assert recorder.connections > 1

        await client.emit(example_event_3)

    assert_recorded_events_in_order(
        recorder,
        [
            example_event_1,
            example_event_2,
            example_event_3,
        ],
    )


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

        # Set the websocket to None. This may not be the exact situation that
        # the client saw, but it emulates the same condition
        client._websocket = None

        # This is what makes it "long-lasting", that the server will start refusing any
        # further connections, so we should expect up to N attempts to reconnect before
        # raising the underlying error
        puppeteer.refuse_any_further_connections = True

        with pytest.raises(ConnectionClosedError):
            await client.emit(example_event_2)
            await client.emit(example_event_3)

    min_connections = 1 + 1 + 3  # initial, reconnect, three more attempts
    assert (
        recorder.connections >= min_connections < min_connections + 1
    )  # There's some non-determinism in the number of connections
    assert_recorded_events_in_order(
        recorder,
        [
            example_event_1,
            # event 2 never made it because we cause that error during reconnection
            # event 3 never made it because we cause that error during reconnection
        ],
    )


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

    monkeypatch.setattr("prefect.events.clients.websocket_connect", mock_connect)

    with caplog.at_level(logging.WARNING):
        with pytest.raises(Exception, match="Connection failed"):
            async with PrefectEventsClient("ws://localhost"):
                pass

    assert any(
        "Unable to connect to 'ws" in record.message for record in caplog.records
    )


async def test_events_subscriber_auth_string(puppeteer: Puppeteer, events_api_url: str):
    """Tests that the PrefectEventSubscriber sends the correct auth token based on
    PREFECT_API_AUTH_STRING, using the puppeteer fixture to simulate server responses.

    Sets PREFECT_API_URL via temporary_settings to events_api_url to ensure
    get_events_subscriber targets the puppeteer test server.
    """

    secret = "server-secret"

    puppeteer.token = secret

    with temporary_settings(
        {
            PREFECT_API_URL: events_api_url,
            PREFECT_CLOUD_API_URL: "http://different-cloud/api",
        }
    ):
        # Scenario 1: Client string matches server secret - Should succeed
        with temporary_settings({PREFECT_API_AUTH_STRING: secret}):
            try:
                # Call without api_url - it uses PREFECT_API_URL from outer context
                async with get_events_subscriber():
                    pass
            except Exception as e:
                pytest.fail(f"Connection failed unexpectedly: {e}")

        # Scenario 2: Client string does NOT match server secret - Should fail
        with temporary_settings({PREFECT_API_AUTH_STRING: "wrong"}):
            # Match the client's formatted error message, including the reason sent by puppeteer
            with pytest.raises(
                Exception, match=r"Unable to authenticate.*Reason: nope"
            ):
                async with get_events_subscriber():
                    pass

        # Scenario 3: Client string is missing - Should fail (Auth required but no token provided)
        with temporary_settings({PREFECT_API_AUTH_STRING: None}):
            # Match the client's formatted error message, including the reason sent by puppeteer
            with pytest.raises(
                Exception, match=r"Unable to authenticate.*Reason: nope"
            ):
                async with get_events_subscriber():
                    pass  # Connection should fail during __aenter__
