from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from prefect.server.utilities.leasing import LeaseStorage, ResourceLease


@dataclass
class ConcurrencyLimitLeaseMetadata:
    slots: int


class ConcurrencyLeaseStorage(LeaseStorage[ConcurrencyLimitLeaseMetadata]):
    async def create_lease(
        self,
        resource_ids: list[UUID],
        ttl: timedelta,
        metadata: ConcurrencyLimitLeaseMetadata | None = None,
    ) -> ResourceLease[ConcurrencyLimitLeaseMetadata]: ...

    async def read_lease(
        self, lease_id: UUID
    ) -> ResourceLease[ConcurrencyLimitLeaseMetadata] | None: ...

    async def renew_lease(self, lease_id: UUID, ttl: timedelta) -> None: ...

    async def release_lease(self, lease_id: UUID) -> None: ...

    async def read_expired_lease_ids(self, limit: int = 100) -> list[UUID]: ...
