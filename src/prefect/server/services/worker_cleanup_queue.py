"""
The worker cleanup queue service. Handles cleanup message lease expiry.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from docket import Depends, Perpetual

from prefect.logging import get_logger
from prefect.server.services.perpetual_services import perpetual_service
from prefect.server.worker_communication.cleanup_queue import (
    CleanupQueueLeaseExpiryResult,
    WorkerCleanupQueue,
    get_worker_cleanup_queue,
)
from prefect.settings.context import get_current_settings

logger: logging.Logger = get_logger(__name__)


@perpetual_service(
    enabled_getter=lambda: (
        get_current_settings().server.services.worker_cleanup_queue.enabled
    ),
)
async def expire_worker_cleanup_leases(
    cleanup_queue: WorkerCleanupQueue = Depends(get_worker_cleanup_queue),
    perpetual: Perpetual = Perpetual(
        automatic=False,
        every=timedelta(
            seconds=get_current_settings().server.services.worker_cleanup_queue.loop_seconds
        ),
    ),
) -> CleanupQueueLeaseExpiryResult:
    """
    Expire overdue worker cleanup reservations and apply retry/DLQ policy.
    """
    settings = get_current_settings().server.services.worker_cleanup_queue
    result = await cleanup_queue.expire_leases(limit=settings.batch_size)

    if result.redelivered or result.dead_lettered:
        logger.info(
            "Expired worker cleanup leases: redelivered=%s dead_lettered=%s",
            len(result.redelivered),
            len(result.dead_lettered),
        )

    return result
