from datetime import timedelta
from unittest import mock
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest

from prefect.events import emit_event
from prefect.events.clients import AssertingEventsClient
from prefect.events.worker import EventsWorker
from prefect.settings import (
    PREFECT_API_URL,
    temporary_settings,
)
from prefect.types import DateTime
from prefect.types._datetime import now


@pytest.mark.usefixtures("reset_worker_events")
def test_emits_simple_event(asserting_events_worker: EventsWorker):
    emit_event(
        event="vogon.poetry.read",
        resource={"prefect.resource.id": "vogon.poem.oh-freddled-gruntbuggly"},
    )

    asserting_events_worker.drain()

    assert isinstance(asserting_events_worker._client, AssertingEventsClient)
    assert len(asserting_events_worker._client.events) == 1
    event = asserting_events_worker._client.events[0]
    assert event.event == "vogon.poetry.read"
    assert event.resource.id == "vogon.poem.oh-freddled-gruntbuggly"


@pytest.mark.usefixtures("reset_worker_events")
def test_emits_complex_event(asserting_events_worker: EventsWorker):
    emit_event(
        event="vogon.poetry.read",
        resource={"prefect.resource.id": "vogon.poem.oh-freddled-gruntbuggly"},
        occurred=DateTime(2023, 3, 1, 12, 39, 28, tzinfo=ZoneInfo("UTC")),
        related=[
            {
                "prefect.resource.id": "vogon.ship.the-business-end",
                "prefect.resource.role": "locale",
            }
        ],
        payload={"text": "Oh freddled gruntbuggly..."},
        id=UUID(int=1),
    )

    asserting_events_worker.drain()

    assert isinstance(asserting_events_worker._client, AssertingEventsClient)
    assert len(asserting_events_worker._client.events) == 1
    event = asserting_events_worker._client.events[0]
    assert event.event == "vogon.poetry.read"
    assert event.resource.id == "vogon.poem.oh-freddled-gruntbuggly"
    assert event.occurred == DateTime(2023, 3, 1, 12, 39, 28, tzinfo=ZoneInfo("UTC"))
    assert len(event.related) == 1
    assert event.related[0].id == "vogon.ship.the-business-end"
    assert event.related[0].role == "locale"
    assert event.payload == {"text": "Oh freddled gruntbuggly..."}
    assert event.id == UUID(int=1)


@pytest.mark.usefixtures("reset_worker_events")
def test_returns_event(asserting_events_worker: EventsWorker):
    emitted_event = emit_event(
        event="vogon.poetry.read",
        resource={"prefect.resource.id": "vogon.poem.oh-freddled-gruntbuggly"},
    )

    asserting_events_worker.drain()
    assert isinstance(asserting_events_worker._client, AssertingEventsClient)
    assert len(asserting_events_worker._client.events) == 1
    assert emitted_event == asserting_events_worker._client.events[0]


@pytest.mark.usefixtures("reset_worker_events")
def test_sets_follows_tight_timing(asserting_events_worker: EventsWorker):
    destroyed_event = emit_event(
        event="planet.destroyed",
        resource={"prefect.resource.id": "milky-way.sol.earth"},
    )
    assert destroyed_event

    read_event = emit_event(
        event="vogon.poetry.read",
        resource={"prefect.resource.id": "vogon.poem.oh-freddled-gruntbuggly"},
        follows=destroyed_event,
    )
    assert read_event

    asserting_events_worker.drain()
    assert read_event.follows == destroyed_event.id


@pytest.mark.usefixtures("reset_worker_events")
def test_does_not_set_follows_not_tight_timing(asserting_events_worker: EventsWorker):
    destroyed_event = emit_event(
        event="planet.destroyed",
        occurred=now("UTC") - timedelta(minutes=10),
        resource={"prefect.resource.id": "milky-way.sol.earth"},
    )
    assert destroyed_event

    # These events are more than 5m apart so the `follows` property of the
    # emitted event shouldn't be set.
    read_event = emit_event(
        event="vogon.poetry.read",
        resource={"prefect.resource.id": "vogon.poem.oh-freddled-gruntbuggly"},
        follows=destroyed_event,
    )
    assert read_event

    asserting_events_worker.drain()
    assert read_event.follows is None


def test_noop_with_non_cloud_client(mock_should_emit_events: mock.Mock):
    with temporary_settings(updates={PREFECT_API_URL: "http://localhost:4242"}):
        mock_should_emit_events.return_value = None

        assert (
            emit_event(
                event="vogon.poetry.read",
                resource={"prefect.resource.id": "vogon.poem.oh-freddled-gruntbuggly"},
            )
            is None
        )
