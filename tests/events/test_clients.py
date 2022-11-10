from prefect.events.clients import NullEventsClient
from prefect.events.schemas import Event
from prefect.testing.events import AssertingEventsClient


async def test_null_client_can_emit_event(example_event: Event):
    async with NullEventsClient() as client:
        await client.emit(example_event)


async def test_asserting_client_can_emit_event(example_event: Event):
    async with AssertingEventsClient() as client:
        await client.emit(example_event)
        assert example_event in client.events
