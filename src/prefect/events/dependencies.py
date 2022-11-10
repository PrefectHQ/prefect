from typing import AsyncGenerator

from prefect.events.clients import EventsClient, NullEventsClient


async def events_client() -> AsyncGenerator[EventsClient, None]:
    async with NullEventsClient() as client:
        yield client
