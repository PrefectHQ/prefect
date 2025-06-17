"""
Log messaging for streaming logs through the messaging system.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, AsyncGenerator

from prefect.logging import get_logger
from prefect.server.schemas.core import Log
from prefect.server.utilities import messaging
from prefect.settings.context import get_current_settings

if TYPE_CHECKING:
    import logging

logger: "logging.Logger" = get_logger(__name__)


@asynccontextmanager
async def create_log_publisher() -> AsyncGenerator[messaging.Publisher, None]:
    """
    Creates a publisher for sending logs to the messaging system.

    Returns:
        A messaging publisher configured for the "logs" topic
    """
    async with messaging.create_publisher(topic="logs") as publisher:
        yield publisher


async def publish_logs(logs: list[Log]) -> None:
    """
    Publishes logs to the messaging system.

    Args:
        logs: The logs to publish
    """
    if not get_current_settings().server.logs.stream_publishing_enabled:
        return

    if not logs:
        return

    async with create_log_publisher() as publisher:
        for log in logs:
            await publisher.publish_data(
                data=log.model_dump_json().encode(),
                attributes={"log_id": str(log.id)} if log.id else {},
            )
