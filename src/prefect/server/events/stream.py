import asyncio
from asyncio import Queue
from contextlib import asynccontextmanager
from typing import AsyncGenerator, AsyncIterable, Dict, Optional, Set

from prefect.logging import get_logger
from prefect.server.events.filters import EventFilter
from prefect.server.events.schemas.events import ReceivedEvent
from prefect.server.utilities import messaging

logger = get_logger(__name__)

subscribers: Set["Queue[ReceivedEvent]"] = set()
filters: Dict["Queue[ReceivedEvent]", EventFilter] = {}

# The maximum number of message that can be waiting for one subscriber, after which
# new messages will be dropped
SUBSCRIPTION_BACKLOG = 256


@asynccontextmanager
async def subscribed(
    filter: EventFilter,
) -> AsyncGenerator["Queue[ReceivedEvent]", None]:
    queue: "Queue[ReceivedEvent]" = Queue(maxsize=SUBSCRIPTION_BACKLOG)

    subscribers.add(queue)
    filters[queue] = filter

    try:
        yield queue
    finally:
        subscribers.remove(queue)
        del filters[queue]


@asynccontextmanager
async def events(
    filter: EventFilter,
) -> AsyncGenerator[AsyncIterable[Optional[ReceivedEvent]], None]:
    async with subscribed(filter) as queue:

        async def consume() -> AsyncGenerator[Optional[ReceivedEvent], None]:
            while True:
                # Use a brief timeout to allow for cancellation, especially when a
                # client disconnects.  Without a timeout here, a consumer may block
                # forever waiting for a message to be put on the queue, and never notice
                # that their client (like a websocket) has actually disconnected.
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=1)
                except asyncio.TimeoutError:
                    # If the queue is empty, we'll yield to the caller with a None in
                    # order to give it control over what happens next.  This helps with
                    # the outbound websocket, where we want to check if the client is
                    # still connected periodically.
                    yield None
                    continue

                yield event

        yield consume()


@asynccontextmanager
async def distributor() -> AsyncGenerator[messaging.MessageHandler, None]:
    async def message_handler(message: messaging.Message):
        assert message.data

        try:
            assert message.attributes
        except Exception:
            return

        if subscribers:
            event = ReceivedEvent.model_validate_json(message.data)
            for queue in subscribers:
                filter = filters[queue]
                if filter.excludes(event):
                    continue

                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    continue

    yield message_handler


_distributor_task: Optional[asyncio.Task] = None
_distributor_started: Optional[asyncio.Event] = None


async def start_distributor():
    """Starts the distributor consumer as a global background task"""
    global _distributor_task
    global _distributor_started
    if _distributor_task:
        return

    _distributor_started = asyncio.Event()
    _distributor_task = asyncio.create_task(run_distributor(_distributor_started))
    await _distributor_started.wait()


async def stop_distributor():
    """Stops the distributor consumer global background task"""
    global _distributor_task
    global _distributor_started
    if not _distributor_task:
        return

    task = _distributor_task
    _distributor_task = None
    _distributor_started = None

    task.cancel()
    try:
        await asyncio.shield(task)
    except asyncio.CancelledError:
        pass


class Distributor:
    name: str = "Distributor"

    async def start(self):
        await start_distributor()
        try:
            await _distributor_task
        except asyncio.CancelledError:
            pass

    async def stop(self):
        await stop_distributor()


async def run_distributor(started: asyncio.Event):
    """Runs the distributor consumer forever until it is cancelled"""
    global _distributor_started
    async with messaging.ephemeral_subscription(
        topic="events",
    ) as create_consumer_kwargs:
        started.set()
        async with distributor() as handler:
            consumer = messaging.create_consumer(**create_consumer_kwargs)
            await consumer.run(
                handler=handler,
            )
