import pytest

from prefect.events import Event
from prefect.events.clients import AssertingEventsClient
from prefect.settings import (
    PREFECT_API_KEY,
    PREFECT_API_URL,
    PREFECT_CLOUD_API_URL,
    temporary_settings,
)
from prefect.testing.cli import invoke_and_assert
from prefect.testing.fixtures import Puppeteer
from prefect.utilities.asyncutils import run_sync_in_worker_thread


@pytest.fixture
def example_event_1() -> Event:
    return Event(
        event="marvelous.things.happened",
        resource={"prefect.resource.id": "something-valuable"},
        related=[
            {
                "prefect.resource.role": "actor",
                "prefect.resource.id": "prefect-cloud.actor.5c83c6e4-3a6b-42db-93b1-b81d2773a0ec",
                "prefect.resource.name": "Peter Francis Geraci",
                "prefect-cloud.email": "george@prefect.io",
                "prefect-cloud.name": "George Coyne",
                "prefect-cloud.handle": "georgeprefectio",
            }
        ],
    )


@pytest.fixture
def example_event_2() -> Event:
    return Event(
        event="wondrous.things.happened",
        resource={"prefect.resource.id": "something-valuable"},
    )


@pytest.fixture
def cloud_api_setup(events_cloud_api_url: str):
    with temporary_settings(
        updates={
            PREFECT_API_URL: events_cloud_api_url,
            PREFECT_API_KEY: "my-token",
            PREFECT_CLOUD_API_URL: events_cloud_api_url,
        }
    ):
        yield


@pytest.mark.usefixtures("cloud_api_setup")
async def test_stream_workspace(
    example_event_1: Event,
    example_event_2: Event,
    puppeteer: Puppeteer,
):
    puppeteer.outgoing_events = [example_event_1, example_event_2]
    puppeteer.token = "my-token"

    event_stream = await run_sync_in_worker_thread(
        invoke_and_assert,
        [
            "events",
            "stream",
            "--run-once",
        ],
        expected_code=0,
        expected_output_contains=[
            "Subscribing to event stream...",
            "wondrous.things.happened",
            "something-valuable",
        ],
    )
    stdout_list = event_stream.stdout.strip().split("\n")
    assert len(stdout_list) == 3
    event1 = stdout_list[1]
    try:
        parsed_event = Event.model_validate_json(event1)
        assert parsed_event.event == example_event_1.event
    except ValueError as e:
        pytest.fail(f"Failed to parse event: {e}")


@pytest.mark.usefixtures("cloud_api_setup")
async def test_stream_account(
    example_event_1: Event,
    example_event_2: Event,
    puppeteer: Puppeteer,
):
    puppeteer.outgoing_events = [example_event_1, example_event_2]
    puppeteer.token = "my-token"

    event_stream = await run_sync_in_worker_thread(
        invoke_and_assert,
        [
            "events",
            "stream",
            "--account",
            "--run-once",
        ],
        expected_code=0,
        expected_output_contains=[
            "Subscribing to event stream...",
            "marvelous.things.happened",
            "something-valuable",
        ],
    )
    stdout_list = event_stream.stdout.strip().split("\n")
    assert len(stdout_list) == 3
    event1 = stdout_list[1]
    try:
        parsed_event = Event.model_validate_json(event1)
        assert parsed_event.event == example_event_1.event
    except ValueError as e:
        pytest.fail(f"Failed to parse event: {e}")


@pytest.fixture
def oss_api_setup(events_api_url: str):
    with temporary_settings(
        updates={
            PREFECT_API_URL: events_api_url,
            PREFECT_API_KEY: None,
        }
    ):
        yield


@pytest.fixture
def mock_events_client(monkeypatch: pytest.MonkeyPatch):
    mock_client = AssertingEventsClient()
    monkeypatch.setattr(
        "prefect.cli.events.get_events_client",
        lambda *args, **kwargs: mock_client,
    )
    return mock_client


@pytest.mark.usefixtures("oss_api_setup")
async def test_stream_oss_events(
    example_event_1: Event,
    example_event_2: Event,
    puppeteer: Puppeteer,
):
    puppeteer.outgoing_events = [example_event_1, example_event_2]
    puppeteer.token = None

    event_stream = await run_sync_in_worker_thread(
        invoke_and_assert,
        [
            "events",
            "stream",
            "--run-once",
        ],
        expected_code=0,
        expected_output_contains=[
            "Subscribing to event stream...",
            "wondrous.things.happened",
            "something-valuable",
        ],
    )

    stdout_list = event_stream.stdout.strip().split("\n")
    assert len(stdout_list) == 3

    event1 = stdout_list[1]
    try:
        parsed_event = Event.model_validate_json(event1)
        assert parsed_event.event == example_event_1.event
    except ValueError as e:
        pytest.fail(f"Failed to parse event: {e}")


# Test emit commands - these emit events and verify their shape


def test_emit_event_simple(mock_events_client):
    invoke_and_assert(
        command=[
            "events",
            "emit",
            "user.action",
            "--resource-id",
            "user-123",
        ],
        expected_code=0,
        expected_output_contains=[
            "Successfully emitted event 'user.action'",
        ],
    )

    # Verify the event was emitted with correct shape
    assert len(mock_events_client.events) == 1
    event = mock_events_client.events[0]
    assert event.event == "user.action"
    assert event.resource["prefect.resource.id"] == "user-123"


def test_emit_event_with_payload(mock_events_client):
    invoke_and_assert(
        command=[
            "events",
            "emit",
            "order.shipped",
            "--resource-id",
            "order-456",
            "--payload",
            '{"tracking": "ABC123", "carrier": "UPS"}',
        ],
        expected_code=0,
        expected_output_contains=[
            "Successfully emitted event 'order.shipped'",
        ],
    )

    # Verify the event was emitted with correct shape
    assert len(mock_events_client.events) == 1
    event = mock_events_client.events[0]
    assert event.event == "order.shipped"
    assert event.resource["prefect.resource.id"] == "order-456"
    assert event.payload == {"tracking": "ABC123", "carrier": "UPS"}


def test_emit_event_with_full_resource(mock_events_client):
    invoke_and_assert(
        command=[
            "events",
            "emit",
            "customer.subscribed",
            "--resource",
            '{"prefect.resource.id": "customer-789", "prefect.resource.name": "ACME Corp", "tier": "premium"}',
        ],
        expected_code=0,
        expected_output_contains=[
            "Successfully emitted event 'customer.subscribed'",
        ],
    )

    # Verify the event was emitted with correct shape
    assert len(mock_events_client.events) == 1
    event = mock_events_client.events[0]
    assert event.event == "customer.subscribed"
    assert event.resource["prefect.resource.id"] == "customer-789"
    assert event.resource["prefect.resource.name"] == "ACME Corp"
    assert event.resource["tier"] == "premium"


async def test_emit_event_missing_resource_id():
    await run_sync_in_worker_thread(
        invoke_and_assert,
        [
            "events",
            "emit",
            "test.event",
        ],
        expected_code=1,
        expected_output_contains=[
            "Resource must include 'prefect.resource.id'",
        ],
    )


async def test_emit_event_invalid_json_payload():
    await run_sync_in_worker_thread(
        invoke_and_assert,
        [
            "events",
            "emit",
            "test.event",
            "--resource-id",
            "test-123",
            "--payload",
            "{invalid json}",
        ],
        expected_code=1,
        expected_output_contains=[
            "Payload must be valid JSON",
        ],
    )


def test_emit_event_key_value_syntax(mock_events_client):
    invoke_and_assert(
        command=[
            "events",
            "emit",
            "database.migrated",
            "--resource",
            "prefect.resource.id=db-prod-01",
        ],
        expected_code=0,
        expected_output_contains=[
            "Successfully emitted event 'database.migrated'",
        ],
    )

    # Verify the event was emitted with correct shape
    assert len(mock_events_client.events) == 1
    event = mock_events_client.events[0]
    assert event.event == "database.migrated"
    assert event.resource["prefect.resource.id"] == "db-prod-01"


async def test_emit_event_resource_not_dict():
    await run_sync_in_worker_thread(
        invoke_and_assert,
        [
            "events",
            "emit",
            "test.event",
            "--resource",
            '["not", "a", "dict"]',
        ],
        expected_code=1,
        expected_output_contains=[
            "Resource must be a JSON object, not an array or string",
        ],
    )


async def test_emit_event_payload_not_dict():
    await run_sync_in_worker_thread(
        invoke_and_assert,
        [
            "events",
            "emit",
            "test.event",
            "--resource-id",
            "test-123",
            "--payload",
            '"just a string"',
        ],
        expected_code=1,
        expected_output_contains=[
            "Payload must be a JSON object",
        ],
    )


def test_emit_event_related_single_object(mock_events_client):
    invoke_and_assert(
        command=[
            "events",
            "emit",
            "item.purchased",
            "--resource-id",
            "item-789",
            "--related",
            '{"prefect.resource.id": "user-456", "prefect.resource.role": "buyer"}',
        ],
        expected_code=0,
        expected_output_contains=[
            "Successfully emitted event 'item.purchased'",
        ],
    )

    # Verify the event was emitted with correct shape
    assert len(mock_events_client.events) == 1
    event = mock_events_client.events[0]
    assert event.event == "item.purchased"
    assert event.resource["prefect.resource.id"] == "item-789"
    assert len(event.related) == 1
    assert event.related[0]["prefect.resource.id"] == "user-456"
    assert event.related[0]["prefect.resource.role"] == "buyer"


def test_emit_event_related_array(mock_events_client):
    invoke_and_assert(
        command=[
            "events",
            "emit",
            "team.formed",
            "--resource-id",
            "team-123",
            "--related",
            '[{"prefect.resource.id": "user-1", "prefect.resource.role": "member"}, {"prefect.resource.id": "user-2", "prefect.resource.role": "lead"}]',
        ],
        expected_code=0,
        expected_output_contains=[
            "Successfully emitted event 'team.formed'",
        ],
    )

    # Verify the event was emitted with correct shape
    assert len(mock_events_client.events) == 1
    event = mock_events_client.events[0]
    assert event.event == "team.formed"
    assert event.resource["prefect.resource.id"] == "team-123"
    assert len(event.related) == 2
    assert event.related[0]["prefect.resource.id"] == "user-1"
    assert event.related[0]["prefect.resource.role"] == "member"
    assert event.related[1]["prefect.resource.id"] == "user-2"
    assert event.related[1]["prefect.resource.role"] == "lead"
