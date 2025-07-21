from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from functools import partial
from typing import Generic, Protocol, TypeVar
from uuid import UUID, uuid4

T = TypeVar("T")


@dataclass
class ResourceLease(Generic[T]):
    resource_ids: list[UUID]
    expiration: datetime
    created_at: datetime = field(default_factory=partial(datetime.now, timezone.utc))
    id: UUID = field(default_factory=uuid4)
    metadata: T | None = None


class LeaseStorage(Protocol[T]):
    async def create_lease(
        self, resource_ids: list[UUID], ttl: timedelta, metadata: T | None = None
    ) -> ResourceLease[T]:
        """
        Create a new resource lease.

        Args:
            resource_ids: The IDs of the resources that the lease is associated with.
            ttl: How long the lease should initially be held for.
            metadata: Additional metadata associated with the lease.

        Returns:
            A ResourceLease object representing the lease.
        """
        ...

    async def read_lease(self, lease_id: UUID) -> ResourceLease[T] | None:
        """
        Read a resource lease.

        Args:
            lease_id: The ID of the lease to read.

        Returns:
            A ResourceLease object representing the lease, or None if not found.
        """
        ...

    async def renew_lease(self, lease_id: UUID, ttl: timedelta) -> None:
        """
        Renew a resource lease.

        Args:
            lease_id: The ID of the lease to renew.
            ttl: The new amount of time the lease should be held for.
        """
        ...

    async def revoke_lease(self, lease_id: UUID) -> None:
        """
        Release a resource lease by removing it from list of active leases.

        Args:
            lease_id: The ID of the lease to release.
        """
        ...

    async def read_expired_lease_ids(self, limit: int = 100) -> list[UUID]:
        """
        Read the IDs of expired leases.

        Args:
            limit: The maximum number of expired leases to read.

        Returns:
            A list of UUIDs representing the expired leases.
        """
        ...
