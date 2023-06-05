import uuid

import pytest

from prefect import flow
from prefect.events import Event
from prefect.events.clients import (
    AssertingEventsClient,
    NullEventsClient,
    PrefectCloudEventsClient,
)
from prefect.events.worker import EventsWorker
from prefect.settings import (
    PREFECT_API_URL,
    PREFECT_CLOUD_API_URL,
    PREFECT_EXPERIMENTAL_ENABLE_EVENTS_CLIENT,
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


def test_worker_instance_null_client_no_api_url():
    with temporary_settings(updates={PREFECT_API_URL: None}):
        worker = EventsWorker.instance()
        assert worker.client_type == NullEventsClient


def test_worker_instance_null_client_non_cloud_api_url():
    with temporary_settings(updates={PREFECT_API_URL: "http://localhost:8080/api"}):
        worker = EventsWorker.instance()
        assert worker.client_type == NullEventsClient


def test_worker_instance_null_client_cloud_api_url_experiment_disabled():
    with temporary_settings(
        updates={
            PREFECT_EXPERIMENTAL_ENABLE_EVENTS_CLIENT: False,
            PREFECT_API_URL: "https://api.prefect.cloud/api/accounts/72483643-e98d-4323-889a-a12905ff21cd/workspaces/cda37001-1181-4f3c-bf03-00da4b532776",
            PREFECT_CLOUD_API_URL: "https://api.prefect.cloud/api/",
        }
    ):
        worker = EventsWorker.instance()
        assert worker.client_type == NullEventsClient


def test_worker_instance_null_client_cloud_api_url_experiment_enabled():
    with temporary_settings(
        updates={
            PREFECT_EXPERIMENTAL_ENABLE_EVENTS_CLIENT: True,
            PREFECT_API_URL: "https://api.prefect.cloud/api/accounts/72483643-e98d-4323-889a-a12905ff21cd/workspaces/cda37001-1181-4f3c-bf03-00da4b532776",
            PREFECT_CLOUD_API_URL: "https://api.prefect.cloud/api/",
        }
    ):
        worker = EventsWorker.instance()
        assert worker.client_type == PrefectCloudEventsClient


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

    state = emitting_flow._run()

    flow_run = await prefect_client.read_flow_run(state.state_details.flow_run_id)
    db_flow = await prefect_client.read_flow(flow_run.flow_id)

    asserting_events_worker.drain()

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
