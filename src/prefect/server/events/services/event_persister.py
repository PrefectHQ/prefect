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
from prefect.settings.context import get_current_settings
from prefect.settings.models.server.services import ServerServicesEventPersisterSettings
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
    def service_settings(cls) -> ServerServicesEventPersisterSettings:
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
            read_batch_size=self.service_settings().read_batch_size,
        )

        settings = self.service_settings()
        async with create_handler(
            batch_size=settings.batch_size,
            flush_every=timedelta(seconds=settings.flush_interval),
            queue_max_size=settings.queue_max_size,
            max_flush_retries=settings.max_flush_retries,
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
            await self.consumer.cleanup()
            self.consumer_task = None
            if self.started_event:
                self.started_event.clear()
        logger.debug("Event persister stopped")


@asynccontextmanager
async def create_handler(
    batch_size: int = 20,
    flush_every: timedelta = timedelta(seconds=5),
    trim_every: timedelta = timedelta(minutes=15),
    queue_max_size: int = 50_000,
    max_flush_retries: int = 5,
) -> AsyncGenerator[MessageHandler, None]:
    """
    Set up a message handler that will accumulate and send events to
    the database every `batch_size` messages, or every `flush_every` interval to flush
    any remaining messages.

    Args:
        batch_size: Number of events to accumulate before flushing
        flush_every: Maximum time between flushes
        trim_every: How often to trim old events
        queue_max_size: Maximum events in queue before dropping new events
        max_flush_retries: Consecutive flush failures before dropping events
    """
    db = provide_database_interface()

    queue: asyncio.Queue[ReceivedEvent] = asyncio.Queue(maxsize=queue_max_size)
    flush_lock = asyncio.Lock()
    consecutive_failures = 0
    settings = get_current_settings()

    async def flush() -> None:
        nonlocal consecutive_failures

        async with flush_lock:
            if queue.qsize() == 0:
                return

            # Log warning when queue reaches 80% capacity
            if queue_max_size > 0 and queue.qsize() > queue_max_size * 0.8:
                logger.warning(
                    "Event queue at %d%% capacity (%d/%d)",
                    int(queue.qsize() / queue_max_size * 100),
                    queue.qsize(),
                    queue_max_size,
                )

            logger.debug("Persisting %d events...", queue.qsize())

            batch: List[ReceivedEvent] = []

            while queue.qsize() > 0:
                batch.append(await queue.get())

            try:
                async with db.session_context() as session:
                    await write_events(session=session, events=batch)
                    await session.commit()
                    logger.debug("Finished persisting events.")
                    consecutive_failures = 0  # Reset on success
            except Exception:
                consecutive_failures += 1
                if consecutive_failures >= max_flush_retries:
                    logger.error(
                        "Max flush retries (%d) reached, dropping %d events",
                        max_flush_retries,
                        len(batch),
                        exc_info=True,
                    )
                    consecutive_failures = 0
                else:
                    logger.debug(
                        "Error flushing events (attempt %d/%d), restoring to queue",
                        consecutive_failures,
                        max_flush_retries,
                        exc_info=True,
                    )
                    for event in batch:
                        queue.put_nowait(event)

    async def trim() -> None:
        older_than = now("UTC") - settings.server.events.retention_period
        delete_batch_size = settings.server.services.event_persister.batch_size_delete
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

        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning(
                "Event queue full (%d/%d), dropping event id=%s",
                queue.qsize(),
                queue_max_size,
                event.id,
            )
            return

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
