from typing import Type

import pytest

from prefect.events import Event
from prefect.events.clients import AssertingEventsClient, EventsClient, NullEventsClient


async def test_null_events_client_does_nothing(example_event_1: Event):
    async with NullEventsClient() as client:
        await client.emit(example_event_1)


async def test_asserting_events_client_records_instances():
    client1 = AssertingEventsClient()
    assert AssertingEventsClient.last is client1

    client2 = AssertingEventsClient()
    assert AssertingEventsClient.last is client2

    assert AssertingEventsClient.all == [client1, client2]


def test_asserting_events_client_captures_arguments():
    client = AssertingEventsClient("hello", "world", got_this_kwarg=True)
    assert client.args == ("hello", "world")
    assert client.kwargs == {"got_this_kwarg": True}


async def test_asserting_events_client_captures_events(example_event_1: Event):
    client = AssertingEventsClient("hello", "world", got_this_kwarg=True)

    assert not hasattr(client, "events")

    async with client:
        assert client.events == []

        await client.emit(example_event_1)

        assert client.events == [example_event_1]

    # In order to be maximally useful in test contexts, AssertingEventsClient should
    # preserve the list of captured events even after the context has exited
    assert client.events == [example_event_1]


@pytest.mark.parametrize("client_class", [NullEventsClient, AssertingEventsClient])
async def test_asserting_events_client_must_be_used_as_a_context_manager(
    client_class: Type[EventsClient], example_event_1: Event
):
    client = client_class()
    with pytest.raises(TypeError, match="context manager"):
        await client.emit(example_event_1)
