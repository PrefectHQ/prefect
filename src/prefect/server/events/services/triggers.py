from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, NoReturn, Optional

from prefect.logging import get_logger
from prefect.server.events import triggers
from prefect.server.services.base import LoopService, RunInAllServers, Service
from prefect.server.utilities.messaging import Consumer, create_consumer
from prefect.settings import PREFECT_EVENTS_PROACTIVE_GRANULARITY
from prefect.settings.context import get_current_settings
from prefect.settings.models.server.services import ServicesBaseSetting

if TYPE_CHECKING:
    import logging


logger: "logging.Logger" = get_logger(__name__)


class ReactiveTriggers(RunInAllServers, Service):
    """Evaluates reactive automation triggers and listens for automation changes"""

    event_consumer_task: asyncio.Task[None] | None = None
    automation_notification_consumer_task: asyncio.Task[None] | None = None

    event_consumer: Consumer | None = None
    automation_notification_consumer: Consumer | None = None

    @classmethod
    def service_settings(cls) -> ServicesBaseSetting:
        return get_current_settings().server.services.triggers

    async def start(self) -> NoReturn:
        assert self.event_consumer_task is None, "Reactive triggers event consumer already started"
        assert self.automation_notification_consumer_task is None, (
            "Reactive triggers automation notification consumer already started"
        )

        self.event_consumer = create_consumer("events")
        self.automation_notification_consumer = create_consumer(
            "automations-notifications"
        )

        async with triggers.consumer() as event_handler, triggers.automations_notification_consumer() as automation_notification_handler:
            self.event_consumer_task = asyncio.create_task(
                self.event_consumer.run(event_handler)
            )
            self.automation_notification_consumer_task = asyncio.create_task(
                self.automation_notification_consumer.run(automation_notification_handler)
            )

            logger.debug("Reactive triggers service started with both consumers")

            try:
                # Gather will propagate cancellations to both tasks
                await asyncio.gather(
                    self.event_consumer_task,
                    self.automation_notification_consumer_task,
                )
            except asyncio.CancelledError:
                logger.debug("Reactive triggers service cancellation received")
            finally:
                logger.debug("Reactive triggers service shutting down consumers")

    async def stop(self) -> None:
        running_tasks = []
        if self.event_consumer_task:
            if not self.event_consumer_task.done():
                self.event_consumer_task.cancel()
            running_tasks.append(self.event_consumer_task)
            self.event_consumer_task = None

        if self.automation_notification_consumer_task:
            if not self.automation_notification_consumer_task.done():
                self.automation_notification_consumer_task.cancel()
            running_tasks.append(self.automation_notification_consumer_task)
            self.automation_notification_consumer_task = None
        
        if not running_tasks:
            logger.debug("Reactive triggers service had no running tasks to stop.")
            return

        logger.debug(f"Stopping {len(running_tasks)} consumer tasks...")
        try:
            await asyncio.gather(*running_tasks, return_exceptions=True)
        except asyncio.CancelledError:
            logger.debug("Consumer tasks cancelled during stop.")
        
        self.event_consumer = None
        self.automation_notification_consumer = None
        logger.debug("Reactive triggers service stopped")


class ProactiveTriggers(RunInAllServers, LoopService):
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
