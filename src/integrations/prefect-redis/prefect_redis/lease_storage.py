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
        self.base_prefix = "prefect:concurrency:"
        self.lease_prefix = f"{self.base_prefix}lease:"
        self.expirations_key = f"{self.base_prefix}expirations"
        self.expiration_prefix = f"{self.base_prefix}expiration:"

    def _lease_key(self, lease_id: UUID) -> str:
        """Generate Redis key for a lease."""
        return f"{self.lease_prefix}{lease_id}"

    def _expiration_key(self, lease_id: UUID) -> str:
        """Generate Redis key for lease expiration."""
        return f"{self.expiration_prefix}{lease_id}"

    @staticmethod
    def _holder_key(holder: dict | None) -> str | None:
        """Create a canonical holder key of form 'type:uuid'."""
        if not holder:
            return None
        h_type = holder.get("type")
        h_id = holder.get("id")
        if not h_type or not h_id:
            return None
        return f"{h_type}:{h_id}"

    @staticmethod
    def _limit_holders_key(limit_id: UUID) -> str:
        return f"prefect:concurrency:limit:{limit_id}:holders"

    @staticmethod
    def _holder_to_lease_key(limit_id: UUID, holder_key: str) -> str:
        return f"prefect:concurrency:holder:{limit_id}:{holder_key}"

    def _serialize_lease(
        self, lease: ResourceLease[ConcurrencyLimitLeaseMetadata]
    ) -> str:
        """Serialize a lease to JSON."""
        metadata_dict = None
        if lease.metadata:
            metadata_dict = {"slots": lease.metadata.slots}
            if getattr(lease.metadata, "holder", None) is not None:
                holder = lease.metadata.holder
                if hasattr(holder, "model_dump"):
                    holder = holder.model_dump(mode="json")  # type: ignore[attr-defined]
                metadata_dict["holder"] = holder

        data = {
            "id": str(lease.id),
            "resource_ids": [str(rid) for rid in lease.resource_ids],
            "expiration": lease.expiration.isoformat(),
            "created_at": lease.created_at.isoformat(),
            "metadata": metadata_dict,
        }
        return json.dumps(data)

    def _deserialize_lease(
        self, data: str
    ) -> ResourceLease[ConcurrencyLimitLeaseMetadata]:
        """Deserialize a lease from JSON."""
        lease_data = json.loads(data)
        metadata = None
        if lease_data["metadata"]:
            holder = lease_data["metadata"].get("holder")
            metadata = ConcurrencyLimitLeaseMetadata(
                slots=lease_data["metadata"]["slots"]
            )
            if holder is not None:
                try:
                    setattr(metadata, "holder", holder)
                except (AttributeError, TypeError):
                    logger.debug(
                        "Could not set holder on metadata type %s for lease %s",
                        type(metadata).__name__,
                        lease_data.get("id"),
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
            serialized_lease = self._serialize_lease(lease)

            # Use pipeline for atomic operations
            pipe = self.redis_client.pipeline()
            pipe.set(lease_key, serialized_lease)
            pipe.zadd(
                self.expirations_key,
                {str(lease.id): expiration.timestamp()},
            )

            # Index holder per limit for fast lookups
            holder = None
            if metadata is not None:
                holder = getattr(metadata, "holder", None)
                if hasattr(holder, "model_dump"):
                    holder = holder.model_dump(mode="json")  # type: ignore[attr-defined]
            hk = self._holder_key(holder)
            if hk:
                for rid in resource_ids:
                    pipe.sadd(self._limit_holders_key(rid), hk)
                    pipe.set(self._holder_to_lease_key(rid, hk), str(lease.id))

            await pipe.execute()

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
            serialized_lease = self._serialize_lease(lease)

            # Use pipeline for atomic operations
            pipe = self.redis_client.pipeline()
            pipe.set(lease_key, serialized_lease)
            pipe.zadd(
                self.expirations_key,
                {str(lease_id): new_expiration.timestamp()},
            )
            await pipe.execute()
        except RedisError as e:
            logger.error(f"Failed to renew lease {lease_id}: {e}")
            raise

    async def revoke_lease(self, lease_id: UUID) -> None:
        try:
            lease_key = self._lease_key(lease_id)
            # Read lease to clean up indexes
            data = await self.redis_client.get(lease_key)
            holder_key: str | None = None
            resource_ids: list[UUID] = []
            if data is not None:
                lease = self._deserialize_lease(data)
                resource_ids = lease.resource_ids
                holder = (
                    getattr(lease.metadata, "holder", None) if lease.metadata else None
                )
                if hasattr(holder, "model_dump"):
                    holder = holder.model_dump(mode="json")  # type: ignore[attr-defined]
                holder_key = self._holder_key(holder)

            # Use pipeline for atomic operations
            pipe = self.redis_client.pipeline()
            pipe.delete(lease_key)
            pipe.zrem(self.expirations_key, str(lease_id))
            if holder_key and resource_ids:
                for rid in resource_ids:
                    pipe.srem(self._limit_holders_key(rid), holder_key)
                    pipe.delete(self._holder_to_lease_key(rid, holder_key))
            await pipe.execute()
        except RedisError as e:
            logger.error(f"Failed to revoke lease {lease_id}: {e}")
            raise

    async def read_active_lease_ids(self, limit: int = 100) -> list[UUID]:
        try:
            now = datetime.now(timezone.utc).timestamp()

            # Get lease IDs that expire after now (active leases)
            active_lease_ids = await self.redis_client.zrangebyscore(
                self.expirations_key, now, "+inf", start=0, num=limit
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
                self.expirations_key, "-inf", now, start=0, num=limit
            )

            return [UUID(lease_id) for lease_id in expired_lease_ids]
        except RedisError as e:
            logger.error(f"Failed to read expired lease IDs: {e}")
            raise

    async def list_holders_for_limit(self, limit_id: UUID) -> list[dict]:
        try:
            members = await self.redis_client.smembers(
                self._limit_holders_key(limit_id)
            )
            result: list[dict] = []
            for m in members:
                if isinstance(m, bytes):
                    m = m.decode()
                if not isinstance(m, str) or ":" not in m:
                    continue
                h_type, h_id = m.split(":", 1)
                result.append({"type": h_type, "id": h_id})
            return result
        except RedisError as e:
            logger.error(f"Failed to list holders for limit {limit_id}: {e}")
            raise

    async def find_lease_by_holder(self, limit_id: UUID, holder: dict) -> UUID | None:
        try:
            hk = self._holder_key(holder)
            if not hk:
                return None
            val = await self.redis_client.get(self._holder_to_lease_key(limit_id, hk))
            return UUID(val) if val else None
        except RedisError as e:
            logger.error("Failed to find lease by holder for limit %s: %s", limit_id, e)
            raise
        except (ValueError, TypeError):
            return None
