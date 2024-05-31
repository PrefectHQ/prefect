import asyncio
from typing import Optional

import pendulum
import rich

from prefect.logging import get_logger
from prefect.server.events.schemas.events import ReceivedEvent
from prefect.server.utilities.messaging import Message, create_consumer

logger = get_logger(__name__)


class EventLogger:
    """A debugging service that logs events to the console as they arrive."""

    name: str = "EventLogger"

    consumer_task: Optional[asyncio.Task] = None

    async def start(self):
        assert self.consumer_task is None, "Logger already started"
        self.consumer = create_consumer("events")

        console = rich.console.Console()

        async def handler(message: Message):
            now = pendulum.now("UTC")
            event: ReceivedEvent = ReceivedEvent.model_validate_json(message.data)

            console.print(
                "Event:",
                str(event.id).partition("-")[0],
                f"{event.occurred.isoformat()}",
                f" ({(event.occurred - now).total_seconds():>6,.2f})",
                f"\\[[bold green]{event.event}[/]]",
                event.resource.id,
            )
            console.file.flush()

        self.consumer_task = asyncio.create_task(self.consumer.run(handler))
        logger.debug("Event logger started")

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
        logger.debug("Event logger stopped")
