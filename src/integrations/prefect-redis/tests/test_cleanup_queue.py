from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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
    PREFECT_SERVER_WORKER_CHANNEL_CLEANUP_QUEUE_STORAGE,
    temporary_settings,
)
from prefect.testing.standard_test_suites import WorkerCleanupQueueStandardTestSuite


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


class TestRedisWorkerCleanupQueue(WorkerCleanupQueueStandardTestSuite):
    pass


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
    monkeypatch.setenv("PREFECT_REDIS_WORKER_CLEANUP_QUEUE_SOCKET_TIMEOUT", "10.0")
    monkeypatch.setenv(
        "PREFECT_REDIS_WORKER_CLEANUP_QUEUE_SOCKET_CONNECT_TIMEOUT", "3.5"
    )
    monkeypatch.setenv("PREFECT_REDIS_WORKER_CLEANUP_QUEUE_PROTOCOL", "3")

    settings = RedisWorkerCleanupQueueSettings()

    assert settings.key_prefix == "prefect:test:worker-cleanup"
    assert settings.url == "redis://localhost:6379/4"
    assert settings.socket_timeout == 10.0
    assert settings.socket_connect_timeout == 3.5
    assert settings.protocol == 3


async def test_redis_worker_cleanup_queue_client_preserves_connection_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PREFECT_REDIS_WORKER_CLEANUP_QUEUE_URL", raising=False)

    queue = WorkerCleanupQueue()
    client = queue._client()
    conn_kwargs = client.connection_pool.connection_kwargs

    assert conn_kwargs.get("socket_timeout") is None
    assert conn_kwargs.get("socket_connect_timeout") is None
    assert conn_kwargs.get("protocol") == 2
    await client.aclose()


async def test_redis_worker_cleanup_queue_url_client_preserves_connection_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "PREFECT_REDIS_WORKER_CLEANUP_QUEUE_URL", "redis://localhost:6379/4"
    )

    queue = WorkerCleanupQueue()
    client = queue._client()
    conn_kwargs = client.connection_pool.connection_kwargs

    assert conn_kwargs.get("socket_timeout") is None
    assert conn_kwargs.get("socket_connect_timeout") is None
    assert conn_kwargs.get("protocol") == 2
    await client.aclose()


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


async def test_redis_duplicate_enqueue_wakes_when_existing_message_is_visible(
    queue: WorkerCleanupQueue,
) -> None:
    work_pool_id = uuid4()
    first = await queue.enqueue(
        message_id=uuid4(),
        idempotency_key="flow-run-cleanup",
        work_pool_id=work_pool_id,
        kind=CANCELLING_TIMEOUT_TEARDOWN,
        target=_target(),
    )
    wakeup_sequence = await queue.read_wakeup_sequence(work_pool_id)

    duplicate = await queue.enqueue(
        message_id=uuid4(),
        idempotency_key="flow-run-cleanup",
        work_pool_id=work_pool_id,
        kind=CANCELLING_TIMEOUT_TEARDOWN,
        target=_target(),
    )

    assert duplicate.message_id == first.message_id
    assert await queue.read_wakeup_sequence(work_pool_id) == wakeup_sequence + 1


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


async def test_redis_release_redelivery_advances_wakeup_in_transaction(
    queue: WorkerCleanupQueue,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    work_pool_id = uuid4()
    message_id = await _enqueue_message(queue, work_pool_id=work_pool_id)
    reservation = await queue.reserve(work_pool_id=work_pool_id)
    assert reservation is not None
    sequence = await queue.read_wakeup_sequence(work_pool_id)

    async def fail_separate_wakeup(work_pool_id: UUID) -> None:
        raise AssertionError("release should not wake with a separate Redis command")

    monkeypatch.setattr(queue, "wake_dispatchers", fail_separate_wakeup)

    result = await queue.release(
        work_pool_id=work_pool_id,
        message_id=message_id,
        reservation_token=reservation.reservation_token,
        reason="cannot_act",
    )
    redelivery = await queue.reserve(work_pool_id=work_pool_id)

    assert result.status == "accepted"
    assert await queue.read_wakeup_sequence(work_pool_id) == sequence + 1
    assert redelivery is not None
    assert redelivery.message_id == message_id
    assert redelivery.delivery_count == 2


async def test_redis_expire_leases_redelivery_advances_wakeup_in_transaction(
    queue: WorkerCleanupQueue,
    clock: Clock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    work_pool_id = uuid4()
    message_id = await _enqueue_message(queue, work_pool_id=work_pool_id)
    reservation = await queue.reserve(work_pool_id=work_pool_id)
    assert reservation is not None
    sequence = await queue.read_wakeup_sequence(work_pool_id)

    async def fail_separate_wakeup(work_pool_id: UUID) -> None:
        raise AssertionError(
            "lease expiry should not wake with a separate Redis command"
        )

    monkeypatch.setattr(queue, "wake_dispatchers", fail_separate_wakeup)
    clock.advance(timedelta(minutes=1))

    result = await queue.expire_leases(work_pool_id=work_pool_id)
    redelivery = await queue.reserve(work_pool_id=work_pool_id)

    assert [message.message_id for message in result.redelivered] == [message_id]
    assert await queue.read_wakeup_sequence(work_pool_id) == sequence + 1
    assert redelivery is not None
    assert redelivery.message_id == message_id
    assert redelivery.delivery_count == 2


async def test_redis_reserve_scans_visible_messages_in_batches(
    queue: WorkerCleanupQueue,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(WorkerCleanupQueue, "_VISIBLE_SCAN_BATCH_SIZE", 2)
    work_pool_id = uuid4()
    preferred_work_queue_id = uuid4()
    first_unmatched_message_id = UUID(int=1)
    second_unmatched_message_id = UUID(int=2)
    preferred_message_id = UUID(int=3)

    await _enqueue_message(
        queue,
        work_pool_id=work_pool_id,
        message_id=first_unmatched_message_id,
        idempotency_key="first-unmatched-cleanup",
        work_queue_id=uuid4(),
    )
    await _enqueue_message(
        queue,
        work_pool_id=work_pool_id,
        message_id=second_unmatched_message_id,
        idempotency_key="second-unmatched-cleanup",
        work_queue_id=uuid4(),
    )
    await _enqueue_message(
        queue,
        work_pool_id=work_pool_id,
        message_id=preferred_message_id,
        idempotency_key="preferred-cleanup",
        work_queue_id=preferred_work_queue_id,
    )

    reservation = await queue.reserve(
        work_pool_id=work_pool_id,
        preferred_work_queue_ids=[preferred_work_queue_id],
        allow_fallback_to_any_queue=False,
    )

    assert reservation is not None
    assert reservation.message_id == preferred_message_id


async def test_redis_reserve_does_not_skip_after_cleaning_stale_visible_entries(
    queue: WorkerCleanupQueue,
    redis: Redis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(WorkerCleanupQueue, "_VISIBLE_SCAN_BATCH_SIZE", 2)
    work_pool_id = uuid4()
    first_stale_message_id = UUID(int=1)
    second_stale_message_id = UUID(int=2)
    eligible_message_id = UUID(int=3)

    await _enqueue_message(
        queue,
        work_pool_id=work_pool_id,
        message_id=first_stale_message_id,
        idempotency_key="first-stale-cleanup",
    )
    await _enqueue_message(
        queue,
        work_pool_id=work_pool_id,
        message_id=second_stale_message_id,
        idempotency_key="second-stale-cleanup",
    )
    await _enqueue_message(
        queue,
        work_pool_id=work_pool_id,
        message_id=eligible_message_id,
        idempotency_key="eligible-cleanup",
    )

    await redis.delete(
        queue._message_key(work_pool_id, first_stale_message_id),
        queue._message_key(work_pool_id, second_stale_message_id),
    )

    reservation = await queue.reserve(work_pool_id=work_pool_id)

    assert reservation is not None
    assert reservation.message_id == eligible_message_id


async def test_redis_reserve_does_not_skip_when_visible_set_shrinks_between_batches(
    queue: WorkerCleanupQueue,
    redis: Redis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(WorkerCleanupQueue, "_VISIBLE_SCAN_BATCH_SIZE", 1)
    work_pool_id = uuid4()
    preferred_work_queue_id = uuid4()
    unmatched_message_id = UUID(int=1)
    preferred_message_id = UUID(int=2)

    await _enqueue_message(
        queue,
        work_pool_id=work_pool_id,
        message_id=unmatched_message_id,
        idempotency_key="unmatched-cleanup",
        work_queue_id=uuid4(),
    )
    await _enqueue_message(
        queue,
        work_pool_id=work_pool_id,
        message_id=preferred_message_id,
        idempotency_key="preferred-cleanup",
        work_queue_id=preferred_work_queue_id,
    )

    original_zscore = redis.zscore

    async def zscore_and_remove_seen_member(name: str, value: str) -> float | None:
        score = await original_zscore(name, value)
        if value == str(unmatched_message_id) and score is not None:
            await redis.zrem(name, value)
        return score

    monkeypatch.setattr(redis, "zscore", zscore_and_remove_seen_member)

    reservation = await queue.reserve(
        work_pool_id=work_pool_id,
        preferred_work_queue_ids=[preferred_work_queue_id],
        allow_fallback_to_any_queue=False,
    )

    assert reservation is not None
    assert reservation.message_id == preferred_message_id


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
