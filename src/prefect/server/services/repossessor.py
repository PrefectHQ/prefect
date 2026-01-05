"""
The Repossessor service. Handles reconciliation of expired concurrency leases.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from docket import CurrentDocket, Depends, Docket, Logged, Perpetual

from prefect.logging import get_logger
from prefect.server.concurrency.lease_storage import (
    ConcurrencyLeaseStorage,
    get_concurrency_lease_storage,
)
from prefect.server.database import PrefectDBInterface, provide_database_interface
from prefect.server.models.concurrency_limits_v2 import bulk_decrement_active_slots
from prefect.server.services.perpetual_services import perpetual_service
from prefect.settings.context import get_current_settings

logger: logging.Logger = get_logger(__name__)


async def revoke_expired_lease(
    lease_id: Annotated[UUID, Logged],
    *,
    db: PrefectDBInterface = Depends(provide_database_interface),
    lease_storage: ConcurrencyLeaseStorage = Depends(get_concurrency_lease_storage),
) -> None:
    """Revoke a single expired lease (docket task)."""
    expired_lease = await lease_storage.read_lease(lease_id)
    if expired_lease is None or expired_lease.metadata is None:
        logger.warning(
            f"Lease {lease_id} should be revoked but was not found or has no metadata"
        )
        return

    occupancy_seconds = (
        datetime.now(timezone.utc) - expired_lease.created_at
    ).total_seconds()

    logger.info(
        f"Revoking lease {lease_id} for {len(expired_lease.resource_ids)} "
        f"concurrency limits with {expired_lease.metadata.slots} slots"
    )

    async with db.session_context(begin_transaction=True) as session:
        await bulk_decrement_active_slots(
            session=session,
            concurrency_limit_ids=expired_lease.resource_ids,
            slots=expired_lease.metadata.slots,
            occupancy_seconds=occupancy_seconds,
        )
        await lease_storage.revoke_lease(lease_id)


@perpetual_service(
    enabled_getter=lambda: get_current_settings().server.services.repossessor.enabled,
)
async def monitor_expired_leases(
    docket: Docket = CurrentDocket(),
    lease_storage: ConcurrencyLeaseStorage = Depends(get_concurrency_lease_storage),
    perpetual: Perpetual = Perpetual(
        automatic=False,
        every=timedelta(
            seconds=get_current_settings().server.services.repossessor.loop_seconds
        ),
    ),
) -> None:
    """Monitor for expired leases and schedule revocation tasks."""
    expired_lease_ids = await lease_storage.read_expired_lease_ids()

    if expired_lease_ids:
        logger.info(f"Scheduling revocation of {len(expired_lease_ids)} expired leases")

    for lease_id in expired_lease_ids:
        await docket.add(revoke_expired_lease)(lease_id)
