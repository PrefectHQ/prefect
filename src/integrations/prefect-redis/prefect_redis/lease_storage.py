from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable
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
        # Lua scripts (registered or fallback wrappers)
        self._create_script: Callable[..., Awaitable[Any]] | None = None
        self._revoke_script: Callable[..., Awaitable[Any]] | None = None

    def _lease_key(self, lease_id: UUID) -> str:
        """Generate Redis key for a lease."""
        return f"{self.lease_prefix}{lease_id}"

    def _expiration_key(self, lease_id: UUID) -> str:
        """Generate Redis key for lease expiration."""
        return f"{self.expiration_prefix}{lease_id}"

    @staticmethod
    def _holder_key(holder: dict[str, Any] | None) -> str | None:
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

    async def _ensure_scripts(self) -> None:
        if self._create_script is None:
            create_script = """
            -- KEYS[1] = lease_key
            -- KEYS[2] = expirations_key
            -- KEYS[3..n] = pairs of (limit_holders_key, holder_to_lease_key)
            -- ARGV[1] = lease_json
            -- ARGV[2] = expiration_ts (number)
            -- ARGV[3] = lease_id
            -- ARGV[4] = holder_key (or empty string)
            redis.call('SET', KEYS[1], ARGV[1])
            redis.call('ZADD', KEYS[2], ARGV[2], ARGV[3])
            if ARGV[4] ~= '' then
              local i = 3
              while i <= #KEYS do
                redis.call('SADD', KEYS[i], ARGV[4])
                redis.call('SET', KEYS[i+1], ARGV[3])
                i = i + 2
              end
            end
            return 1
            """
            # Prefer register_script; fall back to script_load+evalsha if unavailable
            if hasattr(self.redis_client, "register_script"):
                script_obj = self.redis_client.register_script(create_script)

                async def _call_registered_create(*, keys: list[str], args: list[str]):
                    return await script_obj(keys=keys, args=args)  # type: ignore[misc]

                self._create_script = _call_registered_create
            else:  # pragma: no cover - legacy fallback
                create_sha = await self.redis_client.script_load(create_script)

                async def _call_evalsha_create(*, keys: list[str], args: list[str]):
                    return await self.redis_client.evalsha(
                        create_sha, len(keys), *keys, *args
                    )  # type: ignore[arg-type]

                self._create_script = _call_evalsha_create

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
                local holder_key = ''
                if lease['metadata'] and lease['metadata']['holder'] then
                  local h = lease['metadata']['holder']
                  if h and h['type'] and h['id'] then
                    holder_key = tostring(h['type']) .. ':' .. tostring(h['id'])
                  end
                end
                if holder_key ~= '' and lease['resource_ids'] then
                  for _, rid in ipairs(lease['resource_ids']) do
                    local set_key = 'prefect:concurrency:limit:' .. tostring(rid) .. ':holders'
                    local map_key = 'prefect:concurrency:holder:' .. tostring(rid) .. ':' .. holder_key
                    if redis.call('GET', map_key) == ARGV[1] then
                      redis.call('SREM', set_key, holder_key)
                      redis.call('DEL', map_key)
                    end
                  end
                end
              end
            end
            -- Proceed with idempotent deletes regardless
            redis.call('DEL', KEYS[1])
            redis.call('ZREM', KEYS[2], ARGV[1])
            return 1
            """
            if hasattr(self.redis_client, "register_script"):
                script_obj = self.redis_client.register_script(revoke_script)

                async def _call_registered_revoke(*, keys: list[str], args: list[str]):
                    return await script_obj(keys=keys, args=args)  # type: ignore[misc]

                self._revoke_script = _call_registered_revoke
            else:  # pragma: no cover - legacy fallback
                revoke_sha = await self.redis_client.script_load(revoke_script)

                async def _call_evalsha_revoke(*, keys: list[str], args: list[str]):
                    return await self.redis_client.evalsha(
                        revoke_sha, len(keys), *keys, *args
                    )  # type: ignore[arg-type]

                self._revoke_script = _call_evalsha_revoke

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

            # Use a Lua script for atomic multi-key updates
            await self._ensure_scripts()
            holder = None
            if metadata is not None:
                holder = getattr(metadata, "holder", None)
                if hasattr(holder, "model_dump"):
                    holder = holder.model_dump(mode="json")  # type: ignore[attr-defined]
            hk = self._holder_key(holder) or ""

            keys: list[str] = [
                lease_key,
                self.expirations_key,
            ]
            if hk:
                for rid in resource_ids:
                    keys.append(self._limit_holders_key(rid))
                    keys.append(self._holder_to_lease_key(rid, hk))

            args: list[str] = [
                serialized_lease,
                str(expiration.timestamp()),
                str(lease.id),
                hk,
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

    async def list_holders_for_limit(self, limit_id: UUID) -> list[dict[str, Any]]:
        try:
            members = await self.redis_client.smembers(
                self._limit_holders_key(limit_id)
            )
            result: list[dict[str, Any]] = []
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

    async def find_lease_by_holder(
        self, limit_id: UUID, holder: dict[str, Any]
    ) -> UUID | None:
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
