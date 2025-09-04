"""
The event persister moves event messages from the event bus to storage
storage as fast as it can.  Never gets tired.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import TYPE_CHECKING, Any, AsyncGenerator, List, NoReturn, TypeVar

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from prefect.logging import get_logger
from prefect.server.database import provide_database_interface
from prefect.server.events.schemas.events import ReceivedEvent
from prefect.server.events.storage.database import write_events
from prefect.server.services.base import RunInEphemeralServers, Service
from prefect.server.utilities.messaging import (
    Consumer,
    Message,
    MessageHandler,
    create_consumer,
)
from prefect.server.utilities.messaging._consumer_names import (
    generate_unique_consumer_name,
)
from prefect.settings import (
    PREFECT_API_SERVICES_EVENT_PERSISTER_BATCH_SIZE,
    PREFECT_API_SERVICES_EVENT_PERSISTER_FLUSH_INTERVAL,
    PREFECT_EVENTS_RETENTION_PERIOD,
    PREFECT_SERVER_SERVICES_EVENT_PERSISTER_BATCH_SIZE_DELETE,
)
from prefect.settings.context import get_current_settings
from prefect.settings.models.server.services import ServicesBaseSetting
from prefect.types._datetime import now

if TYPE_CHECKING:
    import logging

logger: "logging.Logger" = get_logger(__name__)

T = TypeVar("T")


async def batch_delete(
    session: AsyncSession,
    model: type[T],
    condition: Any,
    batch_size: int = 10_000,
) -> int:
    """
    Perform a batch deletion of database records using a subquery with LIMIT. Works with both PostgreSQL and
    SQLite. Compared to a basic delete(...).where(...), a batch deletion is more robust against timeouts
    when handling large tables, which is especially the case if we first delete old entries from long
    existing tables.

    Returns:
        Total number of deleted records
    """
    total_deleted = 0

    while True:
        subquery = (
            sa.select(model.id).where(condition).limit(batch_size).scalar_subquery()
        )
        delete_stmt = sa.delete(model).where(model.id.in_(subquery))

        result = await session.execute(delete_stmt)
        batch_deleted = result.rowcount

        if batch_deleted == 0:
            break

        total_deleted += batch_deleted
        await session.commit()

    return total_deleted


class EventPersister(RunInEphemeralServers, Service):
    """A service that persists events to the database as they arrive."""

    consumer_task: asyncio.Task[None] | None = None

    @classmethod
    def service_settings(cls) -> ServicesBaseSetting:
        return get_current_settings().server.services.event_persister

    def __init__(self):
        super().__init__()
        self._started_event: asyncio.Event | None = None

    @property
    def started_event(self) -> asyncio.Event:
        if self._started_event is None:
            self._started_event = asyncio.Event()
        return self._started_event

    @started_event.setter
    def started_event(self, value: asyncio.Event) -> None:
        self._started_event = value

    async def start(self) -> NoReturn:
        assert self.consumer_task is None, "Event persister already started"
        self.consumer: Consumer = create_consumer(
            "events",
            group="event-persister",
            name=generate_unique_consumer_name("event-persister"),
        )

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

    async def stop(self) -> None:
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
        older_than = now("UTC") - PREFECT_EVENTS_RETENTION_PERIOD.value()
        delete_batch_size = (
            PREFECT_SERVER_SERVICES_EVENT_PERSISTER_BATCH_SIZE_DELETE.value()
        )
        try:
            async with db.session_context() as session:
                resource_count = await batch_delete(
                    session,
                    db.EventResource,
                    db.EventResource.updated < older_than,
                    batch_size=delete_batch_size,
                )

                event_count = await batch_delete(
                    session,
                    db.Event,
                    db.Event.occurred < older_than,
                    batch_size=delete_batch_size,
                )

                if resource_count or event_count:
                    logger.debug(
                        "Trimmed %s events and %s event resources older than %s.",
                        event_count,
                        resource_count,
                        older_than,
                    )
        except Exception:
            logger.exception("Error trimming events and resources", exc_info=True)

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

        logger.debug(
            "Received event: %s with id: %s for resource: %s",
            event.event,
            event.id,
            event.resource.get("prefect.resource.id"),
        )

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
