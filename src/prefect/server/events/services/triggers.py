from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, NoReturn

from docket import Perpetual

from prefect.logging import get_logger
from prefect.server.events import triggers
from prefect.server.services.base import RunInEphemeralServers, Service
from prefect.server.services.perpetual_services import perpetual_service
from prefect.server.utilities.messaging import Consumer, create_consumer
from prefect.server.utilities.messaging._consumer_names import (
    generate_unique_consumer_name,
)
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
            "events",
            group="reactive-triggers",
            name=consumer_name,
            read_batch_size=self.service_settings().read_batch_size,
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
            await self.consumer.cleanup()
            self.consumer_task = None
        logger.debug("Reactive triggers stopped")


@perpetual_service(
    enabled_getter=lambda: get_current_settings().server.services.triggers.enabled,
    run_in_ephemeral=True,
)
async def evaluate_proactive_triggers_periodic(
    perpetual: Perpetual = Perpetual(
        automatic=True,
        every=get_current_settings().server.events.proactive_granularity,
    ),
) -> None:
    """Evaluate proactive automation triggers on a periodic schedule."""
    await triggers.evaluate_proactive_triggers()
