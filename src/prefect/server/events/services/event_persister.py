"""
The event persister moves event messages from the event bus to storage
storage as fast as it can.  Never gets tired.
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import AsyncGenerator, List, Optional

import pendulum
import sqlalchemy as sa

from prefect.logging import get_logger
from prefect.server.database.dependencies import provide_database_interface
from prefect.server.events.schemas.events import ReceivedEvent
from prefect.server.events.storage.database import write_events
from prefect.server.utilities.messaging import Message, MessageHandler, create_consumer
from prefect.settings import (
    PREFECT_API_SERVICES_EVENT_PERSISTER_BATCH_SIZE,
    PREFECT_API_SERVICES_EVENT_PERSISTER_FLUSH_INTERVAL,
    PREFECT_EVENTS_RETENTION_PERIOD,
)

logger = get_logger(__name__)


class EventPersister:
    """A service that persists events to the database as they arrive."""

    name: str = "EventLogger"

    consumer_task: Optional[asyncio.Task] = None

    def __init__(self):
        self._started_event: Optional[asyncio.Event] = None

    @property
    def started_event(self) -> asyncio.Event:
        if self._started_event is None:
            self._started_event = asyncio.Event()
        return self._started_event

    @started_event.setter
    def started_event(self, value: asyncio.Event) -> None:
        self._started_event = value

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
    trim_every: timedelta = timedelta(minutes=15),
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

        try:
            async with db.session_context() as session:
                await write_events(session=session, events=batch)
                await session.commit()
                logger.debug("Finished persisting events.")
        except Exception:
            logger.debug("Error flushing events, restoring to queue", exc_info=True)
            for event in batch:
                queue.put_nowait(event)

    async def trim() -> None:
        older_than = pendulum.now("UTC") - PREFECT_EVENTS_RETENTION_PERIOD.value()

        try:
            async with db.session_context() as session:
                result = await session.execute(
                    sa.delete(db.Event).where(db.Event.occurred < older_than)
                )
                await session.commit()
                if result.rowcount:
                    logger.debug(
                        "Trimmed %s events older than %s.", result.rowcount, older_than
                    )
        except Exception:
            logger.exception("Error trimming events", exc_info=True)

    async def flush_periodically():
        try:
            while True:
                await asyncio.sleep(flush_every.total_seconds())
                if queue.qsize():
                    await flush()
        except asyncio.CancelledError:
            return

    async def trim_periodically():
        try:
            while True:
                await asyncio.sleep(trim_every.total_seconds())
                await trim()
        except asyncio.CancelledError:
            return

    async def message_handler(message: Message):
        if not message.data:
            return

        event = ReceivedEvent.model_validate_json(message.data)
        await queue.put(event)

        if queue.qsize() >= batch_size:
            await flush()

    periodic_flush = asyncio.create_task(flush_periodically())
    periodic_trim = asyncio.create_task(trim_periodically())

    try:
        yield message_handler
    finally:
        periodic_flush.cancel()
        periodic_trim.cancel()
        if queue.qsize():
            await flush()
