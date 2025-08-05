from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import RedisError

from prefect.server.concurrency.lease_storage import (
    ConcurrencyLeaseStorage as _ConcurrencyLeaseStorage,
)
from prefect.server.concurrency.lease_storage import (
    ConcurrencyLimitLeaseMetadata,
)
from prefect.server.utilities.leasing import ResourceLease
from prefect_redis.client import get_async_redis_client

logger = logging.getLogger(__name__)


class ConcurrencyLeaseStorage(_ConcurrencyLeaseStorage):
    """
    A Redis-based concurrency lease storage implementation.
    """

    def __init__(self, redis_client: Redis | None = None):
        self.redis_client = redis_client or get_async_redis_client()
        self.lease_prefix = "prefect:concurrency:lease:"
        self.expiration_prefix = "prefect:concurrency:expiration:"

    def _lease_key(self, lease_id: UUID) -> str:
        """Generate Redis key for a lease."""
        return f"{self.lease_prefix}{lease_id}"

    def _expiration_key(self, lease_id: UUID) -> str:
        """Generate Redis key for lease expiration."""
        return f"{self.expiration_prefix}{lease_id}"

    def _serialize_lease(
        self, lease: ResourceLease[ConcurrencyLimitLeaseMetadata]
    ) -> str:
        """Serialize a lease to JSON."""
        data = {
            "id": str(lease.id),
            "resource_ids": [str(rid) for rid in lease.resource_ids],
            "expiration": lease.expiration.isoformat(),
            "created_at": lease.created_at.isoformat(),
            "metadata": {"slots": lease.metadata.slots} if lease.metadata else None,
        }
        return json.dumps(data)

    def _deserialize_lease(
        self, data: str
    ) -> ResourceLease[ConcurrencyLimitLeaseMetadata]:
        """Deserialize a lease from JSON."""
        lease_data = json.loads(data)
        metadata = None
        if lease_data["metadata"]:
            metadata = ConcurrencyLimitLeaseMetadata(
                slots=lease_data["metadata"]["slots"]
            )

        return ResourceLease(
            id=UUID(lease_data["id"]),
            resource_ids=[UUID(rid) for rid in lease_data["resource_ids"]],
            expiration=datetime.fromisoformat(lease_data["expiration"]),
            created_at=datetime.fromisoformat(lease_data["created_at"]),
            metadata=metadata,
        )

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

        try:
            lease_key = self._lease_key(lease.id)

            # Store the lease data
            serialized_lease = self._serialize_lease(lease)
            await self.redis_client.set(lease_key, serialized_lease)

            # Store expiration timestamp for efficient expiration queries
            await self.redis_client.zadd(
                "prefect:concurrency:expirations",
                {str(lease.id): expiration.timestamp()},
            )

            return lease
        except RedisError as e:
            logger.error(f"Failed to create lease {lease.id}: {e}")
            raise

    async def read_lease(
        self, lease_id: UUID
    ) -> ResourceLease[ConcurrencyLimitLeaseMetadata] | None:
        try:
            lease_key = self._lease_key(lease_id)
            data = await self.redis_client.get(lease_key)

            if data is None:
                return None

            return self._deserialize_lease(data)
        except RedisError as e:
            logger.error(f"Failed to read lease {lease_id}: {e}")
            raise

    async def renew_lease(self, lease_id: UUID, ttl: timedelta) -> None:
        try:
            lease_key = self._lease_key(lease_id)

            # Get the existing lease
            data = await self.redis_client.get(lease_key)
            if data is None:
                return

            lease = self._deserialize_lease(data)

            # Update expiration
            new_expiration = datetime.now(timezone.utc) + ttl
            lease.expiration = new_expiration

            # Store updated lease
            serialized_lease = self._serialize_lease(lease)
            await self.redis_client.set(lease_key, serialized_lease)

            # Update expiration in sorted set
            await self.redis_client.zadd(
                "prefect:concurrency:expirations",
                {str(lease_id): new_expiration.timestamp()},
            )
        except RedisError as e:
            logger.error(f"Failed to renew lease {lease_id}: {e}")
            raise

    async def revoke_lease(self, lease_id: UUID) -> None:
        try:
            lease_key = self._lease_key(lease_id)

            # Remove lease data
            await self.redis_client.delete(lease_key)

            # Remove from expiration tracking
            await self.redis_client.zrem(
                "prefect:concurrency:expirations", str(lease_id)
            )
        except RedisError as e:
            logger.error(f"Failed to revoke lease {lease_id}: {e}")
            raise

    async def read_active_lease_ids(self, limit: int = 100) -> list[UUID]:
        try:
            now = datetime.now(timezone.utc).timestamp()

            # Get lease IDs that expire after now (active leases)
            active_lease_ids = await self.redis_client.zrangebyscore(
                "prefect:concurrency:expirations", now, "+inf", start=0, num=limit
            )

            return [UUID(lease_id) for lease_id in active_lease_ids]
        except RedisError as e:
            logger.error(f"Failed to read active lease IDs: {e}")
            raise

    async def read_expired_lease_ids(self, limit: int = 100) -> list[UUID]:
        try:
            now = datetime.now(timezone.utc).timestamp()

            # Get lease IDs that expire before now (expired leases)
            expired_lease_ids = await self.redis_client.zrangebyscore(
                "prefect:concurrency:expirations", "-inf", now, start=0, num=limit
            )

            return [UUID(lease_id) for lease_id in expired_lease_ids]
        except RedisError as e:
            logger.error(f"Failed to read expired lease IDs: {e}")
            raise
