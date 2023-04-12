from typing import Generator

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


@pytest.fixture
def asserting_events_worker(monkeypatch) -> Generator[EventsWorker, None, None]:
    worker = EventsWorker.instance(AssertingEventsClient)
    # Always yield the asserting worker when new instances are retrieved
    monkeypatch.setattr(EventsWorker, "instance", lambda *_: worker)
    try:
        yield worker
    finally:
        worker.drain()


@pytest.fixture
def reset_worker_events(asserting_events_worker: EventsWorker):
    yield
    assert isinstance(asserting_events_worker._client, AssertingEventsClient)
    asserting_events_worker._client.events = []
