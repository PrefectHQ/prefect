import asyncio
from typing import Optional

import rich

from prefect.logging import get_logger
from prefect.server.events.schemas.automations import TriggeredAction
from prefect.server.utilities.messaging import Message, create_consumer

logger = get_logger(__name__)


class ActionLogger:
    """A debugging service that logs actions to the console as they arrive."""

    name: str = "ActionLogger"

    consumer_task: Optional[asyncio.Task] = None

    async def start(self):
        assert self.consumer_task is None, "Logger already started"
        self.consumer = create_consumer("actions")

        console = rich.console.Console()

        async def handler(message: Message):
            triggered_action: TriggeredAction = TriggeredAction.parse_raw(message.data)
            console.print("Action:", triggered_action.action.type)
            console.file.flush()

        self.consumer_task = asyncio.create_task(self.consumer.run(handler))
        logger.debug("Action logger started")

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
        logger.debug("Action logger stopped")
