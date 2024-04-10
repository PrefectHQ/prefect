import pytest

from prefect.events import Event
from prefect.events.clients import AssertingEventsClient


@pytest.fixture(autouse=True)
def reset_asserting_events_client():
    AssertingEventsClient.reset()


@pytest.fixture(autouse=True)
def mock_should_emit_events(mock_should_emit_events):
    yield mock_should_emit_events


@pytest.fixture
def example_event_1() -> Event:
    return Event(
        event="marvelous.things.happened",
        resource={"prefect.resource.id": "something-valuable"},
    )


@pytest.fixture
def example_event_2() -> Event:
    return Event(
        event="wondrous.things.happened",
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
