from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import RedisError

from prefect.server.concurrency.lease_storage import (
    ConcurrencyLeaseHolder,
    ConcurrencyLimitLeaseMetadata,
)
from prefect.server.concurrency.lease_storage import (
    ConcurrencyLeaseStorage as _ConcurrencyLeaseStorage,
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
        # Lua scripts registered on the server
        self._create_script: Any | None = None
        self._revoke_script: Any | None = None

    def _lease_key(self, lease_id: UUID) -> str:
        """Generate Redis key for a lease."""
        return f"{self.lease_prefix}{lease_id}"

    def _expiration_key(self, lease_id: UUID) -> str:
        """Generate Redis key for lease expiration."""
        return f"{self.expiration_prefix}{lease_id}"

    @staticmethod
    def _limit_holders_key(limit_id: UUID) -> str:
        return f"prefect:concurrency:limit:{limit_id}:holders"

    async def _ensure_scripts(self) -> None:
        if self._create_script is None:
            create_script = """
            -- KEYS[1] = lease_key
            -- KEYS[2] = expirations_key
            -- KEYS[3..n] = limit_holders_key for each resource id
            -- ARGV[1] = lease_json
            -- ARGV[2] = expiration_ts (number)
            -- ARGV[3] = lease_id
            -- ARGV[4] = holder_entry_json (or empty string)
            redis.call('SET', KEYS[1], ARGV[1])
            redis.call('ZADD', KEYS[2], ARGV[2], ARGV[3])
            if ARGV[4] ~= '' then
              local i = 3
              while i <= #KEYS do
                redis.call('HSET', KEYS[i], ARGV[3], ARGV[4])
                i = i + 1
              end
            end
            return 1
            """
            self._create_script = self.redis_client.register_script(create_script)

        if self._revoke_script is None:
            revoke_script = """
            -- KEYS[1] = lease_key
            -- KEYS[2] = expirations_key
            -- ARGV[1] = lease_id
            -- Read the lease in-script to avoid races and compute index keys
            local lease_json = redis.call('GET', KEYS[1])
            if lease_json then
              local ok, lease = pcall(cjson.decode, lease_json)
              if ok and lease then
                if lease['resource_ids'] then
                  for _, rid in ipairs(lease['resource_ids']) do
                    local holder_index_key = 'prefect:concurrency:limit:' .. tostring(rid) .. ':holders'
                    redis.call('HDEL', holder_index_key, ARGV[1])
                  end
                end
              end
            end
            -- Proceed with idempotent deletes regardless
            redis.call('DEL', KEYS[1])
            redis.call('ZREM', KEYS[2], ARGV[1])
            return 1
            """
            self._revoke_script = self.redis_client.register_script(revoke_script)

    def _serialize_lease(
        self, lease: ResourceLease[ConcurrencyLimitLeaseMetadata]
    ) -> str:
        """Serialize a lease to JSON."""
        metadata_dict: dict[str, Any] | None = None
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

            # Use a Lua script for atomic multi-key updates
            await self._ensure_scripts()
            holder_entry_json = ""
            if metadata is not None and getattr(metadata, "holder", None) is not None:
                holder = getattr(metadata, "holder")
                if hasattr(holder, "model_dump"):
                    holder = holder.model_dump(mode="json")  # type: ignore[attr-defined]
                holder_entry_json = json.dumps(
                    {
                        "holder": holder,
                        "slots": metadata.slots,
                        "lease_id": str(lease.id),
                    }
                )

            keys: list[str] = [
                lease_key,
                self.expirations_key,
            ]
            if holder_entry_json:
                for rid in resource_ids:
                    keys.append(self._limit_holders_key(rid))

            args: list[str] = [
                serialized_lease,
                str(expiration.timestamp()),
                str(lease.id),
                holder_entry_json,
            ]

            await self._create_script(keys=keys, args=args)  # type: ignore[misc]

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

    async def renew_lease(self, lease_id: UUID, ttl: timedelta) -> bool:
        """
        Atomically renew a concurrency lease by updating its expiration.

        Uses a Lua script to atomically check if the lease exists, update its expiration
        in the lease data, and update the index - all in a single atomic operation,
        preventing race conditions from creating orphaned index entries.

        Args:
            lease_id: The ID of the lease to renew
            ttl: The new time-to-live duration

        Returns:
            True if the lease was renewed, False if it didn't exist
        """
        try:
            lease_key = self._lease_key(lease_id)
            new_expiration = datetime.now(timezone.utc) + ttl
            new_expiration_iso = new_expiration.isoformat()
            new_expiration_timestamp = new_expiration.timestamp()

            # Lua script to atomically get, update, and store lease + index
            # All operations are atomic - no TOCTOU race condition possible
            renew_lease_script = """
            local lease_key = KEYS[1]
            local expirations_key = KEYS[2]
            local lease_id = ARGV[1]
            local new_expiration_timestamp = tonumber(ARGV[2])
            local new_expiration_iso = ARGV[3]

            -- Get existing lease data
            local serialized_lease = redis.call('get', lease_key)
            if not serialized_lease then
                -- Lease doesn't exist - clean up any orphaned index entry
                redis.call('zrem', expirations_key, lease_id)
                return 0
            end

            -- Parse lease data, update expiration, and save back
            local lease_data = cjson.decode(serialized_lease)
            lease_data['expiration'] = new_expiration_iso
            redis.call('set', lease_key, cjson.encode(lease_data))

            -- Update the expiration index
            redis.call('zadd', expirations_key, new_expiration_timestamp, lease_id)
            return 1
            """

            # Execute the atomic Lua script
            result = await self.redis_client.eval(
                renew_lease_script,
                2,  # number of keys
                lease_key,
                self.expirations_key,
                str(lease_id),
                new_expiration_timestamp,
                new_expiration_iso,
            )

            return bool(result)
        except RedisError as e:
            logger.error(f"Failed to renew lease {lease_id}: {e}")
            raise

    async def revoke_lease(self, lease_id: UUID) -> None:
        try:
            lease_key = self._lease_key(lease_id)
            # Use a Lua script for atomic multi-key updates with in-script read/cleanup
            await self._ensure_scripts()
            keys: list[str] = [
                lease_key,
                self.expirations_key,
            ]
            args: list[str] = [
                str(lease_id),
            ]
            await self._revoke_script(keys=keys, args=args)  # type: ignore[misc]
        except RedisError as e:
            logger.error(f"Failed to revoke lease {lease_id}: {e}")
            raise

    async def read_active_lease_ids(
        self, limit: int = 100, offset: int = 0
    ) -> list[UUID]:
        try:
            now = datetime.now(timezone.utc).timestamp()

            # Get lease IDs that expire after now (active leases)
            # Redis zrangebyscore uses 'start' as the offset and 'num' as the limit
            active_lease_ids = await self.redis_client.zrangebyscore(
                self.expirations_key, now, "+inf", start=offset, num=limit
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

    async def list_holders_for_limit(
        self, limit_id: UUID
    ) -> list[tuple[UUID, ConcurrencyLeaseHolder]]:
        try:
            # Get all holder entries for this limit
            values = await self.redis_client.hvals(self._limit_holders_key(limit_id))
            holders_with_leases: list[tuple[UUID, ConcurrencyLeaseHolder]] = []

            for v in values:
                if isinstance(v, (bytes, bytearray)):
                    v = v.decode()
                try:
                    data = json.loads(v)
                    if isinstance(data, dict) and "holder" in data:
                        holder_data: dict[str, Any] = data["holder"]
                        if isinstance(holder_data, dict):
                            # Create ConcurrencyLeaseHolder from the data
                            holder = ConcurrencyLeaseHolder(**holder_data)
                            holders_with_leases.append((UUID(data["lease_id"]), holder))
                except Exception:
                    # Skip malformed entries
                    continue

            return holders_with_leases
        except RedisError as e:
            logger.error(f"Failed to list holders for limit {limit_id}: {e}")
            raise
