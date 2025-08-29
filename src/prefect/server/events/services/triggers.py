from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, NoReturn, Optional

from prefect.logging import get_logger
from prefect.server.events import triggers
from prefect.server.services.base import LoopService, RunInEphemeralServers, Service
from prefect.server.utilities.messaging import Consumer, create_consumer
from prefect.server.utilities.messaging._consumer_names import (
    generate_unique_consumer_name,
)
from prefect.settings import PREFECT_EVENTS_PROACTIVE_GRANULARITY
from prefect.settings.context import get_current_settings
from prefect.settings.models.server.services import ServicesBaseSetting

if TYPE_CHECKING:
    import logging


logger: "logging.Logger" = get_logger(__name__)


class ReactiveTriggers(RunInEphemeralServers, Service):
    """Evaluates reactive automation triggers"""

    consumer_task: asyncio.Task[None] | None = None

    @classmethod
    def service_settings(cls) -> ServicesBaseSetting:
        return get_current_settings().server.services.triggers

    async def start(self) -> NoReturn:
        assert self.consumer_task is None, "Reactive triggers already started"
        consumer_name = generate_unique_consumer_name("reactive-triggers")
        logger.info(
            f"ReactiveTriggers starting with unique consumer name: {consumer_name}"
        )
        self.consumer: Consumer = create_consumer(
            "events", group="reactive-triggers", name=consumer_name
        )

        async with triggers.consumer() as handler:
            self.consumer_task = asyncio.create_task(self.consumer.run(handler))
            logger.debug("Reactive triggers started")

            try:
                await self.consumer_task
            except asyncio.CancelledError:
                pass

    async def stop(self) -> None:
        assert self.consumer_task is not None, "Reactive triggers not started"
        self.consumer_task.cancel()
        try:
            await self.consumer_task
        except asyncio.CancelledError:
            pass
        finally:
            self.consumer_task = None
        logger.debug("Reactive triggers stopped")


class ProactiveTriggers(RunInEphemeralServers, LoopService):
    """Evaluates proactive automation triggers"""

    @classmethod
    def service_settings(cls) -> ServicesBaseSetting:
        return get_current_settings().server.services.triggers

    def __init__(self, loop_seconds: Optional[float] = None, **kwargs: Any):
        super().__init__(
            loop_seconds=(
                loop_seconds
                or PREFECT_EVENTS_PROACTIVE_GRANULARITY.value().total_seconds()
            ),
            **kwargs,
        )

    async def run_once(self) -> None:
        await triggers.evaluate_proactive_triggers()
