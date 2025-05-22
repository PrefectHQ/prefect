from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, NoReturn

import rich

from prefect.logging import get_logger
from prefect.server.events.schemas.events import ReceivedEvent
from prefect.server.services.base import RunInAllServers, Service
from prefect.server.utilities.messaging import Consumer, Message, create_consumer
from prefect.server.utilities.messaging._consumer_names import (
    generate_unique_consumer_name,
)
from prefect.settings.context import get_current_settings
from prefect.settings.models.server.services import ServicesBaseSetting
from prefect.types._datetime import now

if TYPE_CHECKING:
    import logging

logger: "logging.Logger" = get_logger(__name__)


class EventLogger(RunInAllServers, Service):
    """A debugging service that logs events to the console as they arrive."""

    consumer_task: asyncio.Task[None] | None = None

    @classmethod
    def service_settings(cls) -> ServicesBaseSetting:
        return get_current_settings().server.services.event_logger

    async def start(self) -> NoReturn:
        assert self.consumer_task is None, "Logger already started"
        self.consumer: Consumer = create_consumer(
            "events",
            group="event-logger",
            name=generate_unique_consumer_name("event-logger"),
        )

        console = rich.console.Console()

        async def handler(message: Message):
            right_now = now("UTC")
            event: ReceivedEvent = ReceivedEvent.model_validate_json(message.data)

            console.print(
                "Event:",
                str(event.id).partition("-")[0],
                f"{event.occurred.isoformat()}",
                f" ({(event.occurred - right_now).total_seconds():>6,.2f})",
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

    async def stop(self) -> None:
        assert self.consumer_task is not None, "Logger not started"
        self.consumer_task.cancel()
        try:
            await self.consumer_task
        except asyncio.CancelledError:
            pass
        finally:
            self.consumer_task = None
        logger.debug("Event logger stopped")
