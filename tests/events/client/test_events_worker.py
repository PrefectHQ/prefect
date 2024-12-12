import uuid

import pytest

from prefect import flow
from prefect.client.schemas.objects import State
from prefect.events import Event
from prefect.events.clients import (
    AssertingEventsClient,
    PrefectEventsClient,
)
from prefect.events.utilities import emit_event
from prefect.events.worker import EventsWorker
from prefect.settings import (
    PREFECT_API_URL,
    temporary_settings,
)


@pytest.fixture
def event() -> Event:
    return Event(
        event="vogon.poetry.read",
        resource={"prefect.resource.id": f"poem.{uuid.uuid4()}"},
    )


def test_emits_event_via_client(asserting_events_worker: EventsWorker, event: Event):
    asserting_events_worker.send(event)

    asserting_events_worker.drain()

    assert isinstance(asserting_events_worker._client, AssertingEventsClient)
    assert asserting_events_worker._client.events == [event]


def test_worker_instance_server_client_non_cloud_api_url():
    with temporary_settings(updates={PREFECT_API_URL: "http://localhost:8080/api"}):
        worker = EventsWorker.instance()
        assert worker.client_type == PrefectEventsClient


def test_worker_instance_client_non_cloud_api_url_events_enabled():
    with temporary_settings(updates={PREFECT_API_URL: "http://localhost:8080/api"}):
        worker = EventsWorker.instance()
        assert worker.client_type == PrefectEventsClient


def test_worker_instance_ephemeral_prefect_events_client(enable_ephemeral_server):
    """
    Getting an instance of the worker with ephemeral server mode enabled should
    return a PrefectEventsClient pointing to the subprocess server.
    """
    worker = EventsWorker.instance()
    assert worker.client_type == PrefectEventsClient


async def test_includes_related_resources_from_run_context(
    asserting_events_worker: EventsWorker, reset_worker_events, prefect_client
):
    @flow
    def emitting_flow():
        from prefect.events import emit_event

        emit_event(
            event="vogon.poetry.read",
            resource={"prefect.resource.id": "vogon.poem.oh-freddled-gruntbuggly"},
        )

    state: State[None] = emitting_flow(return_state=True)

    flow_run = await prefect_client.read_flow_run(state.state_details.flow_run_id)
    db_flow = await prefect_client.read_flow(flow_run.flow_id)

    await asserting_events_worker.drain()

    assert isinstance(asserting_events_worker._client, AssertingEventsClient)
    assert len(asserting_events_worker._client.events) == 1
    event = asserting_events_worker._client.events[0]
    assert event.event == "vogon.poetry.read"
    assert event.resource.id == "vogon.poem.oh-freddled-gruntbuggly"

    assert len(event.related) == 2

    assert event.related[0].id == f"prefect.flow-run.{flow_run.id}"
    assert event.related[0].role == "flow-run"
    assert event.related[0]["prefect.resource.name"] == flow_run.name

    assert event.related[1].id == f"prefect.flow.{db_flow.id}"
    assert event.related[1].role == "flow"
    assert event.related[1]["prefect.resource.name"] == db_flow.name


async def test_does_not_include_related_resources_from_run_context_for_lineage_events(
    asserting_events_worker: EventsWorker,
    reset_worker_events,
    prefect_client,
):
    @flow
    def emitting_flow():
        emit_event(
            event="s3.read",
            resource={
                "prefect.resource.id": "s3://bucket-name/key-name",
                "prefect.resource.role": "data-source",
                "prefect.resource.lineage-group": "global",
            },
        )

    emitting_flow(return_state=True)

    await asserting_events_worker.drain()

    assert len(asserting_events_worker._client.events) == 1
    event = asserting_events_worker._client.events[0]
    assert event.event == "s3.read"
    assert event.resource.id == "s3://bucket-name/key-name"
    assert len(event.related) == 0
