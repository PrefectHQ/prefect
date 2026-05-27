from __future__ import annotations

import asyncio
import json
from collections.abc import Iterable, Mapping
from datetime import timedelta
from hashlib import sha256
from secrets import token_urlsafe
from typing import TYPE_CHECKING, Any
from uuid import UUID

from prefect.client.schemas.worker_channel import CleanupKind
from prefect.server.worker_communication.cleanup_queue import (
    CleanupQueueDeadLetter,
    CleanupQueueLeaseExpiryResult,
    CleanupQueueMessage,
    CleanupQueueOperation,
    CleanupQueueOperationResult,
    CleanupQueueReservation,
    CleanupQueueWakeup,
)
from prefect.server.worker_communication.cleanup_queue import (
    WorkerCleanupQueue as _WorkerCleanupQueue,
)
from prefect.settings.context import get_current_settings
from prefect.types import DateTime
from prefect.types._datetime import now

if TYPE_CHECKING:
    from redis.asyncio import Redis


_ENQUEUE_SCRIPT = """
local prefix = ARGV[1]
local message_id = ARGV[2]
local idempotency_hash = ARGV[3]
local idempotency_key = ARGV[4]
local work_pool_id = ARGV[5]
local work_queue_id = ARGV[6]
local kind = ARGV[7]
local target = ARGV[8]
local data = ARGV[9]
local current_time = ARGV[10]
local score = ARGV[11]

local active_key = prefix .. ":messages:" .. message_id
local dead_key = prefix .. ":dead:" .. message_id
local acked_key = prefix .. ":acked:" .. message_id
local idempotency_key_name = prefix .. ":idempotency:" .. work_pool_id .. ":" .. idempotency_hash
local visible_key = prefix .. ":pool:" .. work_pool_id .. ":visible"
local pools_key = prefix .. ":pools"

local function validate_existing(key)
    if redis.call("HGET", key, "idempotency_key") ~= idempotency_key
        or redis.call("HGET", key, "work_pool_id") ~= work_pool_id then
        return {"conflict"}
    end
    return {"existing", redis.call("HGETALL", key)}
end

if redis.call("EXISTS", active_key) == 1 then
    return validate_existing(active_key)
end
if redis.call("EXISTS", dead_key) == 1 then
    return validate_existing(dead_key)
end
if redis.call("EXISTS", acked_key) == 1 then
    return validate_existing(acked_key)
end

local existing_message_id = redis.call("GET", idempotency_key_name)
if existing_message_id then
    local existing_active_key = prefix .. ":messages:" .. existing_message_id
    local existing_dead_key = prefix .. ":dead:" .. existing_message_id
    local existing_acked_key = prefix .. ":acked:" .. existing_message_id
    if redis.call("EXISTS", existing_active_key) == 1 then
        return validate_existing(existing_active_key)
    end
    if redis.call("EXISTS", existing_dead_key) == 1 then
        return validate_existing(existing_dead_key)
    end
    if redis.call("EXISTS", existing_acked_key) == 1 then
        return validate_existing(existing_acked_key)
    end
    redis.call("DEL", idempotency_key_name)
end

redis.call(
    "HSET",
    active_key,
    "message_id", message_id,
    "idempotency_key", idempotency_key,
    "idempotency_hash", idempotency_hash,
    "work_pool_id", work_pool_id,
    "work_queue_id", work_queue_id,
    "kind", kind,
    "target", target,
    "data", data,
    "created_at", current_time,
    "updated_at", current_time,
    "delivery_count", "0"
)
redis.call("SET", idempotency_key_name, message_id)
redis.call("ZADD", visible_key, score, message_id)
redis.call("SADD", pools_key, work_pool_id)

return {"created", redis.call("HGETALL", active_key)}
"""

_RESERVE_SCRIPT = """
local prefix = ARGV[1]
local work_pool_id = ARGV[2]
local current_time = ARGV[3]
local lease_expires_at = ARGV[4]
local lease_expires_ms = ARGV[5]
local token = ARGV[6]
local max_delivery_attempts = tonumber(ARGV[7])
local kind_count = tonumber(ARGV[8])
local index = 9
local kind_filters = {}
for i = 1, kind_count do
    kind_filters[ARGV[index]] = true
    index = index + 1
end
local preferred_count = tonumber(ARGV[index])
index = index + 1
local preferred_queues = {}
for i = 1, preferred_count do
    preferred_queues[ARGV[index]] = true
    index = index + 1
end
local allow_fallback = ARGV[index] == "1"

local visible_key = prefix .. ":pool:" .. work_pool_id .. ":visible"
local reserved_key = prefix .. ":pool:" .. work_pool_id .. ":reserved"

local function kind_allowed(kind)
    if kind_count == 0 then
        return true
    end
    return kind_filters[kind] == true
end

local function queue_allowed(work_queue_id, preferred_pass)
    if preferred_count == 0 then
        return true
    end
    if preferred_pass then
        return work_queue_id ~= "" and preferred_queues[work_queue_id] == true
    end
    return allow_fallback
end

local function move_to_dead_letter(message_key, reservation_key, reason, release_reason)
    local message_id = redis.call("HGET", message_key, "message_id")
    local dead_key = prefix .. ":dead:" .. message_id
    local fields = redis.call("HGETALL", message_key)
    if #fields > 0 then
        redis.call("HSET", dead_key, unpack(fields))
    end
    redis.call(
        "HSET",
        dead_key,
        "reason", reason,
        "final_delivery_count", redis.call("HGET", message_key, "delivery_count") or "0",
        "moved_at", current_time,
        "reservation_token", redis.call("HGET", reservation_key, "token") or "",
        "lease_expires_at", redis.call("HGET", reservation_key, "lease_expires_at") or "",
        "release_reason", release_reason or ""
    )
    redis.call("DEL", message_key)
    redis.call("DEL", reservation_key)
    redis.call("ZREM", visible_key, message_id)
    redis.call("ZREM", reserved_key, message_id)
end

local function try_reserve(preferred_pass)
    local message_ids = redis.call("ZRANGE", visible_key, 0, -1)
    for _, message_id in ipairs(message_ids) do
        local message_key = prefix .. ":messages:" .. message_id
        if redis.call("EXISTS", message_key) == 0 then
            redis.call("ZREM", visible_key, message_id)
        elseif kind_allowed(redis.call("HGET", message_key, "kind"))
            and queue_allowed(redis.call("HGET", message_key, "work_queue_id") or "", preferred_pass) then
            local delivery_count = tonumber(redis.call("HGET", message_key, "delivery_count") or "0")
            if delivery_count >= max_delivery_attempts then
                local reservation_key = prefix .. ":reservations:" .. message_id
                move_to_dead_letter(message_key, reservation_key, "max_delivery_attempts_reached", "")
            else
                redis.call("HINCRBY", message_key, "delivery_count", 1)
                redis.call("HSET", message_key, "updated_at", current_time)
                redis.call(
                    "HSET",
                    prefix .. ":reservations:" .. message_id,
                    "token", token,
                    "lease_expires_at", lease_expires_at,
                    "lease_expires_ms", lease_expires_ms,
                    "reserved_at", current_time
                )
                redis.call("ZREM", visible_key, message_id)
                redis.call("ZADD", reserved_key, lease_expires_ms, message_id)
                return redis.call("HGETALL", message_key)
            end
        end
    end
    return nil
end

local reserved = try_reserve(preferred_count > 0)
if reserved then
    return {"reserved", reserved, token, lease_expires_at}
end
if preferred_count > 0 and allow_fallback then
    reserved = try_reserve(false)
    if reserved then
        return {"reserved", reserved, token, lease_expires_at}
    end
end

return {"empty"}
"""

_ACK_SCRIPT = """
local prefix = ARGV[1]
local work_pool_id = ARGV[2]
local message_id = ARGV[3]
local token = ARGV[4]
local current_time = ARGV[5]
local current_ms = tonumber(ARGV[6])
local max_delivery_attempts = tonumber(ARGV[7])
local completed_retention_ms = tonumber(ARGV[8])

local message_key = prefix .. ":messages:" .. message_id
local reservation_key = prefix .. ":reservations:" .. message_id
local visible_key = prefix .. ":pool:" .. work_pool_id .. ":visible"
local reserved_key = prefix .. ":pool:" .. work_pool_id .. ":reserved"

local function move_to_dead_letter(reason, release_reason)
    local dead_key = prefix .. ":dead:" .. message_id
    local fields = redis.call("HGETALL", message_key)
    if #fields > 0 then
        redis.call("HSET", dead_key, unpack(fields))
    end
    redis.call(
        "HSET",
        dead_key,
        "reason", reason,
        "final_delivery_count", redis.call("HGET", message_key, "delivery_count") or "0",
        "moved_at", current_time,
        "reservation_token", redis.call("HGET", reservation_key, "token") or "",
        "lease_expires_at", redis.call("HGET", reservation_key, "lease_expires_at") or "",
        "release_reason", release_reason or ""
    )
    redis.call("DEL", message_key)
    redis.call("DEL", reservation_key)
    redis.call("ZREM", visible_key, message_id)
    redis.call("ZREM", reserved_key, message_id)
    return redis.call("HGETALL", dead_key)
end

if redis.call("EXISTS", message_key) == 0 then
    return {"not_found", "message_not_found"}
end
if redis.call("HGET", message_key, "work_pool_id") ~= work_pool_id then
    return {"unauthorized", "work_pool_mismatch"}
end
if redis.call("EXISTS", reservation_key) == 0 then
    return {"not_current", "no_active_reservation"}
end
if redis.call("HGET", reservation_key, "token") ~= token then
    return {"invalid_token", "reservation_token_mismatch"}
end
if tonumber(redis.call("HGET", reservation_key, "lease_expires_ms") or "0") <= current_ms then
    if tonumber(redis.call("HGET", message_key, "delivery_count") or "0") >= max_delivery_attempts then
        return {"dead_lettered", "max_delivery_attempts_reached", move_to_dead_letter("max_delivery_attempts_reached", "")}
    end
    redis.call("DEL", reservation_key)
    redis.call("ZREM", reserved_key, message_id)
    redis.call("HSET", message_key, "updated_at", current_time)
    redis.call("ZADD", visible_key, current_ms, message_id)
    return {"expired", "lease_expired", "wake"}
end

local acked_key = prefix .. ":acked:" .. message_id
local fields = redis.call("HGETALL", message_key)
if #fields > 0 then
    redis.call("HSET", acked_key, unpack(fields))
end
redis.call("HSET", acked_key, "updated_at", current_time, "completed_at", current_time)
redis.call("DEL", message_key)
redis.call("DEL", reservation_key)
redis.call("ZREM", visible_key, message_id)
redis.call("ZREM", reserved_key, message_id)
if completed_retention_ms >= 0 then
    local idempotency_hash = redis.call("HGET", acked_key, "idempotency_hash")
    local idempotency_key_name = prefix .. ":idempotency:" .. work_pool_id .. ":" .. idempotency_hash
    redis.call("PEXPIRE", acked_key, completed_retention_ms)
    redis.call("PEXPIRE", idempotency_key_name, completed_retention_ms)
end

return {"accepted"}
"""

_RELEASE_SCRIPT = """
local prefix = ARGV[1]
local work_pool_id = ARGV[2]
local message_id = ARGV[3]
local token = ARGV[4]
local reason = ARGV[5]
local current_time = ARGV[6]
local current_ms = tonumber(ARGV[7])
local max_delivery_attempts = tonumber(ARGV[8])

local message_key = prefix .. ":messages:" .. message_id
local reservation_key = prefix .. ":reservations:" .. message_id
local visible_key = prefix .. ":pool:" .. work_pool_id .. ":visible"
local reserved_key = prefix .. ":pool:" .. work_pool_id .. ":reserved"

local function move_to_dead_letter(dead_reason, release_reason)
    local dead_key = prefix .. ":dead:" .. message_id
    local fields = redis.call("HGETALL", message_key)
    if #fields > 0 then
        redis.call("HSET", dead_key, unpack(fields))
    end
    redis.call(
        "HSET",
        dead_key,
        "reason", dead_reason,
        "final_delivery_count", redis.call("HGET", message_key, "delivery_count") or "0",
        "moved_at", current_time,
        "reservation_token", redis.call("HGET", reservation_key, "token") or "",
        "lease_expires_at", redis.call("HGET", reservation_key, "lease_expires_at") or "",
        "release_reason", release_reason or ""
    )
    redis.call("DEL", message_key)
    redis.call("DEL", reservation_key)
    redis.call("ZREM", visible_key, message_id)
    redis.call("ZREM", reserved_key, message_id)
    return redis.call("HGETALL", dead_key)
end

if redis.call("EXISTS", message_key) == 0 then
    return {"not_found", "message_not_found"}
end
if redis.call("HGET", message_key, "work_pool_id") ~= work_pool_id then
    return {"unauthorized", "work_pool_mismatch"}
end
if redis.call("EXISTS", reservation_key) == 0 then
    return {"not_current", "no_active_reservation"}
end
if redis.call("HGET", reservation_key, "token") ~= token then
    return {"invalid_token", "reservation_token_mismatch"}
end
if tonumber(redis.call("HGET", reservation_key, "lease_expires_ms") or "0") <= current_ms then
    if tonumber(redis.call("HGET", message_key, "delivery_count") or "0") >= max_delivery_attempts then
        return {"dead_lettered", "max_delivery_attempts_reached", move_to_dead_letter("max_delivery_attempts_reached", "")}
    end
    redis.call("DEL", reservation_key)
    redis.call("ZREM", reserved_key, message_id)
    redis.call("HSET", message_key, "updated_at", current_time)
    redis.call("ZADD", visible_key, current_ms, message_id)
    return {"expired", "lease_expired", "wake"}
end
if tonumber(redis.call("HGET", message_key, "delivery_count") or "0") >= max_delivery_attempts then
    return {"dead_lettered", "max_delivery_attempts_reached", move_to_dead_letter("max_delivery_attempts_reached", reason)}
end

redis.call("DEL", reservation_key)
redis.call("ZREM", reserved_key, message_id)
redis.call("HSET", message_key, "updated_at", current_time)
redis.call("ZADD", visible_key, current_ms, message_id)

return {"accepted", "wake"}
"""

_RENEW_SCRIPT = """
local prefix = ARGV[1]
local work_pool_id = ARGV[2]
local message_id = ARGV[3]
local token = ARGV[4]
local current_time = ARGV[5]
local current_ms = tonumber(ARGV[6])
local lease_expires_at = ARGV[7]
local lease_expires_ms = ARGV[8]
local max_delivery_attempts = tonumber(ARGV[9])

local message_key = prefix .. ":messages:" .. message_id
local reservation_key = prefix .. ":reservations:" .. message_id
local visible_key = prefix .. ":pool:" .. work_pool_id .. ":visible"
local reserved_key = prefix .. ":pool:" .. work_pool_id .. ":reserved"

local function move_to_dead_letter(reason)
    local dead_key = prefix .. ":dead:" .. message_id
    local fields = redis.call("HGETALL", message_key)
    if #fields > 0 then
        redis.call("HSET", dead_key, unpack(fields))
    end
    redis.call(
        "HSET",
        dead_key,
        "reason", reason,
        "final_delivery_count", redis.call("HGET", message_key, "delivery_count") or "0",
        "moved_at", current_time,
        "reservation_token", redis.call("HGET", reservation_key, "token") or "",
        "lease_expires_at", redis.call("HGET", reservation_key, "lease_expires_at") or "",
        "release_reason", ""
    )
    redis.call("DEL", message_key)
    redis.call("DEL", reservation_key)
    redis.call("ZREM", visible_key, message_id)
    redis.call("ZREM", reserved_key, message_id)
    return redis.call("HGETALL", dead_key)
end

if redis.call("EXISTS", message_key) == 0 then
    return {"not_found", "message_not_found"}
end
if redis.call("HGET", message_key, "work_pool_id") ~= work_pool_id then
    return {"unauthorized", "work_pool_mismatch"}
end
if redis.call("EXISTS", reservation_key) == 0 then
    return {"not_current", "no_active_reservation"}
end
if redis.call("HGET", reservation_key, "token") ~= token then
    return {"invalid_token", "reservation_token_mismatch"}
end
if tonumber(redis.call("HGET", reservation_key, "lease_expires_ms") or "0") <= current_ms then
    if tonumber(redis.call("HGET", message_key, "delivery_count") or "0") >= max_delivery_attempts then
        return {"dead_lettered", "max_delivery_attempts_reached", move_to_dead_letter("max_delivery_attempts_reached")}
    end
    redis.call("DEL", reservation_key)
    redis.call("ZREM", reserved_key, message_id)
    redis.call("HSET", message_key, "updated_at", current_time)
    redis.call("ZADD", visible_key, current_ms, message_id)
    return {"expired", "lease_expired", "wake"}
end

redis.call(
    "HSET",
    reservation_key,
    "token", token,
    "lease_expires_at", lease_expires_at,
    "lease_expires_ms", lease_expires_ms
)
redis.call("HSET", message_key, "updated_at", current_time)
redis.call("ZADD", reserved_key, lease_expires_ms, message_id)

return {"accepted", lease_expires_at}
"""

_EXPIRE_LEASES_SCRIPT = """
local prefix = ARGV[1]
local work_pool_id = ARGV[2]
local current_time = ARGV[3]
local current_ms = tonumber(ARGV[4])
local max_delivery_attempts = tonumber(ARGV[5])
local limit = tonumber(ARGV[6])

local visible_key = prefix .. ":pool:" .. work_pool_id .. ":visible"
local reserved_key = prefix .. ":pool:" .. work_pool_id .. ":reserved"
local expired_ids = redis.call("ZRANGEBYSCORE", reserved_key, "-inf", current_ms, "LIMIT", 0, limit)
local results = {}

local function move_to_dead_letter(message_id, message_key, reservation_key)
    local dead_key = prefix .. ":dead:" .. message_id
    local fields = redis.call("HGETALL", message_key)
    if #fields > 0 then
        redis.call("HSET", dead_key, unpack(fields))
    end
    redis.call(
        "HSET",
        dead_key,
        "reason", "max_delivery_attempts_reached",
        "final_delivery_count", redis.call("HGET", message_key, "delivery_count") or "0",
        "moved_at", current_time,
        "reservation_token", redis.call("HGET", reservation_key, "token") or "",
        "lease_expires_at", redis.call("HGET", reservation_key, "lease_expires_at") or "",
        "release_reason", ""
    )
    redis.call("DEL", message_key)
    redis.call("DEL", reservation_key)
    redis.call("ZREM", visible_key, message_id)
    redis.call("ZREM", reserved_key, message_id)
    table.insert(results, {"dead_lettered", redis.call("HGETALL", dead_key)})
end

for _, message_id in ipairs(expired_ids) do
    local message_key = prefix .. ":messages:" .. message_id
    local reservation_key = prefix .. ":reservations:" .. message_id
    if redis.call("EXISTS", message_key) == 0 then
        redis.call("DEL", reservation_key)
        redis.call("ZREM", reserved_key, message_id)
    elseif tonumber(redis.call("HGET", message_key, "delivery_count") or "0") >= max_delivery_attempts then
        move_to_dead_letter(message_id, message_key, reservation_key)
    else
        redis.call("DEL", reservation_key)
        redis.call("ZREM", reserved_key, message_id)
        redis.call("HSET", message_key, "updated_at", current_time)
        redis.call("ZADD", visible_key, current_ms, message_id)
        table.insert(results, {"redelivered", redis.call("HGETALL", message_key)})
    end
end

return results
"""


class WorkerCleanupQueue(_WorkerCleanupQueue):
    """
    Redis-backed cleanup queue storage for self-hosted OSS deployments.
    """

    _DEFAULT_EXPIRE_LEASE_LIMIT = 100

    def __init__(
        self,
        *,
        redis_client: "Redis | None" = None,
        key_prefix: str | None = None,
    ) -> None:
        self._redis_client = redis_client
        self._key_prefix = key_prefix
        self._condition = asyncio.Condition()

    async def enqueue(
        self,
        *,
        message_id: UUID,
        idempotency_key: str,
        work_pool_id: UUID,
        kind: CleanupKind,
        target: Mapping[str, Any],
        data: Mapping[str, Any] | None = None,
        work_queue_id: UUID | None = None,
    ) -> CleanupQueueMessage:
        if not idempotency_key:
            raise ValueError("idempotency_key must be non-empty")

        current_time = now("UTC")
        message_fields = self._message_fields(
            message_id=message_id,
            idempotency_key=idempotency_key,
            work_pool_id=work_pool_id,
            work_queue_id=work_queue_id,
            kind=kind,
            target=target,
            data=data,
            current_time=current_time,
        )
        response = await self._eval(
            _ENQUEUE_SCRIPT,
            self._prefix(),
            str(message_id),
            message_fields["idempotency_hash"],
            idempotency_key,
            str(work_pool_id),
            message_fields["work_queue_id"],
            kind,
            message_fields["target"],
            message_fields["data"],
            message_fields["created_at"],
            str(_score_ms(current_time)),
        )
        status = response[0]
        if status == "conflict":
            raise ValueError(
                "message_id is already associated with a different cleanup message"
            )

        message = self._message_from_fields(response[1])
        if status == "created":
            await self.wake_dispatchers(work_pool_id)
        return message

    async def reserve(
        self,
        *,
        work_pool_id: UUID,
        cleanup_kinds: Iterable[CleanupKind] | None = None,
        preferred_work_queue_ids: Iterable[UUID] | None = None,
        allow_fallback_to_any_queue: bool = True,
    ) -> CleanupQueueReservation | None:
        await self.expire_leases(
            limit=self._DEFAULT_EXPIRE_LEASE_LIMIT, work_pool_id=work_pool_id
        )

        current_time = now("UTC")
        lease_expires_at = current_time + self._policy().lease_duration
        token = token_urlsafe(32)
        kind_filters = list(cleanup_kinds or [])
        preferred_queues = [
            str(queue_id) for queue_id in preferred_work_queue_ids or []
        ]
        response = await self._eval(
            _RESERVE_SCRIPT,
            self._prefix(),
            str(work_pool_id),
            _format_datetime(current_time),
            _format_datetime(lease_expires_at),
            str(_score_ms(lease_expires_at)),
            token,
            str(self._policy().max_delivery_attempts),
            str(len(kind_filters)),
            *kind_filters,
            str(len(preferred_queues)),
            *preferred_queues,
            "1" if allow_fallback_to_any_queue else "0",
        )
        if response[0] == "empty":
            return None

        message = self._message_from_fields(response[1])
        return CleanupQueueReservation(
            **message.model_dump(),
            reservation_token=response[2],
            lease_expires_at=response[3],
        )

    async def ack(
        self,
        *,
        work_pool_id: UUID,
        message_id: UUID,
        reservation_token: str,
    ) -> CleanupQueueOperationResult:
        current_time = now("UTC")
        retention = self._policy().completed_idempotency_retention
        response = await self._eval(
            _ACK_SCRIPT,
            self._prefix(),
            str(work_pool_id),
            str(message_id),
            reservation_token,
            _format_datetime(current_time),
            str(_score_ms(current_time)),
            str(self._policy().max_delivery_attempts),
            str(-1 if retention is None else int(retention.total_seconds() * 1000)),
        )
        return await self._operation_result_from_response(
            operation="ack",
            work_pool_id=work_pool_id,
            message_id=message_id,
            response=response,
        )

    async def release(
        self,
        *,
        work_pool_id: UUID,
        message_id: UUID,
        reservation_token: str,
        reason: str,
    ) -> CleanupQueueOperationResult:
        if not reason:
            raise ValueError("release reason must be non-empty")

        current_time = now("UTC")
        response = await self._eval(
            _RELEASE_SCRIPT,
            self._prefix(),
            str(work_pool_id),
            str(message_id),
            reservation_token,
            reason,
            _format_datetime(current_time),
            str(_score_ms(current_time)),
            str(self._policy().max_delivery_attempts),
        )
        return await self._operation_result_from_response(
            operation="release",
            work_pool_id=work_pool_id,
            message_id=message_id,
            response=response,
        )

    async def renew(
        self,
        *,
        work_pool_id: UUID,
        message_id: UUID,
        reservation_token: str,
    ) -> CleanupQueueOperationResult:
        current_time = now("UTC")
        lease_expires_at = current_time + self._policy().lease_duration
        response = await self._eval(
            _RENEW_SCRIPT,
            self._prefix(),
            str(work_pool_id),
            str(message_id),
            reservation_token,
            _format_datetime(current_time),
            str(_score_ms(current_time)),
            _format_datetime(lease_expires_at),
            str(_score_ms(lease_expires_at)),
            str(self._policy().max_delivery_attempts),
        )
        return await self._operation_result_from_response(
            operation="renew",
            work_pool_id=work_pool_id,
            message_id=message_id,
            response=response,
        )

    async def expire_leases(
        self,
        *,
        limit: int = _DEFAULT_EXPIRE_LEASE_LIMIT,
        work_pool_id: UUID | None = None,
    ) -> CleanupQueueLeaseExpiryResult:
        if limit < 1:
            raise ValueError("limit must be at least 1")

        work_pool_ids = (
            [str(work_pool_id)] if work_pool_id else await self._work_pools()
        )
        remaining = limit
        redelivered: list[CleanupQueueMessage] = []
        dead_lettered: list[CleanupQueueDeadLetter] = []
        current_time = now("UTC")

        for current_work_pool_id in work_pool_ids:
            if remaining <= 0:
                break
            response = await self._eval(
                _EXPIRE_LEASES_SCRIPT,
                self._prefix(),
                current_work_pool_id,
                _format_datetime(current_time),
                str(_score_ms(current_time)),
                str(self._policy().max_delivery_attempts),
                str(remaining),
            )
            for status, fields in response:
                if status == "redelivered":
                    redelivered.append(self._message_from_fields(fields))
                elif status == "dead_lettered":
                    dead_lettered.append(self._dead_letter_from_fields(fields))
                remaining -= 1

        for message in redelivered:
            await self.wake_dispatchers(message.work_pool_id)

        return CleanupQueueLeaseExpiryResult(
            redelivered=redelivered,
            dead_lettered=dead_lettered,
        )

    async def read_message(
        self, *, work_pool_id: UUID, message_id: UUID
    ) -> CleanupQueueMessage | None:
        fields = await self._client().hgetall(self._message_key(message_id))
        if not fields:
            return None
        message = self._message_from_mapping(fields)
        return message if message.work_pool_id == work_pool_id else None

    async def read_dead_letter(
        self, *, work_pool_id: UUID, message_id: UUID
    ) -> CleanupQueueDeadLetter | None:
        fields = await self._client().hgetall(self._dead_key(message_id))
        if not fields:
            return None
        dead_letter = self._dead_letter_from_mapping(fields)
        return dead_letter if dead_letter.message.work_pool_id == work_pool_id else None

    async def wake_dispatchers(self, work_pool_id: UUID) -> CleanupQueueWakeup:
        sequence = await self._client().incr(self._wakeup_key(work_pool_id))
        wakeup = CleanupQueueWakeup(work_pool_id=work_pool_id, sequence=sequence)
        async with self._condition:
            self._condition.notify_all()
        return wakeup

    async def read_wakeup_sequence(self, work_pool_id: UUID) -> int:
        value = await self._client().get(self._wakeup_key(work_pool_id))
        return int(value or 0)

    async def wait_for_wakeup(
        self,
        work_pool_id: UUID,
        *,
        after: int = 0,
        timeout: float | None = None,
    ) -> CleanupQueueWakeup | None:
        deadline = (
            None
            if timeout is None
            else asyncio.get_running_loop().time() + max(timeout, 0.0)
        )

        while True:
            sequence = await self.read_wakeup_sequence(work_pool_id)
            if sequence > after:
                return CleanupQueueWakeup(work_pool_id=work_pool_id, sequence=sequence)

            if deadline is None:
                wait_timeout = 1.0
            else:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    return None
                wait_timeout = min(remaining, 1.0)

            try:
                async with self._condition:
                    await asyncio.wait_for(self._condition.wait(), timeout=wait_timeout)
            except (TimeoutError, asyncio.TimeoutError):
                continue

    async def _eval(self, script: str, *args: Any) -> Any:
        return await self._client().eval(script, 0, *args)

    def _client(self) -> "Redis":
        if self._redis_client is not None:
            return self._redis_client

        try:
            from redis.asyncio import Redis
        except ImportError as exc:
            raise RuntimeError(
                "The Redis cleanup queue backend requires redis-py. Install "
                "Prefect with the `redis` extra to use this backend."
            ) from exc

        settings = get_current_settings().server.worker_channel
        self._redis_client = Redis.from_url(
            settings.cleanup_queue_redis_url,
            decode_responses=True,
        )
        return self._redis_client

    def _prefix(self) -> str:
        if self._key_prefix is not None:
            return self._key_prefix.rstrip(":")

        return get_current_settings().server.worker_channel.cleanup_queue_redis_key_prefix.rstrip(
            ":"
        )

    async def _work_pools(self) -> list[str]:
        return list(await self._client().smembers(f"{self._prefix()}:pools"))

    def _message_key(self, message_id: UUID) -> str:
        return f"{self._prefix()}:messages:{message_id}"

    def _dead_key(self, message_id: UUID) -> str:
        return f"{self._prefix()}:dead:{message_id}"

    def _wakeup_key(self, work_pool_id: UUID) -> str:
        return f"{self._prefix()}:wakeup:{work_pool_id}"

    @staticmethod
    def _message_fields(
        *,
        message_id: UUID,
        idempotency_key: str,
        work_pool_id: UUID,
        work_queue_id: UUID | None,
        kind: CleanupKind,
        target: Mapping[str, Any],
        data: Mapping[str, Any] | None,
        current_time: DateTime,
    ) -> dict[str, str]:
        return {
            "message_id": str(message_id),
            "idempotency_key": idempotency_key,
            "idempotency_hash": _idempotency_hash(idempotency_key),
            "work_pool_id": str(work_pool_id),
            "work_queue_id": "" if work_queue_id is None else str(work_queue_id),
            "kind": kind,
            "target": json.dumps(dict(target), separators=(",", ":")),
            "data": json.dumps(dict(data or {}), separators=(",", ":")),
            "created_at": _format_datetime(current_time),
            "updated_at": _format_datetime(current_time),
            "delivery_count": "0",
        }

    def _message_from_fields(self, fields: list[str]) -> CleanupQueueMessage:
        return self._message_from_mapping(_flat_fields_to_mapping(fields))

    @staticmethod
    def _message_from_mapping(fields: Mapping[str, Any]) -> CleanupQueueMessage:
        return CleanupQueueMessage(
            message_id=fields["message_id"],
            idempotency_key=fields["idempotency_key"],
            work_pool_id=fields["work_pool_id"],
            work_queue_id=fields["work_queue_id"] or None,
            kind=fields["kind"],
            target=json.loads(fields["target"]),
            data=json.loads(fields["data"]),
            created_at=fields["created_at"],
            updated_at=fields["updated_at"],
            delivery_count=int(fields["delivery_count"]),
        )

    def _dead_letter_from_fields(self, fields: list[str]) -> CleanupQueueDeadLetter:
        return self._dead_letter_from_mapping(_flat_fields_to_mapping(fields))

    def _dead_letter_from_mapping(
        self, fields: Mapping[str, Any]
    ) -> CleanupQueueDeadLetter:
        return CleanupQueueDeadLetter(
            message=self._message_from_mapping(fields),
            reason=fields["reason"],
            final_delivery_count=int(fields["final_delivery_count"]),
            moved_at=fields["moved_at"],
            reservation_token=fields["reservation_token"] or None,
            lease_expires_at=fields["lease_expires_at"] or None,
            release_reason=fields["release_reason"] or None,
        )

    async def _operation_result_from_response(
        self,
        *,
        operation: CleanupQueueOperation,
        work_pool_id: UUID,
        message_id: UUID,
        response: list[Any],
    ) -> CleanupQueueOperationResult:
        status = response[0]
        if status == "accepted":
            if len(response) > 1 and response[1] == "wake":
                await self.wake_dispatchers(work_pool_id)
            lease_expires_at = response[1] if operation == "renew" else None
            return CleanupQueueOperationResult(
                message_id=message_id,
                operation=operation,
                status="accepted",
                lease_expires_at=lease_expires_at,
            )

        if status == "dead_lettered":
            return CleanupQueueOperationResult(
                message_id=message_id,
                operation=operation,
                status="dead_lettered",
                reason=response[1],
                dead_letter=self._dead_letter_from_fields(response[2]),
            )

        if len(response) > 2 and response[2] == "wake":
            await self.wake_dispatchers(work_pool_id)

        return CleanupQueueOperationResult(
            message_id=message_id,
            operation=operation,
            status=status,
            reason=response[1],
        )

    @staticmethod
    def _policy() -> "_QueuePolicy":
        worker_channel_settings = get_current_settings().server.worker_channel
        retention_seconds = (
            worker_channel_settings.cleanup_completed_idempotency_retention_seconds
        )
        return _QueuePolicy(
            lease_duration=timedelta(
                seconds=worker_channel_settings.cleanup_lease_seconds
            ),
            max_delivery_attempts=worker_channel_settings.cleanup_max_delivery_attempts,
            completed_idempotency_retention=(
                None
                if retention_seconds is None
                else timedelta(seconds=retention_seconds)
            ),
        )


class _QueuePolicy:
    def __init__(
        self,
        *,
        lease_duration: timedelta,
        max_delivery_attempts: int,
        completed_idempotency_retention: timedelta | None,
    ) -> None:
        self.lease_duration = lease_duration
        self.max_delivery_attempts = max_delivery_attempts
        self.completed_idempotency_retention = completed_idempotency_retention


def _flat_fields_to_mapping(fields: list[str]) -> dict[str, str]:
    return {fields[index]: fields[index + 1] for index in range(0, len(fields), 2)}


def _format_datetime(value: DateTime) -> str:
    return value.isoformat()


def _score_ms(value: DateTime) -> int:
    return int(value.timestamp() * 1000)


def _idempotency_hash(idempotency_key: str) -> str:
    return sha256(idempotency_key.encode()).hexdigest()
