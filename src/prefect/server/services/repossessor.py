from datetime import datetime, timezone

from prefect.server.concurrency.lease_storage import (
    ConcurrencyLeaseStorage,
    get_concurrency_lease_storage,
)
from prefect.server.database.dependencies import provide_database_interface
from prefect.server.models.concurrency_limits_v2 import bulk_decrement_active_slots
from prefect.server.services.base import LoopService
from prefect.settings.context import get_current_settings
from prefect.settings.models.server.services import ServicesBaseSetting


class Repossessor(LoopService):
    """
    Handles the reconciliation of expired leases; no tow truck dependency.
    """

    def __init__(self):
        super().__init__(
            loop_seconds=get_current_settings().server.services.repossessor.loop_seconds,
        )
        self.concurrency_lease_storage: ConcurrencyLeaseStorage = (
            get_concurrency_lease_storage()
        )

    @classmethod
    def service_settings(cls) -> ServicesBaseSetting:
        return get_current_settings().server.services.repossessor

    async def run_once(self) -> None:
        expired_lease_ids = (
            await self.concurrency_lease_storage.read_expired_lease_ids()
        )
        if expired_lease_ids:
            self.logger.info(f"Revoking {len(expired_lease_ids)} expired leases")

        db = provide_database_interface()
        async with db.session_context() as session:
            for expired_lease_id in expired_lease_ids:
                expired_lease = await self.concurrency_lease_storage.read_lease(
                    expired_lease_id
                )
                if expired_lease is None or expired_lease.metadata is None:
                    self.logger.warning(
                        f"Lease {expired_lease_id} should be revoked but was not found or has no metadata"
                    )
                    continue
                occupancy_seconds = (
                    datetime.now(timezone.utc) - expired_lease.created_at
                ).total_seconds()
                self.logger.info(
                    f"Revoking lease {expired_lease_id} for {len(expired_lease.resource_ids)} concurrency limits with {expired_lease.metadata.slots} slots"
                )
                await bulk_decrement_active_slots(
                    session=session,
                    concurrency_limit_ids=expired_lease.resource_ids,
                    slots=expired_lease.metadata.slots,
                    occupancy_seconds=occupancy_seconds,
                )
                await self.concurrency_lease_storage.revoke_lease(expired_lease_id)

                await session.commit()
