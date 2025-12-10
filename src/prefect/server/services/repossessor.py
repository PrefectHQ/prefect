"""
The Repossessor service. Responsible for revoking expired concurrency leases.

This service has been converted from a LoopService to docket Perpetual functions.
"""

from datetime import datetime, timedelta, timezone
from logging import Logger

from docket import CurrentDocket, Depends, Docket, Perpetual

from prefect.logging import get_logger
from prefect.server.concurrency.lease_storage import (
    get_concurrency_lease_storage,
)
from prefect.server.database import (
    PrefectDBInterface,
    provide_database_interface,
)
from prefect.server.models.concurrency_limits_v2 import bulk_decrement_active_slots
from prefect.server.services.perpetual_services import perpetual_service
from prefect.settings.context import get_current_settings

logger: Logger = get_logger(__name__)


# Docket task function for revoking a single expired lease
async def revoke_expired_lease(
    expired_lease_id: str,
    *,
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> None:
    """Revoke a single expired concurrency lease (docket task)."""
    concurrency_lease_storage = get_concurrency_lease_storage()

    expired_lease = await concurrency_lease_storage.read_lease(expired_lease_id)
    if expired_lease is None or expired_lease.metadata is None:
        logger.warning(
            f"Lease {expired_lease_id} should be revoked but was not found or has no metadata"
        )
        return

    async with db.session_context() as session:
        occupancy_seconds = (
            datetime.now(timezone.utc) - expired_lease.created_at
        ).total_seconds()

        logger.info(
            f"Revoking lease {expired_lease_id} for {len(expired_lease.resource_ids)} "
            f"concurrency limits with {expired_lease.metadata.slots} slots"
        )

        await bulk_decrement_active_slots(
            session=session,
            concurrency_limit_ids=expired_lease.resource_ids,
            slots=expired_lease.metadata.slots,
            occupancy_seconds=occupancy_seconds,
        )
        await concurrency_lease_storage.revoke_lease(expired_lease_id)
        await session.commit()


# Perpetual monitor task for finding expired leases (find and flood pattern)
@perpetual_service(
    settings_getter=lambda: get_current_settings().server.services.repossessor,
)
async def monitor_expired_leases(
    docket: Docket = CurrentDocket(),
    perpetual: Perpetual = Perpetual(
        automatic=True,
        every=timedelta(
            seconds=get_current_settings().server.services.repossessor.loop_seconds
        ),
    ),
) -> None:
    """Monitor for expired concurrency leases and schedule revocation tasks."""
    concurrency_lease_storage = get_concurrency_lease_storage()
    expired_lease_ids = await concurrency_lease_storage.read_expired_lease_ids()

    if expired_lease_ids:
        logger.info(f"Found {len(expired_lease_ids)} expired leases")
        for expired_lease_id in expired_lease_ids:
            await docket.add(revoke_expired_lease)(expired_lease_id)
        logger.info(f"Scheduled {len(expired_lease_ids)} lease revocation tasks.")
