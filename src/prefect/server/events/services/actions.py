import asyncio
from typing import Optional

from prefect.logging import get_logger
from prefect.server.events import actions
from prefect.server.utilities.messaging import create_consumer

logger = get_logger(__name__)


class Actions:
    """Runs actions triggered by Automatinos"""

    name: str = "Actions"

    consumer_task: Optional[asyncio.Task] = None

    async def start(self):
        assert self.consumer_task is None, "Actions already started"
        self.consumer = create_consumer("actions")

        async with actions.consumer() as handler:
            self.consumer_task = asyncio.create_task(self.consumer.run(handler))
            logger.debug("Actions started")

            try:
                await self.consumer_task
            except asyncio.CancelledError:
                pass

    async def stop(self):
        assert self.consumer_task is not None, "Actions not started"
        self.consumer_task.cancel()
        try:
            await self.consumer_task
        except asyncio.CancelledError:
            pass
        finally:
            self.consumer_task = None
        logger.debug("Actions stopped")
