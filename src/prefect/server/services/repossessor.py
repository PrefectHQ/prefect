"""
The Repossessor service. Handles reconciliation of expired concurrency leases.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from docket import CurrentDocket, Depends, Docket, Logged, Perpetual

from prefect.logging import get_logger
from prefect.server.concurrency.lease_storage import (
    REVOCATION_CLAIM_TTL_SECONDS,
    ConcurrencyLeaseStorage,
    get_concurrency_lease_storage,
)
from prefect.server.database import PrefectDBInterface, provide_database_interface
from prefect.server.models.concurrency_limits_v2 import bulk_decrement_active_slots
from prefect.server.services.perpetual_services import perpetual_service
from prefect.settings.context import get_current_settings

logger: logging.Logger = get_logger(__name__)


async def _maintain_revocation_claim(
    lease_storage: ConcurrencyLeaseStorage,
    lease_id: UUID,
    revocation_token: str,
    claim_lost: asyncio.Event,
) -> None:
    try:
        while True:
            await asyncio.sleep(REVOCATION_CLAIM_TTL_SECONDS / 3)
            if not await lease_storage.renew_lease_revocation(
                lease_id, revocation_token
            ):
                claim_lost.set()
                return
    except asyncio.CancelledError:
        raise
    except Exception:
        claim_lost.set()


async def revoke_expired_lease(
    lease_id: Annotated[UUID, Logged],
    *,
    db: PrefectDBInterface = Depends(provide_database_interface),
    lease_storage: ConcurrencyLeaseStorage = Depends(get_concurrency_lease_storage),
) -> None:
    """Revoke a single expired lease (docket task)."""
    expired_lease = await lease_storage.begin_lease_revocation(lease_id)
    if expired_lease is None:
        if await lease_storage.read_lease(lease_id) is not None:
            return
        # The lease itself is gone, but storage may still hold an expiration
        # entry for it; revoking clears that entry so the lease stops being
        # reported as expired on every pass.
        await lease_storage.revoke_lease(lease_id)
        logger.warning(f"Lease {lease_id} should be revoked but was not found")
        return

    if expired_lease.metadata is None:
        await lease_storage.cancel_lease_revocation(
            lease_id, expired_lease.revocation_token
        )
        logger.warning(f"Lease {lease_id} should be revoked but has no metadata")
        return

    if expired_lease.expiration > datetime.now(timezone.utc):
        await lease_storage.cancel_lease_revocation(
            lease_id, expired_lease.revocation_token
        )
        logger.info(
            f"Lease {lease_id} was renewed after being listed as expired; skipping revocation"
        )
        return

    occupancy_seconds = (
        datetime.now(timezone.utc) - expired_lease.created_at
    ).total_seconds()

    logger.info(
        f"Revoking lease {lease_id} for {len(expired_lease.resource_ids)} "
        f"concurrency limits with {expired_lease.metadata.slots} slots"
    )

    claim_lost = asyncio.Event()
    claim_task = None
    if expired_lease.revocation_token:
        claim_task = asyncio.create_task(
            _maintain_revocation_claim(
                lease_storage,
                lease_id,
                expired_lease.revocation_token,
                claim_lost,
            )
        )

    try:
        async with db.session_context(begin_transaction=True) as session:
            await bulk_decrement_active_slots(
                session=session,
                concurrency_limit_ids=expired_lease.resource_ids,
                slots=expired_lease.metadata.slots,
                occupancy_seconds=occupancy_seconds,
            )
            if claim_lost.is_set():
                raise RuntimeError("revocation claim is no longer owned")
            await lease_storage.revoke_lease(
                lease_id, expired_lease.revocation_token
            )
    except Exception:
        await lease_storage.cancel_lease_revocation(
            lease_id, expired_lease.revocation_token
        )
        raise
    finally:
        if claim_task:
            claim_task.cancel()
            with suppress(asyncio.CancelledError):
                await claim_task


@perpetual_service(
    enabled_getter=lambda: get_current_settings().server.services.repossessor.enabled,
)
async def monitor_expired_leases(
    docket: Docket = CurrentDocket(),
    lease_storage: ConcurrencyLeaseStorage = Depends(get_concurrency_lease_storage),
    perpetual: Perpetual = Perpetual(
        automatic=True,
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
