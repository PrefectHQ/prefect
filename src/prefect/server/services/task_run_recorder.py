import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from prefect.logging import get_logger
from prefect.server.events.schemas.events import ReceivedEvent
from prefect.server.utilities.messaging import Message, MessageHandler, create_consumer

logger = get_logger(__name__)


@asynccontextmanager
async def consumer() -> AsyncGenerator[MessageHandler, None]:
    async def message_handler(message: Message):
        event: ReceivedEvent = ReceivedEvent.model_validate_json(message.data)

        if not event.event.startswith("prefect.task-run"):
            return

        if not event.resource.get("prefect.orchestration") == "client":
            return

        logger.info(
            f"Received event: {event.event} with id: {event.id} for resource: {event.resource.get('prefect.resource.id')}"
        )

    yield message_handler


class TaskRunRecorder:
    """A service to record task run and task run states from events."""

    name: str = "TaskRunRecorder"

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
        assert self.consumer_task is None, "TaskRunRecorder already started"
        self.consumer = create_consumer("events")

        async with consumer() as handler:
            self.consumer_task = asyncio.create_task(self.consumer.run(handler))
            logger.debug("TaskRunRecorder started")
            self.started_event.set()

            try:
                await self.consumer_task
            except asyncio.CancelledError:
                pass

    async def stop(self):
        assert self.consumer_task is not None, "Logger not started"
        self.consumer_task.cancel()
        try:
            await self.consumer_task
        except asyncio.CancelledError:
            pass
        finally:
            self.consumer_task = None
        logger.debug("TaskRunRecorder stopped")
