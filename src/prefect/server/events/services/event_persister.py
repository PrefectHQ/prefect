"""
The event persister moves event messages from the event bus to storage
storage as fast as it can.  Never gets tired.
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import AsyncGenerator, List, Optional

from prefect.logging import get_logger
from prefect.server.database.dependencies import provide_database_interface
from prefect.server.events.schemas.events import ReceivedEvent
from prefect.server.events.storage.database import write_events
from prefect.server.utilities.messaging import Message, MessageHandler, create_consumer
from prefect.settings import (
    PREFECT_API_SERVICES_EVENT_PERSISTER_BATCH_SIZE,
    PREFECT_API_SERVICES_EVENT_PERSISTER_FLUSH_INTERVAL,
)

logger = get_logger(__name__)


class EventPersister:
    """A service that persists events to the database as they arrive."""

    name: str = "EventLogger"

    consumer_task: Optional[asyncio.Task] = None
    started_event: Optional[asyncio.Event] = asyncio.Event()

    async def start(self):
        assert self.consumer_task is None, "Event persister already started"
        self.consumer = create_consumer("events")

        async with create_handler(
            batch_size=PREFECT_API_SERVICES_EVENT_PERSISTER_BATCH_SIZE.value(),
            flush_every=timedelta(
                seconds=PREFECT_API_SERVICES_EVENT_PERSISTER_FLUSH_INTERVAL.value()
            ),
        ) as handler:
            self.consumer_task = asyncio.create_task(self.consumer.run(handler))
            logger.debug("Event persister started")
            self.started_event.set()

            try:
                await self.consumer_task
            except asyncio.CancelledError:
                pass

    async def stop(self):
        assert self.consumer_task is not None, "Event persister not started"
        self.consumer_task.cancel()
        try:
            await self.consumer_task
        except asyncio.CancelledError:
            pass
        finally:
            self.consumer_task = None
            if self.started_event:
                self.started_event.clear()
        logger.debug("Event persister stopped")


@asynccontextmanager
async def create_handler(
    batch_size: int = 20,
    flush_every: timedelta = timedelta(seconds=5),
) -> AsyncGenerator[MessageHandler, None]:
    """
    Set up a message handler that will accumulate and send events to
    the database every `batch_size` messages, or every `flush_every` interval to flush
    any remaining messages
    """
    db = provide_database_interface()

    queue: asyncio.Queue[ReceivedEvent] = asyncio.Queue()

    async def flush() -> None:
        logger.debug(f"Persisting {queue.qsize()} events...")

        batch: List[ReceivedEvent] = []

        while queue.qsize() > 0:
            batch.append(await queue.get())

        async with await db.session() as session:
            await write_events(session=session, events=batch)
            await session.commit()

        logger.debug("Finished persisting events.")

    async def flush_periodically():
        while True:
            await asyncio.sleep(flush_every.total_seconds())
            if queue.qsize():
                await flush()

    async def message_handler(message: Message):
        if not message.data:
            return

        event = ReceivedEvent.parse_raw(message.data)
        await queue.put(event)

        if queue.qsize() >= batch_size:
            await flush()

    periodic_task = asyncio.create_task(flush_periodically())

    try:
        yield message_handler
    finally:
        periodic_task.cancel()
        if queue.qsize():
            await flush()
