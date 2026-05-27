from __future__ import annotations

import asyncio
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import timedelta
from hashlib import sha256
from secrets import token_urlsafe
from typing import Any, Literal
from uuid import UUID

from pydantic import Field
from redis.asyncio import Redis
from redis.exceptions import WatchError

from prefect.client.schemas.worker_channel import CleanupKind, CleanupOperationStatus
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
from prefect.settings.base import PrefectBaseSettings, build_settings_config
from prefect.settings.context import get_current_settings
from prefect.types import DateTime
from prefect.types._datetime import now

_MAX_TRANSACTION_ATTEMPTS = 20
_LeaseExpiryOutcome = (
    tuple[Literal["redelivered"], CleanupQueueMessage]
    | tuple[Literal["dead_lettered"], CleanupQueueDeadLetter]
    | None
)


class RedisWorkerCleanupQueueSettings(PrefectBaseSettings):
    """
    Settings for the Redis-backed worker cleanup queue.
    """

    model_config = build_settings_config(("redis", "worker_cleanup_queue"))

    key_prefix: str = Field(
        default="prefect:worker-cleanup",
        min_length=1,
        description=(
            "The Redis key prefix used by the worker cleanup delivery queue. "
            "Use a deployment-specific prefix when sharing a Redis database "
            "across separate Prefect server deployments."
        ),
    )
    url: str | None = Field(
        default=None,
        description=(
            "Full Redis URL for worker cleanup queue storage. When set, "
            "host, port, database, username, password, and SSL settings are "
            "ignored."
        ),
    )
    host: str = Field(default="localhost")
    port: int = Field(default=6379)
    db: int = Field(default=0)
    username: str = Field(default="default")
    password: str = Field(default="")
    health_check_interval: int = Field(default=20)
    ssl: bool = Field(default=False)


@dataclass(frozen=True)
class _QueuePolicy:
    lease_duration: timedelta
    max_delivery_attempts: int
    completed_idempotency_retention: timedelta | None


@dataclass(frozen=True)
class _ScopedMessageKeys:
    message: str
    reservation: str
    visible: str
    reserved: str


class WorkerCleanupQueue(_WorkerCleanupQueue):
    """
    Redis-backed cleanup queue storage.
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
        idempotency_key_name = self._idempotency_key(
            work_pool_id, message_fields["idempotency_hash"]
        )
        active_key = self._message_key(message_id)
        dead_key = self._dead_key(message_id)
        acked_key = self._acked_key(message_id)

        for _ in range(_MAX_TRANSACTION_ATTEMPTS):
            async with self._client().pipeline(transaction=True) as pipe:
                try:
                    await pipe.watch(
                        active_key, dead_key, acked_key, idempotency_key_name
                    )
                    existing = await self._read_existing_message_from_keys(
                        pipe=pipe,
                        keys=(active_key, dead_key, acked_key),
                        idempotency_key=idempotency_key,
                        work_pool_id=work_pool_id,
                    )
                    if existing is not None:
                        await pipe.reset()
                        return existing

                    existing_message_id = await pipe.get(idempotency_key_name)
                    if existing_message_id is not None:
                        existing_message_id_string = _decode_redis_value(
                            existing_message_id
                        )
                        existing_keys = (
                            self._message_key(existing_message_id_string),
                            self._dead_key(existing_message_id_string),
                            self._acked_key(existing_message_id_string),
                        )
                        await pipe.watch(*existing_keys)
                        existing = await self._read_existing_message_from_keys(
                            pipe=pipe,
                            keys=existing_keys,
                            idempotency_key=idempotency_key,
                            work_pool_id=work_pool_id,
                        )
                        if existing is not None:
                            await pipe.reset()
                            return existing

                        pipe.multi()
                        pipe.delete(idempotency_key_name)
                        await pipe.execute()
                        continue

                    pipe.multi()
                    pipe.hset(active_key, mapping=message_fields)
                    pipe.set(idempotency_key_name, str(message_id))
                    pipe.zadd(
                        self._visible_key(work_pool_id),
                        {str(message_id): _score_ms(current_time)},
                    )
                    pipe.sadd(self._pools_key(), str(work_pool_id))
                    await pipe.execute()
                    message = self._message_from_mapping(message_fields)
                    await self.wake_dispatchers(work_pool_id)
                    return message
                except WatchError:
                    continue

        raise RuntimeError("Redis cleanup queue enqueue transaction failed.")

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
        reservation_token = token_urlsafe(32)
        cleanup_kind_filter = (
            {str(kind) for kind in cleanup_kinds} if cleanup_kinds is not None else None
        )

        for queue_filter in self._queue_preference_passes(
            preferred_work_queue_ids=preferred_work_queue_ids,
            allow_fallback_to_any_queue=allow_fallback_to_any_queue,
        ):
            message_ids = await self._client().zrange(
                self._visible_key(work_pool_id), 0, -1
            )
            for raw_message_id in message_ids:
                message_id = _decode_redis_value(raw_message_id)
                reservation = await self._reserve_candidate(
                    work_pool_id=work_pool_id,
                    message_id=message_id,
                    current_time=current_time,
                    lease_expires_at=lease_expires_at,
                    reservation_token=reservation_token,
                    cleanup_kind_filter=cleanup_kind_filter,
                    queue_filter=queue_filter,
                )
                if reservation is not None:
                    return reservation

        return None

    async def ack(
        self,
        *,
        work_pool_id: UUID,
        message_id: UUID,
        reservation_token: str,
    ) -> CleanupQueueOperationResult:
        return await self._run_operation(
            operation="ack",
            work_pool_id=work_pool_id,
            message_id=message_id,
            reservation_token=reservation_token,
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

        return await self._run_operation(
            operation="release",
            work_pool_id=work_pool_id,
            message_id=message_id,
            reservation_token=reservation_token,
            release_reason=reason,
        )

    async def renew(
        self,
        *,
        work_pool_id: UUID,
        message_id: UUID,
        reservation_token: str,
    ) -> CleanupQueueOperationResult:
        return await self._run_operation(
            operation="renew",
            work_pool_id=work_pool_id,
            message_id=message_id,
            reservation_token=reservation_token,
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
        current_time = now("UTC")
        current_ms = _score_ms(current_time)
        remaining = limit
        redelivered: list[CleanupQueueMessage] = []
        dead_lettered: list[CleanupQueueDeadLetter] = []

        for current_work_pool_id in work_pool_ids:
            if remaining <= 0:
                break

            expired_message_ids = await self._client().zrangebyscore(
                self._reserved_key(current_work_pool_id),
                "-inf",
                current_ms,
                start=0,
                num=remaining,
            )
            for raw_message_id in expired_message_ids:
                if remaining <= 0:
                    break

                outcome = await self._expire_lease_candidate(
                    work_pool_id=current_work_pool_id,
                    message_id=_decode_redis_value(raw_message_id),
                    current_time=current_time,
                    current_ms=current_ms,
                )
                if outcome is None:
                    continue

                status, payload = outcome
                remaining -= 1
                if status == "redelivered":
                    redelivered.append(payload)
                else:
                    dead_lettered.append(payload)

        for message in redelivered:
            await self.wake_dispatchers(message.work_pool_id)

        return CleanupQueueLeaseExpiryResult(
            redelivered=redelivered,
            dead_lettered=dead_lettered,
        )

    async def read_message(
        self, *, work_pool_id: UUID, message_id: UUID
    ) -> CleanupQueueMessage | None:
        fields = _string_mapping(
            await self._client().hgetall(self._message_key(message_id))
        )
        if not fields:
            return None
        message = self._message_from_mapping(fields)
        return message if message.work_pool_id == work_pool_id else None

    async def read_dead_letter(
        self, *, work_pool_id: UUID, message_id: UUID
    ) -> CleanupQueueDeadLetter | None:
        fields = _string_mapping(
            await self._client().hgetall(self._dead_key(message_id))
        )
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

    async def _reserve_candidate(
        self,
        *,
        work_pool_id: UUID,
        message_id: str,
        current_time: DateTime,
        lease_expires_at: DateTime,
        reservation_token: str,
        cleanup_kind_filter: set[str] | None,
        queue_filter: set[str] | None,
    ) -> CleanupQueueReservation | None:
        keys = self._scoped_message_keys(
            work_pool_id=work_pool_id, message_id=message_id
        )
        lease_expires_ms = _score_ms(lease_expires_at)
        current_ms = _score_ms(current_time)

        for _ in range(_MAX_TRANSACTION_ATTEMPTS):
            async with self._client().pipeline(transaction=True) as pipe:
                try:
                    await pipe.watch(
                        keys.visible, keys.reserved, keys.message, keys.reservation
                    )
                    visible_score = await pipe.zscore(keys.visible, message_id)
                    if visible_score is None:
                        await pipe.reset()
                        return None

                    message_fields = _string_mapping(await pipe.hgetall(keys.message))
                    if not message_fields:
                        pipe.multi()
                        pipe.zrem(keys.visible, message_id)
                        await pipe.execute()
                        return None

                    if not self._message_matches_filters(
                        message_fields=message_fields,
                        work_pool_id=work_pool_id,
                        cleanup_kind_filter=cleanup_kind_filter,
                        queue_filter=queue_filter,
                    ):
                        await pipe.reset()
                        return None

                    reservation_fields = _string_mapping(
                        await pipe.hgetall(keys.reservation)
                    )
                    if self._reservation_is_active(
                        reservation_fields=reservation_fields,
                        current_ms=current_ms,
                    ):
                        pipe.multi()
                        pipe.zrem(keys.visible, message_id)
                        await pipe.execute()
                        return None

                    delivery_count = int(message_fields["delivery_count"])
                    if delivery_count >= self._policy().max_delivery_attempts:
                        pipe.multi()
                        self._stage_dead_letter(
                            pipe=pipe,
                            message_fields=message_fields,
                            reservation_fields=reservation_fields,
                            current_time=current_time,
                            reason="max_delivery_attempts_reached",
                        )
                        await pipe.execute()
                        return None

                    updated_fields = {
                        **message_fields,
                        "delivery_count": str(delivery_count + 1),
                        "updated_at": _format_datetime(current_time),
                    }
                    pipe.multi()
                    pipe.hset(keys.message, mapping=updated_fields)
                    pipe.hset(
                        keys.reservation,
                        mapping={
                            "token": reservation_token,
                            "lease_expires_at": _format_datetime(lease_expires_at),
                            "lease_expires_ms": str(lease_expires_ms),
                            "reserved_at": _format_datetime(current_time),
                        },
                    )
                    pipe.zrem(keys.visible, message_id)
                    pipe.zadd(keys.reserved, {message_id: lease_expires_ms})
                    await pipe.execute()

                    message = self._message_from_mapping(updated_fields)
                    return CleanupQueueReservation(
                        **message.model_dump(),
                        reservation_token=reservation_token,
                        lease_expires_at=lease_expires_at,
                    )
                except WatchError:
                    continue

        raise RuntimeError("Redis cleanup queue reserve transaction failed.")

    async def _run_operation(
        self,
        *,
        operation: CleanupQueueOperation,
        work_pool_id: UUID,
        message_id: UUID,
        reservation_token: str,
        release_reason: str | None = None,
    ) -> CleanupQueueOperationResult:
        current_time = now("UTC")
        current_ms = _score_ms(current_time)
        policy = self._policy()
        lease_expires_at = (
            current_time + policy.lease_duration if operation == "renew" else None
        )
        keys = self._scoped_message_keys(
            work_pool_id=work_pool_id, message_id=message_id
        )

        for _ in range(_MAX_TRANSACTION_ATTEMPTS):
            async with self._client().pipeline(transaction=True) as pipe:
                try:
                    await pipe.watch(
                        keys.message, keys.reservation, keys.visible, keys.reserved
                    )
                    message_fields = _string_mapping(await pipe.hgetall(keys.message))
                    reservation_fields = _string_mapping(
                        await pipe.hgetall(keys.reservation)
                    )

                    # Validate the current reservation before staging any mutation.
                    if not message_fields:
                        await pipe.reset()
                        return self._operation_result(
                            operation=operation,
                            message_id=message_id,
                            status="not_found",
                            reason="message_not_found",
                        )

                    if message_fields["work_pool_id"] != str(work_pool_id):
                        await pipe.reset()
                        return self._operation_result(
                            operation=operation,
                            message_id=message_id,
                            status="unauthorized",
                            reason="work_pool_mismatch",
                        )

                    if not reservation_fields:
                        await pipe.reset()
                        return self._operation_result(
                            operation=operation,
                            message_id=message_id,
                            status="not_current",
                            reason="no_active_reservation",
                        )

                    if reservation_fields.get("token") != reservation_token:
                        await pipe.reset()
                        return self._operation_result(
                            operation=operation,
                            message_id=message_id,
                            status="invalid_token",
                            reason="reservation_token_mismatch",
                        )

                    # An expired reservation fails the requested operation and either
                    # reopens the message or moves it to the dead-letter queue.
                    if int(reservation_fields.get("lease_expires_ms") or "0") <= (
                        current_ms
                    ):
                        pipe.multi()
                        if (
                            int(message_fields["delivery_count"])
                            >= policy.max_delivery_attempts
                        ):
                            dead_letter = self._stage_dead_letter(
                                pipe=pipe,
                                message_fields=message_fields,
                                reservation_fields=reservation_fields,
                                current_time=current_time,
                                reason="max_delivery_attempts_reached",
                            )
                            await pipe.execute()
                            return self._operation_result(
                                operation=operation,
                                message_id=message_id,
                                status="dead_lettered",
                                reason="max_delivery_attempts_reached",
                                dead_letter=dead_letter,
                            )

                        self._stage_redelivery(
                            pipe=pipe,
                            message_fields=message_fields,
                            current_time=current_time,
                            current_ms=current_ms,
                        )
                        await pipe.execute()
                        await self.wake_dispatchers(work_pool_id)
                        return self._operation_result(
                            operation=operation,
                            message_id=message_id,
                            status="expired",
                            reason="lease_expired",
                        )

                    if operation == "ack":
                        pipe.multi()
                        self._stage_ack(
                            pipe=pipe,
                            message_fields=message_fields,
                            current_time=current_time,
                            retention=policy.completed_idempotency_retention,
                        )
                        await pipe.execute()
                        return self._operation_result(
                            operation=operation,
                            message_id=message_id,
                            status="accepted",
                        )

                    if operation == "release":
                        pipe.multi()
                        if (
                            int(message_fields["delivery_count"])
                            >= policy.max_delivery_attempts
                        ):
                            dead_letter = self._stage_dead_letter(
                                pipe=pipe,
                                message_fields=message_fields,
                                reservation_fields=reservation_fields,
                                current_time=current_time,
                                reason="max_delivery_attempts_reached",
                                release_reason=release_reason,
                            )
                            await pipe.execute()
                            return self._operation_result(
                                operation=operation,
                                message_id=message_id,
                                status="dead_lettered",
                                reason="max_delivery_attempts_reached",
                                dead_letter=dead_letter,
                            )

                        self._stage_redelivery(
                            pipe=pipe,
                            message_fields=message_fields,
                            current_time=current_time,
                            current_ms=current_ms,
                        )
                        await pipe.execute()
                        await self.wake_dispatchers(work_pool_id)
                        return self._operation_result(
                            operation=operation,
                            message_id=message_id,
                            status="accepted",
                        )

                    if operation == "renew":
                        if lease_expires_at is None:
                            raise ValueError("lease_expires_at is required for renew")

                        pipe.multi()
                        self._stage_renew(
                            pipe=pipe,
                            message_fields=message_fields,
                            reservation_token=reservation_token,
                            current_time=current_time,
                            lease_expires_at=lease_expires_at,
                        )
                        await pipe.execute()
                        return self._operation_result(
                            operation=operation,
                            message_id=message_id,
                            status="accepted",
                            lease_expires_at=lease_expires_at,
                        )

                    raise ValueError(f"Unknown cleanup queue operation: {operation!r}")
                except WatchError:
                    continue

        raise RuntimeError("Redis cleanup queue operation transaction failed.")

    async def _expire_lease_candidate(
        self,
        *,
        work_pool_id: str,
        message_id: str,
        current_time: DateTime,
        current_ms: int,
    ) -> _LeaseExpiryOutcome:
        keys = self._scoped_message_keys(
            work_pool_id=work_pool_id, message_id=message_id
        )

        for _ in range(_MAX_TRANSACTION_ATTEMPTS):
            async with self._client().pipeline(transaction=True) as pipe:
                try:
                    await pipe.watch(
                        keys.visible, keys.reserved, keys.message, keys.reservation
                    )
                    reserved_score = await pipe.zscore(keys.reserved, message_id)
                    if reserved_score is None or reserved_score > current_ms:
                        await pipe.reset()
                        return None

                    message_fields = _string_mapping(await pipe.hgetall(keys.message))
                    reservation_fields = _string_mapping(
                        await pipe.hgetall(keys.reservation)
                    )

                    if not message_fields:
                        pipe.multi()
                        pipe.delete(keys.reservation)
                        pipe.zrem(keys.reserved, message_id)
                        await pipe.execute()
                        return None

                    reservation_lease_ms = int(
                        reservation_fields.get("lease_expires_ms") or "0"
                    )
                    if reservation_lease_ms > current_ms:
                        pipe.multi()
                        pipe.zadd(keys.reserved, {message_id: reservation_lease_ms})
                        await pipe.execute()
                        return None

                    pipe.multi()
                    if (
                        int(message_fields["delivery_count"])
                        >= self._policy().max_delivery_attempts
                    ):
                        dead_letter = self._stage_dead_letter(
                            pipe=pipe,
                            message_fields=message_fields,
                            reservation_fields=reservation_fields,
                            current_time=current_time,
                            reason="max_delivery_attempts_reached",
                        )
                        await pipe.execute()
                        return "dead_lettered", dead_letter

                    message = self._stage_redelivery(
                        pipe=pipe,
                        message_fields=message_fields,
                        current_time=current_time,
                        current_ms=current_ms,
                    )
                    await pipe.execute()
                    return "redelivered", message
                except WatchError:
                    continue

        raise RuntimeError("Redis cleanup queue lease expiry transaction failed.")

    async def _read_existing_message_from_keys(
        self,
        *,
        pipe: Any,
        keys: tuple[str, ...],
        idempotency_key: str,
        work_pool_id: UUID,
    ) -> CleanupQueueMessage | None:
        for key in keys:
            fields = _string_mapping(await pipe.hgetall(key))
            if not fields:
                continue

            if fields["idempotency_key"] != idempotency_key or fields[
                "work_pool_id"
            ] != str(work_pool_id):
                raise ValueError(
                    "message_id is already associated with a different cleanup message"
                )
            return self._message_from_mapping(fields)

        return None

    def _stage_ack(
        self,
        *,
        pipe: Any,
        message_fields: Mapping[str, str],
        current_time: DateTime,
        retention: timedelta | None,
    ) -> None:
        message_id = message_fields["message_id"]
        work_pool_id = message_fields["work_pool_id"]
        current_time_string = _format_datetime(current_time)
        acked_key = self._acked_key(message_id)

        pipe.hset(
            acked_key,
            mapping={
                **message_fields,
                "updated_at": current_time_string,
                "completed_at": current_time_string,
            },
        )
        pipe.delete(self._message_key(message_id))
        pipe.delete(self._reservation_key(message_id))
        pipe.zrem(self._visible_key(work_pool_id), message_id)
        pipe.zrem(self._reserved_key(work_pool_id), message_id)

        if retention is not None:
            retention_ms = int(retention.total_seconds() * 1000)
            pipe.pexpire(acked_key, retention_ms)
            pipe.pexpire(
                self._idempotency_key(work_pool_id, message_fields["idempotency_hash"]),
                retention_ms,
            )

    def _stage_redelivery(
        self,
        *,
        pipe: Any,
        message_fields: Mapping[str, str],
        current_time: DateTime,
        current_ms: int,
    ) -> CleanupQueueMessage:
        message_id = message_fields["message_id"]
        work_pool_id = message_fields["work_pool_id"]
        updated_fields = {
            **message_fields,
            "updated_at": _format_datetime(current_time),
        }
        pipe.delete(self._reservation_key(message_id))
        pipe.zrem(self._reserved_key(work_pool_id), message_id)
        pipe.hset(self._message_key(message_id), mapping=updated_fields)
        pipe.zadd(self._visible_key(work_pool_id), {message_id: current_ms})
        return self._message_from_mapping(updated_fields)

    def _stage_renew(
        self,
        *,
        pipe: Any,
        message_fields: Mapping[str, str],
        reservation_token: str,
        current_time: DateTime,
        lease_expires_at: DateTime,
    ) -> None:
        message_id = message_fields["message_id"]
        work_pool_id = message_fields["work_pool_id"]
        lease_expires_ms = _score_ms(lease_expires_at)
        pipe.hset(
            self._reservation_key(message_id),
            mapping={
                "token": reservation_token,
                "lease_expires_at": _format_datetime(lease_expires_at),
                "lease_expires_ms": str(lease_expires_ms),
            },
        )
        pipe.hset(
            self._message_key(message_id),
            mapping={
                **message_fields,
                "updated_at": _format_datetime(current_time),
            },
        )
        pipe.zadd(self._reserved_key(work_pool_id), {message_id: lease_expires_ms})

    def _stage_dead_letter(
        self,
        *,
        pipe: Any,
        message_fields: Mapping[str, str],
        reservation_fields: Mapping[str, str],
        current_time: DateTime,
        reason: str,
        release_reason: str | None = None,
    ) -> CleanupQueueDeadLetter:
        message_id = message_fields["message_id"]
        work_pool_id = message_fields["work_pool_id"]
        dead_fields = {
            **message_fields,
            "reason": reason,
            "final_delivery_count": message_fields.get("delivery_count") or "0",
            "moved_at": _format_datetime(current_time),
            "reservation_token": reservation_fields.get("token", ""),
            "lease_expires_at": reservation_fields.get("lease_expires_at", ""),
            "release_reason": release_reason or "",
        }
        pipe.hset(self._dead_key(message_id), mapping=dead_fields)
        pipe.delete(self._message_key(message_id))
        pipe.delete(self._reservation_key(message_id))
        pipe.zrem(self._visible_key(work_pool_id), message_id)
        pipe.zrem(self._reserved_key(work_pool_id), message_id)
        return self._dead_letter_from_mapping(dead_fields)

    def _client(self) -> "Redis":
        if self._redis_client is not None:
            return self._redis_client

        settings = RedisWorkerCleanupQueueSettings()
        if settings.url:
            self._redis_client = Redis.from_url(
                settings.url,
                health_check_interval=settings.health_check_interval,
                decode_responses=True,
            )
            return self._redis_client

        self._redis_client = Redis(
            host=settings.host,
            port=settings.port,
            db=settings.db,
            username=settings.username,
            password=settings.password,
            health_check_interval=settings.health_check_interval,
            ssl=settings.ssl,
            decode_responses=True,
        )
        return self._redis_client

    def _prefix(self) -> str:
        if self._key_prefix is not None:
            return self._key_prefix.rstrip(":")

        return RedisWorkerCleanupQueueSettings().key_prefix.rstrip(":")

    async def _work_pools(self) -> list[str]:
        return [
            _decode_redis_value(work_pool_id)
            for work_pool_id in await self._client().smembers(self._pools_key())
        ]

    def _scoped_message_keys(
        self, *, work_pool_id: UUID | str, message_id: UUID | str
    ) -> _ScopedMessageKeys:
        return _ScopedMessageKeys(
            message=self._message_key(message_id),
            reservation=self._reservation_key(message_id),
            visible=self._visible_key(work_pool_id),
            reserved=self._reserved_key(work_pool_id),
        )

    def _message_key(self, message_id: UUID | str) -> str:
        return f"{self._prefix()}:messages:{message_id}"

    def _reservation_key(self, message_id: UUID | str) -> str:
        return f"{self._prefix()}:reservations:{message_id}"

    def _dead_key(self, message_id: UUID | str) -> str:
        return f"{self._prefix()}:dead:{message_id}"

    def _acked_key(self, message_id: UUID | str) -> str:
        return f"{self._prefix()}:acked:{message_id}"

    def _idempotency_key(self, work_pool_id: UUID | str, idempotency_hash: str) -> str:
        return f"{self._prefix()}:idempotency:{work_pool_id}:{idempotency_hash}"

    def _visible_key(self, work_pool_id: UUID | str) -> str:
        return f"{self._prefix()}:pool:{work_pool_id}:visible"

    def _reserved_key(self, work_pool_id: UUID | str) -> str:
        return f"{self._prefix()}:pool:{work_pool_id}:reserved"

    def _wakeup_key(self, work_pool_id: UUID | str) -> str:
        return f"{self._prefix()}:wakeup:{work_pool_id}"

    def _pools_key(self) -> str:
        return f"{self._prefix()}:pools"

    @staticmethod
    def _message_matches_filters(
        *,
        message_fields: Mapping[str, str],
        work_pool_id: UUID,
        cleanup_kind_filter: set[str] | None,
        queue_filter: set[str] | None,
    ) -> bool:
        if message_fields["work_pool_id"] != str(work_pool_id):
            return False
        if (
            cleanup_kind_filter is not None
            and message_fields["kind"] not in cleanup_kind_filter
        ):
            return False
        if (
            queue_filter is not None
            and message_fields["work_queue_id"] not in queue_filter
        ):
            return False
        return True

    @staticmethod
    def _reservation_is_active(
        *, reservation_fields: Mapping[str, str], current_ms: int
    ) -> bool:
        if not reservation_fields:
            return False
        return int(reservation_fields.get("lease_expires_ms") or "0") > current_ms

    @staticmethod
    def _queue_preference_passes(
        *,
        preferred_work_queue_ids: Iterable[UUID] | None,
        allow_fallback_to_any_queue: bool,
    ) -> tuple[set[str] | None, ...]:
        if preferred_work_queue_ids is None:
            return (None,)

        preferred_queue_filter = {
            str(queue_id) for queue_id in preferred_work_queue_ids
        }
        if allow_fallback_to_any_queue:
            return (preferred_queue_filter, None)
        return (preferred_queue_filter,)

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
            "kind": str(kind),
            "target": json.dumps(dict(target), separators=(",", ":")),
            "data": json.dumps(dict(data or {}), separators=(",", ":")),
            "created_at": _format_datetime(current_time),
            "updated_at": _format_datetime(current_time),
            "delivery_count": "0",
        }

    @staticmethod
    def _message_from_mapping(fields: Mapping[str, str]) -> CleanupQueueMessage:
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

    def _dead_letter_from_mapping(
        self, fields: Mapping[str, str]
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

    @staticmethod
    def _operation_result(
        *,
        operation: CleanupQueueOperation,
        message_id: UUID,
        status: CleanupOperationStatus,
        lease_expires_at: DateTime | None = None,
        reason: str | None = None,
        dead_letter: CleanupQueueDeadLetter | None = None,
    ) -> CleanupQueueOperationResult:
        return CleanupQueueOperationResult(
            message_id=message_id,
            operation=operation,
            status=status,
            lease_expires_at=lease_expires_at,
            reason=reason,
            dead_letter=dead_letter,
        )

    @staticmethod
    def _policy() -> _QueuePolicy:
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


def _string_mapping(fields: Mapping[Any, Any]) -> dict[str, str]:
    return {
        _decode_redis_value(key): _decode_redis_value(value)
        for key, value in fields.items()
    }


def _decode_redis_value(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode()
    return str(value)


def _format_datetime(value: DateTime) -> str:
    return value.isoformat()


def _score_ms(value: DateTime) -> int:
    return int(value.timestamp() * 1000)


def _idempotency_hash(idempotency_key: str) -> str:
    return sha256(idempotency_key.encode()).hexdigest()
