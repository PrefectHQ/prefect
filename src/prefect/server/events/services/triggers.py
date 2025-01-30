from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, NoReturn, Optional

from prefect.logging import get_logger
from prefect.server.events import triggers
from prefect.server.services.base import Service
from prefect.server.services.loop_service import LoopService
from prefect.server.utilities.messaging import Consumer, create_consumer
from prefect.settings import PREFECT_EVENTS_PROACTIVE_GRANULARITY

if TYPE_CHECKING:
    import logging

logger: "logging.Logger" = get_logger(__name__)


class ReactiveTriggers(Service):
    """Runs the reactive triggers consumer"""

    name: str = "ReactiveTriggers"

    consumer_task: asyncio.Task[None] | None = None

    async def start(self) -> NoReturn:
        assert self.consumer_task is None, "Reactive triggers already started"
        self.consumer: Consumer = create_consumer("events")

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


class ProactiveTriggers(LoopService):
    """A loop service that runs the proactive triggers consumer"""

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
