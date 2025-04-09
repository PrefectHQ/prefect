import asyncio
import datetime
from typing import AsyncGenerator, AsyncIterator
from uuid import uuid4

import pytest

from prefect.server.events import messaging, stream
from prefect.server.events.filters import (
    EventFilter,
    EventNameFilter,
    EventOccurredFilter,
)
from prefect.server.events.schemas.events import Event, ReceivedEvent, Resource
from prefect.types._datetime import now


@pytest.fixture
def event1() -> Event:
    return Event(
        occurred=now("UTC"),
        event="was.radical",
        resource=Resource({"prefect.resource.id": "my.resources"}),
        payload={"hello": "world"},
        id=uuid4(),
    )


@pytest.fixture
def event2() -> Event:
    return Event(
        occurred=now("UTC"),
        event="was.super.awesome",
        resource=Resource({"prefect.resource.id": "my.resources"}),
        payload={"goodbye": "moon"},
        id=uuid4(),
    )


@pytest.fixture
def event3() -> Event:
    return Event(
        occurred=now("UTC"),
        event="you.betcha",
        resource=Resource({"prefect.resource.id": "my.resources"}),
        payload={"goodbye": "moon"},
        id=uuid4(),
    )


@pytest.fixture
def received_event1(event1: Event) -> ReceivedEvent:
    return event1.receive()


@pytest.fixture
def received_event2(event2: Event) -> ReceivedEvent:
    return event2.receive()


@pytest.fixture
def received_event3(event3: Event) -> ReceivedEvent:
    return event3.receive()


@pytest.fixture
async def distributor_running() -> AsyncGenerator[None, None]:
    await stream.start_distributor()
    await stream.start_distributor()  # this should be a no-op, covers that case
    try:
        yield
    finally:
        await stream.stop_distributor()
        await stream.stop_distributor()  # this should be a no-op, covers that case


@pytest.fixture
def default_liberal_filter() -> EventFilter:
    return EventFilter(
        occurred=EventOccurredFilter(
            since=now("UTC"),
            until=now("UTC") + datetime.timedelta(days=365),
        )
    )


@pytest.fixture
async def subscription1(
    distributor_running: None,
    default_liberal_filter: EventFilter,
) -> AsyncGenerator[AsyncIterator[ReceivedEvent], None]:
    async with stream.events(default_liberal_filter) as subscription1:
        yield subscription1


@pytest.fixture
async def subscription2(
    distributor_running: None,
    default_liberal_filter: EventFilter,
) -> AsyncGenerator[AsyncIterator[ReceivedEvent], None]:
    async with stream.events(default_liberal_filter) as subscription2:
        yield subscription2


async def test_subscriptions_are_cleaned_up_when_the_context_is_closed(
    default_liberal_filter: EventFilter,
):
    assert len(stream.subscribers) == 0

    filter1 = default_liberal_filter
    filter2 = default_liberal_filter

    async with stream.subscribed(filter1):
        assert len(stream.subscribers) == 1
        async with stream.subscribed(filter2):
            assert len(stream.subscribers) == 2
        assert len(stream.subscribers) == 1

    assert len(stream.subscribers) == 0


async def test_subscribing_to_stream(
    subscription1: AsyncIterator[ReceivedEvent],
    received_event1: ReceivedEvent,
    received_event2: ReceivedEvent,
):
    await messaging.publish([received_event1])
    streamed = await subscription1.__anext__()
    assert streamed == received_event1

    await messaging.publish([received_event2])
    streamed = await subscription1.__anext__()
    assert streamed == received_event2


@pytest.fixture(autouse=True)
def smaller_backlog_size(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(stream, "SUBSCRIPTION_BACKLOG", 10)


async def test_maximum_backlog(
    subscription1: AsyncIterator[ReceivedEvent],
    received_event1: ReceivedEvent,
    received_event2: ReceivedEvent,
):
    assert stream.SUBSCRIPTION_BACKLOG == 10  # from the fixture above

    # send one message just to prime the pump
    await messaging.publish([received_event1])
    streamed = await subscription1.__anext__()
    assert streamed == received_event1

    # now send one more message than the queue can hold
    for i in range(stream.SUBSCRIPTION_BACKLOG + 1):
        await messaging.publish(
            [received_event1.model_copy(update={"id": uuid4(), "event": str(i)})]
        )

    # let the pending messages in the Pub/Sub queue get distributed
    await asyncio.sleep(0.25)

    # and drain that backlog, which should be exactly SUBSCRIPTION_BACKLOG events
    for i in range(stream.SUBSCRIPTION_BACKLOG):
        await subscription1.__anext__()

    # now send one more event; if everything is working, it will be the very next one
    # that shows up on the subscription
    await messaging.publish([received_event2])
    streamed = await subscription1.__anext__()
    assert streamed.event == received_event2.event


async def test_two_subscriptions_get_all_events(
    subscription1: AsyncIterator[ReceivedEvent],
    subscription2: AsyncIterator[ReceivedEvent],
    received_event1: ReceivedEvent,
    received_event2: ReceivedEvent,
    received_event3: ReceivedEvent,
):
    await messaging.publish([received_event1])

    one, two = await subscription1.__anext__(), await subscription2.__anext__()
    assert one == two == received_event1

    await messaging.publish([received_event2])

    one, two = await subscription1.__anext__(), await subscription2.__anext__()
    assert one == two == received_event2

    await messaging.publish([received_event3])

    one, two = await subscription1.__anext__(), await subscription2.__anext__()
    assert one == two == received_event3


@pytest.fixture
async def filter_by_events(default_liberal_filter: EventFilter) -> EventFilter:
    by_event = default_liberal_filter.model_copy()
    by_event.event = EventNameFilter(name=["was.radical", "you.betcha"])
    return by_event


@pytest.fixture
async def filtered_subscription(
    distributor_running: None,
    filter_by_events: EventFilter,
) -> AsyncGenerator[AsyncIterator[ReceivedEvent], None]:
    async with stream.events(filter_by_events) as filtered:
        yield filtered


async def test_event_filter_is_applied_to_event_stream(
    filtered_subscription: AsyncIterator[ReceivedEvent],
    filter_by_events: EventFilter,
    received_event1: ReceivedEvent,
    received_event2: ReceivedEvent,
    received_event3: ReceivedEvent,
):
    assert filter_by_events.includes(received_event1)
    await messaging.publish([received_event1])

    streamed = await filtered_subscription.__anext__()
    assert streamed == received_event1

    assert not filter_by_events.includes(received_event2)
    await messaging.publish([received_event2])

    assert filter_by_events.includes(received_event3)
    await messaging.publish([received_event3])

    # event 2 will be skipped because it doesn't match the filter
    streamed = await filtered_subscription.__anext__()
    assert streamed == received_event3
