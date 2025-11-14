from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from prefect.server.concurrency.lease_storage import (
    ConcurrencyLeaseHolder,
    ConcurrencyLimitLeaseMetadata,
)
from prefect.server.concurrency.lease_storage import (
    ConcurrencyLeaseStorage as _ConcurrencyLeaseStorage,
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

    async def renew_lease(self, lease_id: UUID, ttl: timedelta) -> bool:
        """
        Atomically renew a concurrency lease by updating its expiration.

        Checks if the lease exists before updating the expiration index,
        preventing orphaned index entries.

        Args:
            lease_id: The ID of the lease to renew
            ttl: The new time-to-live duration

        Returns:
            True if the lease was renewed, False if it didn't exist
        """
        if lease_id not in self.leases:
            # Clean up any orphaned expiration entry
            self.expirations.pop(lease_id, None)
            return False

        self.expirations[lease_id] = datetime.now(timezone.utc) + ttl
        return True

    async def revoke_lease(self, lease_id: UUID) -> None:
        self.leases.pop(lease_id, None)
        self.expirations.pop(lease_id, None)

    async def read_active_lease_ids(
        self, limit: int = 100, offset: int = 0
    ) -> list[UUID]:
        now = datetime.now(timezone.utc)
        active_leases = [
            lease_id
            for lease_id, expiration in self.expirations.items()
            if expiration > now
        ]
        return active_leases[offset : offset + limit]

    async def read_expired_lease_ids(self, limit: int = 100) -> list[UUID]:
        now = datetime.now(timezone.utc)
        expired_leases = [
            lease_id
            for lease_id, expiration in self.expirations.items()
            if expiration < now
        ]
        return expired_leases[:limit]

    async def list_holders_for_limit(
        self, limit_id: UUID
    ) -> list[tuple[UUID, ConcurrencyLeaseHolder]]:
        """List all holders for a given concurrency limit."""
        now = datetime.now(timezone.utc)
        holders_with_leases: list[tuple[UUID, ConcurrencyLeaseHolder]] = []

        for lease_id, lease in self.leases.items():
            # Check if lease is active and for the specified limit
            if (
                limit_id in lease.resource_ids
                and self.expirations.get(lease_id, now) > now
                and lease.metadata
                and lease.metadata.holder
            ):
                holders_with_leases.append((lease.id, lease.metadata.holder))

        return holders_with_leases
