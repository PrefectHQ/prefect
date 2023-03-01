from typing import Generator
from unittest import mock

import pendulum
import pytest

from prefect.events import Event
from prefect.events.clients import AssertingEventsClient
from prefect.events.worker import EventsWorker


@pytest.fixture(autouse=True)
def reset_asserting_events_client():
    AssertingEventsClient.reset()


@pytest.fixture
def start_of_test() -> pendulum.DateTime:
    return pendulum.now("UTC")


@pytest.fixture
def example_event_1() -> Event:
    return Event(
        event="marvelous.things.happened",
        resource={"prefect.resource.id": "something-valuable"},
    )


@pytest.fixture
def example_event_2() -> Event:
    return Event(
        event="wonderous.things.happened",
        resource={"prefect.resource.id": "something-valuable"},
    )


@pytest.fixture
def example_event_3() -> Event:
    return Event(
        event="delightful.things.happened",
        resource={"prefect.resource.id": "something-valuable"},
    )


@pytest.fixture
def example_event_4() -> Event:
    return Event(
        event="ingenious.things.happened",
        resource={"prefect.resource.id": "something-valuable"},
    )


@pytest.fixture
def example_event_5() -> Event:
    return Event(
        event="delectable.things.happened",
        resource={"prefect.resource.id": "something-valuable"},
    )


@pytest.fixture(scope="session")
def events_worker() -> Generator[EventsWorker, None, None]:
    worker = EventsWorker(AssertingEventsClient)

    # Mock `get_worker_from_run_context` so that `get_events_worker` context
    # manager doesn't attempt to manage the lifecycle of this worker.
    with mock.patch(
        "prefect.events.worker.get_worker_from_run_context"
    ) as worker_from_context:
        worker_from_context.return_value = worker

        worker.start()
        yield worker
        worker.stop()


@pytest.fixture(autouse=True)
def reset_worker_events(events_worker: EventsWorker):
    assert isinstance(events_worker._client, AssertingEventsClient)
    events_worker._client.events = []
