import time
import uuid
from unittest import mock

import pytest

from prefect.events import Event
from prefect.events.clients import (
    AssertingEventsClient,
    NullEventsClient,
    PrefectCloudEventsClient,
)
from prefect.events.worker import (
    EventsWorker,
    async_get_events_worker,
    get_events_worker,
    get_worker_from_settings,
)
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


@pytest.fixture
def worker() -> EventsWorker:
    return EventsWorker(AssertingEventsClient)


def test_controls_client_and_thread_lifecycle(worker: EventsWorker):
    assert not worker._thread.is_alive()
    assert not hasattr(worker, "_client")
    worker.start()
    worker.emit(None)

    assert worker._thread.is_alive()
    assert isinstance(worker._client, AssertingEventsClient)
    assert worker._client._in_context

    worker.stop()
    assert not hasattr(worker._client, "_in_context")
    assert not worker._thread.is_alive()


def test_start_is_idempontent(worker: EventsWorker):
    worker.start()
    worker.start()  # Would throw a RuntimeError if the thread was started again.
    worker.stop()


def test_stop_is_idempontent(worker: EventsWorker):
    worker.start()
    worker.stop()
    worker.stop()


def test_worker_failure(worker: EventsWorker):
    with mock.patch.object(worker, "_main_loop") as main_loop:
        main_loop.side_effect = Exception("Boom!")
        with pytest.raises(Exception, match="Boom!"):
            worker.start()


def test_emits_event_via_client(worker: EventsWorker, event: Event):
    worker.start()
    worker.emit(event)
    assert isinstance(worker._client, AssertingEventsClient)
    time.sleep(0.3)
    assert worker._client.events == [event]
    worker.stop()


def test_worker_from_settings_null_client_no_api_url():
    with temporary_settings(updates={PREFECT_API_URL: None}):
        worker = get_worker_from_settings()
        assert worker._client_type == NullEventsClient


def test_worker_from_settings_null_client_non_cloud_api_url():
    with temporary_settings(
        updates={
            PREFECT_API_URL: "http://localhost:8080/api",
            PREFECT_CLOUD_API_URL: "https://api.prefect.cloud/api/",
        }
    ):
        worker = get_worker_from_settings()
        assert worker._client_type == NullEventsClient


def test_worker_from_settings_null_client_cloud_api_url_experiment_disabled():
    with temporary_settings(
        updates={
            PREFECT_EXPERIMENTAL_ENABLE_EVENTS_CLIENT: False,
            PREFECT_API_URL: "https://api.prefect.cloud/api/",
            PREFECT_CLOUD_API_URL: "https://api.prefect.cloud/api/",
        }
    ):
        worker = get_worker_from_settings()
        assert worker._client_type == NullEventsClient


def test_worker_from_settings_null_client_cloud_api_url_experiment_enabled():
    with temporary_settings(
        updates={
            PREFECT_EXPERIMENTAL_ENABLE_EVENTS_CLIENT: True,
            PREFECT_API_URL: "https://api.prefect.cloud/api/",
            PREFECT_CLOUD_API_URL: "https://api.prefect.cloud/api/",
        }
    ):
        worker = get_worker_from_settings()
        assert worker._client_type == PrefectCloudEventsClient


def test_get_events_worker_context_manager():
    with get_events_worker() as worker:
        assert worker._thread.is_alive()
        assert isinstance(worker._client, NullEventsClient)
        assert worker._client._in_context

    assert not worker._thread.is_alive()


def test_get_events_worker_unmanaged_lifecycle(worker: EventsWorker):
    import prefect.context

    worker.start()

    with prefect.context.FlowRunContext.construct(events=worker):
        with get_events_worker() as worker_from_context:
            assert worker == worker_from_context

    assert worker._thread.is_alive()
    worker.stop()


async def test_async_get_events_worker_context_manager():
    async with async_get_events_worker() as worker:
        assert worker._thread.is_alive()
        assert isinstance(worker._client, NullEventsClient)
        assert worker._client._in_context
