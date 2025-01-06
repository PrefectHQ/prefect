from datetime import timedelta
from typing import AsyncGenerator, Generator, List, Type
from unittest import mock
from uuid import uuid4

import pytest

from prefect.server.events.clients import (
    AssertingEventsClient,
    NullEventsClient,
    PrefectServerEventsClient,
)
from prefect.server.events.schemas.events import Event, ReceivedEvent, RelatedResource
from prefect.server.utilities.messaging import CapturingPublisher
from prefect.types import DateTime


@pytest.fixture
def example_event(start_of_test: DateTime) -> Event:
    return Event(
        occurred=start_of_test,
        event="hello.world",
        resource={"prefect.resource.id": "woot"},
        id=uuid4(),
    )


async def test_null_events_client_does_nothing_really(example_event: Event):
    async with NullEventsClient() as c:
        await c.emit(example_event)


@pytest.fixture(autouse=True)
def reset_asserting_events_client():
    AssertingEventsClient.reset()


async def test_asserting_events_client_records_instances():
    async with AssertingEventsClient() as a:
        pass
    async with AssertingEventsClient() as b:
        pass
    assert AssertingEventsClient.last is b
    assert AssertingEventsClient.all == [a, b]


async def test_asserting_events_client_captures_arguments(example_event: Event):
    async with AssertingEventsClient("hello", "world", foo="bar") as c:
        await c.emit(example_event)
    assert c.args == ("hello", "world")
    assert c.kwargs == {"foo": "bar"}


async def test_asserting_events_client_captures_events(example_event: Event):
    async with AssertingEventsClient() as c:
        await c.emit(example_event)
    assert c.events == [example_event]


async def test_asserting_events_client_must_be_opened(example_event: Event):
    with pytest.raises(TypeError, match="context manager"):
        await AssertingEventsClient().emit(example_event)


@pytest.fixture
def example_event_1(start_of_test: DateTime) -> Event:
    return Event(
        occurred=start_of_test + timedelta(seconds=1),
        event="marvelous.things.happened",
        resource={"prefect.resource.id": "something-valuable"},
        id=uuid4(),
    )


@pytest.fixture
def example_event_2(start_of_test: DateTime) -> Event:
    return Event(
        occurred=start_of_test + timedelta(seconds=2),
        event="wondrous.things.happened",
        resource={"prefect.resource.id": "something-invaluable"},
        id=uuid4(),
    )


@pytest.fixture
def example_event_3(start_of_test: DateTime) -> Event:
    return Event(
        occurred=start_of_test + timedelta(seconds=3),
        event="delightful.things.happened",
        resource={
            "prefect.resource.id": "something-wondrous",
            "wonder-type": "amazement",
        },
        related=[
            RelatedResource.model_validate(
                {
                    "prefect.resource.id": "something-valuable",
                    "prefect.resource.role": "shiny",
                    "name": "gold",
                }
            ),
            RelatedResource.model_validate(
                {
                    "prefect.resource.id": "something-glittery",
                    "prefect.resource.role": "sparkle",
                    "name": "diamond",
                }
            ),
        ],
        id=uuid4(),
    )


@pytest.fixture
def example_event_4(start_of_test: DateTime) -> Event:
    return Event(
        occurred=start_of_test + timedelta(seconds=4),
        event="ingenious.things.happened",
        resource={"prefect.resource.id": "something-valuable"},
        id=uuid4(),
    )


@pytest.fixture
def example_event_5(start_of_test: DateTime) -> Event:
    return Event(
        occurred=start_of_test + timedelta(seconds=5),
        event="delectable.things.happened",
        resource={"prefect.resource.id": "something-valuable"},
        payload={
            "glitter_count": "∞",
        },
        id=uuid4(),
    )


@pytest.fixture
async def all_events_emitted(
    example_event_1: Event,
    example_event_2: Event,
    example_event_3: Event,
    example_event_4: Event,
    example_event_5: Event,
) -> AsyncGenerator[AssertingEventsClient, None]:
    async with AssertingEventsClient() as c:
        await c.emit(example_event_1)
        await c.emit(example_event_2)
        await c.emit(example_event_3)
        await c.emit(example_event_4)
        await c.emit(example_event_5)
        yield c


async def test_asserting_event_count(all_events_emitted: AssertingEventsClient):
    assert len(all_events_emitted.events) == 5
    assert AssertingEventsClient.emitted_events_count() == 5
    AssertingEventsClient.assert_emitted_event_count(5)


async def test_asserting_event(all_events_emitted: AssertingEventsClient):
    AssertingEventsClient.assert_emitted_event_with(event="delightful.things.happened")
    with pytest.raises(AssertionError):
        AssertingEventsClient.assert_no_emitted_event_with(
            event="delightful.things.happened"
        )

    AssertingEventsClient.assert_no_emitted_event_with(event="terrible.things.happened")
    with pytest.raises(AssertionError):
        AssertingEventsClient.assert_emitted_event_with(
            event="terrible.things.happened"
        )


async def test_asserting_resource(all_events_emitted: AssertingEventsClient):
    AssertingEventsClient.assert_emitted_event_with(
        resource={"wonder-type": "amazement"}
    )
    with pytest.raises(AssertionError):
        AssertingEventsClient.assert_no_emitted_event_with(
            resource={"wonder-type": "amazement"}
        )

    AssertingEventsClient.assert_emitted_event_with(
        resource={"wonder-type": ["amazement", "astonishment"]}
    )
    with pytest.raises(AssertionError):
        AssertingEventsClient.assert_no_emitted_event_with(
            resource={"wonder-type": ["amazement", "astonishment"]}
        )

    AssertingEventsClient.assert_no_emitted_event_with(
        resource={"wonder-type": ["disappointment", "dejection"]}
    )
    with pytest.raises(AssertionError):
        AssertingEventsClient.assert_emitted_event_with(
            resource={"wonder-type": ["disappointment", "dejection"]}
        )


async def test_asserting_related(all_events_emitted: AssertingEventsClient):
    AssertingEventsClient.assert_emitted_event_with(
        related=[{"prefect.resource.role": "sparkle"}]
    )
    with pytest.raises(AssertionError):
        AssertingEventsClient.assert_no_emitted_event_with(
            related=[{"prefect.resource.role": "sparkle"}]
        )

    AssertingEventsClient.assert_emitted_event_with(
        related=[{"prefect.resource.role": ["sparkle", "luster"]}]
    )
    with pytest.raises(AssertionError):
        AssertingEventsClient.assert_no_emitted_event_with(
            related=[{"prefect.resource.role": ["sparkle", "luster"]}]
        )

    AssertingEventsClient.assert_emitted_event_with(
        related=[{"prefect.resource.role": ["sparkle", "luster"]}, {"name": ["gold"]}]
    )
    with pytest.raises(AssertionError):
        AssertingEventsClient.assert_no_emitted_event_with(
            related=[
                {"prefect.resource.role": ["sparkle", "luster"]},
                {"name": ["gold"]},
            ]
        )

    AssertingEventsClient.assert_no_emitted_event_with(
        related=[{"prefect.resource.role": ["dulling", "dimming"]}]
    )
    with pytest.raises(AssertionError):
        AssertingEventsClient.assert_emitted_event_with(
            related=[{"prefect.resource.role": ["dulling", "dimming"]}]
        )


async def test_asserting_payload(all_events_emitted: AssertingEventsClient):
    AssertingEventsClient.assert_emitted_event_with(payload={"glitter_count": "∞"})
    with pytest.raises(AssertionError):
        AssertingEventsClient.assert_no_emitted_event_with(
            payload={"glitter_count": "∞"}
        )

    AssertingEventsClient.assert_no_emitted_event_with(payload={"sadness_call": "wail"})
    with pytest.raises(AssertionError):
        AssertingEventsClient.assert_emitted_event_with(
            payload={"sadness_call": "wail"}
        )


@pytest.fixture
def capturing_publisher() -> Generator[Type[CapturingPublisher], None, None]:
    with mock.patch(
        "prefect.server.events.messaging.create_publisher",
        CapturingPublisher,
    ):
        CapturingPublisher.messages = []
        yield CapturingPublisher
        CapturingPublisher.messages = []


def captured_events(capturing_publisher: CapturingPublisher) -> List[ReceivedEvent]:
    return [
        ReceivedEvent.model_validate_json(message.data)
        for message in capturing_publisher.messages
    ]


async def test_server_client_publishes_events(
    example_event: Event, capturing_publisher: CapturingPublisher, frozen_time: DateTime
):
    received_event = example_event.receive(received=frozen_time)

    async with PrefectServerEventsClient() as c:
        await c.emit(example_event)

    assert captured_events(capturing_publisher) == [received_event]


async def test_server_client_must_be_opened(example_event: Event):
    with pytest.raises(TypeError, match="context manager"):
        await PrefectServerEventsClient().emit(example_event)


async def test_server_client_only_publishes_if_events(
    capturing_publisher: CapturingPublisher,
):
    async with PrefectServerEventsClient():
        pass

    assert captured_events(capturing_publisher) == []


async def test_server_client_still_publishes_if_error(
    capturing_publisher: CapturingPublisher, example_event: Event, frozen_time: DateTime
):
    with pytest.raises(Exception, match="hi"):
        async with PrefectServerEventsClient() as c:
            received_event = await c.emit(example_event)
            raise Exception("hi!")

    assert captured_events(capturing_publisher) == [received_event]


async def test_server_client_returns_received_event_from_emit(
    capturing_publisher: CapturingPublisher, example_event: Event, frozen_time: DateTime
):
    async with PrefectServerEventsClient() as c:
        received_event = await c.emit(example_event)

    assert isinstance(received_event, ReceivedEvent)
    assert received_event.event == example_event.event
    assert received_event.resource == example_event.resource
    assert received_event.occurred == example_event.occurred
    assert received_event.id == example_event.id
