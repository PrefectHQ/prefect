from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest
from prefect_redis import cleanup_queue as redis_module
from prefect_redis.cleanup_queue import (
    RedisWorkerCleanupQueueSettings,
    WorkerCleanupQueue,
)
from redis.asyncio import Redis

from prefect.client.schemas.worker_channel import CANCELLING_TIMEOUT_TEARDOWN
from prefect.server.worker_communication.cleanup_queue import get_worker_cleanup_queue
from prefect.settings import (
    PREFECT_SERVER_WORKER_CHANNEL_CLEANUP_LEASE_SECONDS,
    PREFECT_SERVER_WORKER_CHANNEL_CLEANUP_MAX_DELIVERY_ATTEMPTS,
    PREFECT_SERVER_WORKER_CHANNEL_CLEANUP_QUEUE_STORAGE,
    temporary_settings,
)

CleanupPolicySettings = Callable[..., AbstractContextManager[None]]


@dataclass
class Clock:
    current: datetime

    def advance(self, duration: timedelta) -> None:
        self.current += duration


@pytest.fixture
async def queue(redis: Redis) -> AsyncGenerator[WorkerCleanupQueue, None]:
    key_prefix = f"prefect:test:cleanup:{uuid4()}"
    queue = WorkerCleanupQueue(redis_client=redis, key_prefix=key_prefix)
    yield queue
    keys = [key async for key in redis.scan_iter(f"{key_prefix}:*")]
    if keys:
        await redis.delete(*keys)


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    clock = Clock(datetime(2026, 5, 27, 12, 0, tzinfo=timezone.utc))
    monkeypatch.setattr(redis_module, "now", lambda timezone: clock.current)
    return clock


@pytest.fixture
def cleanup_policy_settings() -> CleanupPolicySettings:
    @contextmanager
    def settings(
        *,
        lease_seconds: float | None = None,
        max_delivery_attempts: int | None = None,
    ) -> Iterator[None]:
        values: dict[Any, Any] = {}
        if lease_seconds is not None:
            values[PREFECT_SERVER_WORKER_CHANNEL_CLEANUP_LEASE_SECONDS] = lease_seconds
        if max_delivery_attempts is not None:
            values[PREFECT_SERVER_WORKER_CHANNEL_CLEANUP_MAX_DELIVERY_ATTEMPTS] = (
                max_delivery_attempts
            )

        with temporary_settings(values):
            yield

    return settings


def _target() -> dict[str, str]:
    return {"flow_run_id": str(uuid4())}


async def _enqueue_message(
    queue: WorkerCleanupQueue,
    *,
    work_pool_id: UUID | None = None,
    message_id: UUID | None = None,
    idempotency_key: str = "cleanup-key",
    work_queue_id: UUID | None = None,
) -> UUID:
    message_id = message_id or uuid4()
    await queue.enqueue(
        message_id=message_id,
        idempotency_key=idempotency_key,
        work_pool_id=work_pool_id or uuid4(),
        kind=CANCELLING_TIMEOUT_TEARDOWN,
        target=_target(),
        work_queue_id=work_queue_id,
    )
    return message_id


async def test_get_worker_cleanup_queue_can_select_redis_backend() -> None:
    with temporary_settings(
        {
            PREFECT_SERVER_WORKER_CHANNEL_CLEANUP_QUEUE_STORAGE: "prefect_redis.cleanup_queue",
        }
    ):
        assert isinstance(get_worker_cleanup_queue(), WorkerCleanupQueue)


def test_redis_worker_cleanup_queue_settings_use_integration_namespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "PREFECT_REDIS_WORKER_CLEANUP_QUEUE_KEY_PREFIX",
        "prefect:test:worker-cleanup",
    )
    monkeypatch.setenv(
        "PREFECT_REDIS_WORKER_CLEANUP_QUEUE_URL",
        "redis://localhost:6379/4",
    )

    settings = RedisWorkerCleanupQueueSettings()

    assert settings.key_prefix == "prefect:test:worker-cleanup"
    assert settings.url == "redis://localhost:6379/4"


async def test_redis_enqueue_is_idempotent_for_cleanup_key(
    queue: WorkerCleanupQueue,
) -> None:
    work_pool_id = uuid4()
    first_message_id = uuid4()
    second_message_id = uuid4()

    first = await queue.enqueue(
        message_id=first_message_id,
        idempotency_key="flow-run-cleanup",
        work_pool_id=work_pool_id,
        kind=CANCELLING_TIMEOUT_TEARDOWN,
        target=_target(),
    )
    second = await queue.enqueue(
        message_id=second_message_id,
        idempotency_key="flow-run-cleanup",
        work_pool_id=work_pool_id,
        kind=CANCELLING_TIMEOUT_TEARDOWN,
        target=_target(),
    )

    assert second.message_id == first.message_id
    assert second.message_id != second_message_id


async def test_redis_message_ids_are_scoped_by_work_pool(
    queue: WorkerCleanupQueue,
) -> None:
    message_id = uuid4()
    first_work_pool_id = uuid4()
    second_work_pool_id = uuid4()

    first = await queue.enqueue(
        message_id=message_id,
        idempotency_key="flow-run-cleanup",
        work_pool_id=first_work_pool_id,
        kind=CANCELLING_TIMEOUT_TEARDOWN,
        target=_target(),
    )
    second = await queue.enqueue(
        message_id=message_id,
        idempotency_key="flow-run-cleanup",
        work_pool_id=second_work_pool_id,
        kind=CANCELLING_TIMEOUT_TEARDOWN,
        target=_target(),
    )
    first_reservation = await queue.reserve(work_pool_id=first_work_pool_id)
    second_reservation = await queue.reserve(work_pool_id=second_work_pool_id)

    assert first.message_id == message_id
    assert second.message_id == message_id
    assert first.work_pool_id == first_work_pool_id
    assert second.work_pool_id == second_work_pool_id
    assert first_reservation is not None
    assert first_reservation.work_pool_id == first_work_pool_id
    assert second_reservation is not None
    assert second_reservation.work_pool_id == second_work_pool_id


async def test_redis_enqueue_after_ack_keeps_idempotency_completed(
    queue: WorkerCleanupQueue,
) -> None:
    work_pool_id = uuid4()
    message_id = uuid4()
    idempotency_key = "flow-run-cleanup"
    first = await queue.enqueue(
        message_id=message_id,
        idempotency_key=idempotency_key,
        work_pool_id=work_pool_id,
        kind=CANCELLING_TIMEOUT_TEARDOWN,
        target=_target(),
    )
    reservation = await queue.reserve(work_pool_id=work_pool_id)
    assert reservation is not None
    accepted = await queue.ack(
        work_pool_id=work_pool_id,
        message_id=message_id,
        reservation_token=reservation.reservation_token,
    )

    duplicate = await queue.enqueue(
        message_id=uuid4(),
        idempotency_key=idempotency_key,
        work_pool_id=work_pool_id,
        kind=CANCELLING_TIMEOUT_TEARDOWN,
        target=_target(),
    )

    assert accepted.status == "accepted"
    assert duplicate.message_id == first.message_id
    assert await queue.reserve(work_pool_id=work_pool_id) is None


async def test_redis_operations_require_current_reservation_token(
    queue: WorkerCleanupQueue,
) -> None:
    work_pool_id = uuid4()
    message_id = await _enqueue_message(queue, work_pool_id=work_pool_id)
    reservation = await queue.reserve(work_pool_id=work_pool_id)
    assert reservation is not None

    rejected = await queue.ack(
        work_pool_id=work_pool_id,
        message_id=message_id,
        reservation_token="not-the-current-token",
    )
    accepted = await queue.ack(
        work_pool_id=work_pool_id,
        message_id=message_id,
        reservation_token=reservation.reservation_token,
    )

    assert rejected.status == "invalid_token"
    assert rejected.reason == "reservation_token_mismatch"
    assert accepted.status == "accepted"
    assert (
        await queue.read_message(work_pool_id=work_pool_id, message_id=message_id)
        is None
    )


async def test_redis_stale_reservation_token_is_rejected_after_redelivery(
    queue: WorkerCleanupQueue,
) -> None:
    work_pool_id = uuid4()
    message_id = await _enqueue_message(queue, work_pool_id=work_pool_id)
    first = await queue.reserve(work_pool_id=work_pool_id)
    assert first is not None

    released = await queue.release(
        work_pool_id=work_pool_id,
        message_id=message_id,
        reservation_token=first.reservation_token,
        reason="cannot_act",
    )
    second = await queue.reserve(work_pool_id=work_pool_id)
    assert second is not None

    stale_ack = await queue.ack(
        work_pool_id=work_pool_id,
        message_id=message_id,
        reservation_token=first.reservation_token,
    )

    assert released.status == "accepted"
    assert second.reservation_token != first.reservation_token
    assert stale_ack.status == "invalid_token"


async def test_redis_release_moves_message_to_dead_letter_at_retry_limit(
    queue: WorkerCleanupQueue,
    cleanup_policy_settings: CleanupPolicySettings,
) -> None:
    work_pool_id = uuid4()
    message_id = await _enqueue_message(queue, work_pool_id=work_pool_id)

    with cleanup_policy_settings(max_delivery_attempts=1):
        reservation = await queue.reserve(work_pool_id=work_pool_id)
        assert reservation is not None

        result = await queue.release(
            work_pool_id=work_pool_id,
            message_id=message_id,
            reservation_token=reservation.reservation_token,
            reason="unsupported_cleanup_kind",
        )

    dead_letter = await queue.read_dead_letter(
        work_pool_id=work_pool_id, message_id=message_id
    )

    assert result.status == "dead_lettered"
    assert result.reason == "max_delivery_attempts_reached"
    assert dead_letter is not None
    assert dead_letter.final_delivery_count == 1
    assert dead_letter.release_reason == "unsupported_cleanup_kind"
    assert await queue.reserve(work_pool_id=work_pool_id) is None


async def test_redis_operation_on_expired_reservation_redelivers_message(
    queue: WorkerCleanupQueue,
    clock: Clock,
    cleanup_policy_settings: CleanupPolicySettings,
) -> None:
    work_pool_id = uuid4()
    message_id = await _enqueue_message(queue, work_pool_id=work_pool_id)
    with cleanup_policy_settings(lease_seconds=10.0, max_delivery_attempts=2):
        first = await queue.reserve(work_pool_id=work_pool_id)
        assert first is not None

        clock.advance(timedelta(seconds=11))
        expired = await queue.renew(
            work_pool_id=work_pool_id,
            message_id=message_id,
            reservation_token=first.reservation_token,
        )
        second = await queue.reserve(work_pool_id=work_pool_id)

    assert expired.status == "expired"
    assert expired.reason == "lease_expired"
    assert second is not None
    assert second.message_id == message_id
    assert second.delivery_count == 2
    assert second.reservation_token != first.reservation_token


async def test_redis_concurrent_reserve_attempts_create_one_reservation(
    queue: WorkerCleanupQueue,
) -> None:
    work_pool_id = uuid4()
    message_id = await _enqueue_message(queue, work_pool_id=work_pool_id)

    reservations = await asyncio.gather(
        *(queue.reserve(work_pool_id=work_pool_id) for _ in range(10))
    )

    accepted = [reservation for reservation in reservations if reservation is not None]
    assert len(accepted) == 1
    assert accepted[0].message_id == message_id
    assert accepted[0].delivery_count == 1


async def test_redis_wait_for_wakeup_observes_shared_sequence(redis: Redis) -> None:
    work_pool_id = uuid4()
    key_prefix = f"prefect:test:cleanup:{uuid4()}"
    waiting_queue = WorkerCleanupQueue(redis_client=redis, key_prefix=key_prefix)
    waking_queue = WorkerCleanupQueue(redis_client=redis, key_prefix=key_prefix)
    sequence = await waiting_queue.read_wakeup_sequence(work_pool_id)

    waiter = asyncio.create_task(
        waiting_queue.wait_for_wakeup(work_pool_id, after=sequence, timeout=2)
    )
    await waking_queue.wake_dispatchers(work_pool_id)
    wakeup = await waiter

    keys = [key async for key in redis.scan_iter(f"{key_prefix}:*")]
    if keys:
        await redis.delete(*keys)

    assert wakeup is not None
    assert wakeup.work_pool_id == work_pool_id
    assert wakeup.sequence == sequence + 1
