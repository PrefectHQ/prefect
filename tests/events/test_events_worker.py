import uuid

import pytest

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
        assert worker._client_type == NullEventsClient


def test_worker_instance_null_client_non_cloud_api_url():
    with temporary_settings(
        updates={
            PREFECT_API_URL: "http://localhost:8080/api",
            PREFECT_API_URL: "https://api.prefect.cloud/api/accounts/72483643-e98d-4323-889a-a12905ff21cd/workspaces/cda37001-1181-4f3c-bf03-00da4b532776",
        }
    ):
        worker = EventsWorker.instance()
        assert worker._client_type == NullEventsClient


def test_worker_instance_null_client_cloud_api_url_experiment_disabled():
    with temporary_settings(
        updates={
            PREFECT_EXPERIMENTAL_ENABLE_EVENTS_CLIENT: False,
            PREFECT_API_URL: "https://api.prefect.cloud/api/accounts/72483643-e98d-4323-889a-a12905ff21cd/workspaces/cda37001-1181-4f3c-bf03-00da4b532776",
            PREFECT_CLOUD_API_URL: "https://api.prefect.cloud/api/",
        }
    ):
        worker = EventsWorker.instance()
        assert worker._client_type == NullEventsClient


def test_worker_instance_null_client_cloud_api_url_experiment_enabled():
    with temporary_settings(
        updates={
            PREFECT_EXPERIMENTAL_ENABLE_EVENTS_CLIENT: True,
            PREFECT_API_URL: "https://api.prefect.cloud/api/accounts/72483643-e98d-4323-889a-a12905ff21cd/workspaces/cda37001-1181-4f3c-bf03-00da4b532776",
            PREFECT_CLOUD_API_URL: "https://api.prefect.cloud/api/",
        }
    ):
        worker = EventsWorker.instance()
        assert worker._client_type == PrefectCloudEventsClient
