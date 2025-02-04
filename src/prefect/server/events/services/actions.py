from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, NoReturn

from prefect.logging import get_logger
from prefect.server.events import actions
from prefect.server.services.base import RunInAllServers, Service
from prefect.server.utilities.messaging import Consumer, create_consumer
from prefect.settings.context import get_current_settings
from prefect.settings.models.server.services import ServicesBaseSetting

if TYPE_CHECKING:
    import logging

logger: "logging.Logger" = get_logger(__name__)


class Actions(RunInAllServers, Service):
    """Runs the actions triggered by automations"""

    consumer_task: asyncio.Task[None] | None = None

    @classmethod
    def service_settings(cls) -> ServicesBaseSetting:
        return get_current_settings().server.services.triggers

    async def start(self) -> NoReturn:
        assert self.consumer_task is None, "Actions already started"
        self.consumer: Consumer = create_consumer("actions")

        async with actions.consumer() as handler:
            self.consumer_task = asyncio.create_task(self.consumer.run(handler))
            logger.debug("Actions started")

            try:
                await self.consumer_task
            except asyncio.CancelledError:
                pass

    async def stop(self) -> None:
        assert self.consumer_task is not None, "Actions not started"
        self.consumer_task.cancel()
        try:
            await self.consumer_task
        except asyncio.CancelledError:
            pass
        finally:
            self.consumer_task = None
        logger.debug("Actions stopped")
