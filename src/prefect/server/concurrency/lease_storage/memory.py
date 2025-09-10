from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from prefect.server.concurrency.lease_storage import (
    ConcurrencyLeaseStorage as _ConcurrencyLeaseStorage,
)
from prefect.server.concurrency.lease_storage import (
    ConcurrencyLimitLeaseMetadata,
)
from prefect.server.utilities.leasing import ResourceLease


class ConcurrencyLeaseStorage(_ConcurrencyLeaseStorage):
    """
    A singleton concurrency lease storage implementation that stores leases in memory.
    """

    _instance: "ConcurrencyLeaseStorage | None" = None
    _initialized: bool = False

    def __new__(cls) -> "ConcurrencyLeaseStorage":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self.__class__._initialized:
            return

        self.leases: dict[UUID, ResourceLease[ConcurrencyLimitLeaseMetadata]] = {}
        self.expirations: dict[UUID, datetime] = {}
        self.__class__._initialized = True

    async def create_lease(
        self,
        resource_ids: list[UUID],
        ttl: timedelta,
        metadata: ConcurrencyLimitLeaseMetadata | None = None,
    ) -> ResourceLease[ConcurrencyLimitLeaseMetadata]:
        expiration = datetime.now(timezone.utc) + ttl
        lease = ResourceLease(
            resource_ids=resource_ids, metadata=metadata, expiration=expiration
        )
        self.leases[lease.id] = lease
        self.expirations[lease.id] = expiration
        return lease

    async def read_lease(
        self, lease_id: UUID
    ) -> ResourceLease[ConcurrencyLimitLeaseMetadata] | None:
        return self.leases.get(lease_id)

    async def renew_lease(self, lease_id: UUID, ttl: timedelta) -> None:
        self.expirations[lease_id] = datetime.now(timezone.utc) + ttl

    async def revoke_lease(self, lease_id: UUID) -> None:
        self.leases.pop(lease_id, None)
        self.expirations.pop(lease_id, None)

    async def read_active_lease_ids(self, limit: int = 100) -> list[UUID]:
        now = datetime.now(timezone.utc)
        active_leases = [
            lease_id
            for lease_id, expiration in self.expirations.items()
            if expiration > now
        ]
        return active_leases[:limit]

    async def read_expired_lease_ids(self, limit: int = 100) -> list[UUID]:
        now = datetime.now(timezone.utc)
        expired_leases = [
            lease_id
            for lease_id, expiration in self.expirations.items()
            if expiration < now
        ]
        return expired_leases[:limit]

    # Optional helper used by the API layer when present
    async def list_holders_for_limit(self, limit_id: UUID) -> list[dict]:
        now = datetime.now(timezone.utc)
        out: list[dict] = []
        for lease_id, lease in self.leases.items():
            exp = self.expirations.get(lease_id)
            if not exp or exp <= now:
                continue
            if limit_id not in lease.resource_ids:
                continue
            holder = getattr(lease.metadata, "holder", None) if lease.metadata else None
            if holder is not None and hasattr(holder, "model_dump"):
                holder = holder.model_dump(mode="json")  # type: ignore[attr-defined]
            if isinstance(holder, dict) and holder.get("type") and holder.get("id"):
                out.append(
                    {
                        "holder": holder,
                        "slots": getattr(lease.metadata, "slots", 1)
                        if lease.metadata
                        else 1,
                    }
                )
        return out
