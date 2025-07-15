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
        super().__init__()
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

        db = provide_database_interface()
        async with db.session_context() as session:
            for expired_lease_id in expired_lease_ids:
                expired_lease = await self.concurrency_lease_storage.read_lease(
                    expired_lease_id
                )
                if expired_lease is None or expired_lease.metadata is None:
                    continue
                await bulk_decrement_active_slots(
                    session=session,
                    concurrency_limit_ids=expired_lease.resource_ids,
                    slots=expired_lease.metadata.slots,
                )
                await self.concurrency_lease_storage.revoke_lease(expired_lease_id)
