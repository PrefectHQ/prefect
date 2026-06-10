"""
The cleanup reconciler service. Handles cleanup message lease expiry.
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

_service_cleanup_queue: WorkerCleanupQueue | None = None
_service_cleanup_queue_storage: str | None = None


def _get_service_worker_cleanup_queue() -> WorkerCleanupQueue:
    global _service_cleanup_queue, _service_cleanup_queue_storage

    storage = get_current_settings().server.worker_channel.cleanup_queue_storage
    if _service_cleanup_queue is None or _service_cleanup_queue_storage != storage:
        _service_cleanup_queue = get_worker_cleanup_queue()
        _service_cleanup_queue_storage = storage

    return _service_cleanup_queue


@perpetual_service(
    enabled_getter=lambda: (
        get_current_settings().server.services.cleanup_reconciler.enabled
    ),
)
async def reconcile_cleanup_delivery(
    cleanup_queue: WorkerCleanupQueue = Depends(_get_service_worker_cleanup_queue),
    perpetual: Perpetual = Perpetual(
        automatic=True,
        every=timedelta(
            seconds=get_current_settings().server.services.cleanup_reconciler.loop_seconds
        ),
    ),
) -> CleanupQueueLeaseExpiryResult:
    """
    Reconcile overdue cleanup reservations and apply retry/DLQ policy.
    """
    settings = get_current_settings().server.services.cleanup_reconciler
    result = await cleanup_queue.expire_leases(limit=settings.batch_size)

    if result.redelivered or result.dead_lettered:
        logger.info(
            "Expired worker cleanup leases: redelivered=%s dead_lettered=%s",
            len(result.redelivered),
            len(result.dead_lettered),
        )

    return result
