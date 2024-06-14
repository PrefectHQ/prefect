import asyncio
from typing import Optional

from prefect.logging import get_logger
from prefect.server.events import triggers
from prefect.server.services.loop_service import LoopService
from prefect.server.utilities.messaging import create_consumer
from prefect.settings import PREFECT_EVENTS_PROACTIVE_GRANULARITY

logger = get_logger(__name__)


class ReactiveTriggers:
    """Runs the reactive triggers consumer"""

    name: str = "ReactiveTriggers"

    consumer_task: Optional[asyncio.Task] = None

    async def start(self):
        assert self.consumer_task is None, "Reactive triggers already started"
        self.consumer = create_consumer("events")

        async with triggers.consumer() as handler:
            self.consumer_task = asyncio.create_task(self.consumer.run(handler))
            logger.debug("Reactive triggers started")

            try:
                await self.consumer_task
            except asyncio.CancelledError:
                pass

    async def stop(self):
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
    def __init__(self, loop_seconds: Optional[float] = None, **kwargs):
        super().__init__(
            loop_seconds=(
                loop_seconds
                or PREFECT_EVENTS_PROACTIVE_GRANULARITY.value().total_seconds()
            ),
            **kwargs,
        )

    async def run_once(self):
        await triggers.evaluate_proactive_triggers()
