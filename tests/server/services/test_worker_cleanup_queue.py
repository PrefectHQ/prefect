from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from prefect.client.schemas.worker_channel import CANCELLING_TIMEOUT_TEARDOWN
from prefect.server.services.worker_cleanup_queue import expire_worker_cleanup_leases
from prefect.server.worker_communication.cleanup_queue import memory as memory_module
from prefect.server.worker_communication.cleanup_queue.memory import WorkerCleanupQueue
from prefect.settings import (
    PREFECT_SERVER_WORKER_CHANNEL_CLEANUP_LEASE_SECONDS,
    PREFECT_SERVER_WORKER_CHANNEL_CLEANUP_MAX_DELIVERY_ATTEMPTS,
    temporary_settings,
)
from prefect.settings.context import get_current_settings


@dataclass
class Clock:
    current: datetime

    def advance(self, duration: timedelta) -> None:
        self.current += duration


@pytest.fixture
def queue() -> WorkerCleanupQueue:
    queue = WorkerCleanupQueue()
    queue.clear()
    return queue


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    clock = Clock(datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc))
    monkeypatch.setattr(memory_module, "now", lambda timezone: clock.current)
    return clock


def _target() -> dict[str, str]:
    return {"flow_run_id": str(uuid4())}


async def _enqueue_message(
    queue: WorkerCleanupQueue,
    *,
    work_pool_id: UUID,
    idempotency_key: str = "cleanup-key",
) -> UUID:
    message_id = uuid4()
    await queue.enqueue(
        message_id=message_id,
        idempotency_key=idempotency_key,
        work_pool_id=work_pool_id,
        kind=CANCELLING_TIMEOUT_TEARDOWN,
        target=_target(),
    )
    return message_id


async def test_expire_worker_cleanup_leases_redelivers_expired_messages(
    queue: WorkerCleanupQueue,
    clock: Clock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    work_pool_id = uuid4()
    message_id = await _enqueue_message(queue, work_pool_id=work_pool_id)

    with temporary_settings(
        {PREFECT_SERVER_WORKER_CHANNEL_CLEANUP_LEASE_SECONDS: 10.0}
    ):
        reservation = await queue.reserve(work_pool_id=work_pool_id)
        assert reservation is not None
        clock.advance(timedelta(seconds=11))

        with caplog.at_level(
            logging.INFO, logger="prefect.server.services.worker_cleanup_queue"
        ):
            result = await expire_worker_cleanup_leases(cleanup_queue=queue)

    assert [message.message_id for message in result.redelivered] == [message_id]
    assert result.dead_lettered == []
    assert (
        await queue.read_message(work_pool_id=work_pool_id, message_id=message_id)
        is not None
    )
    assert "redelivered=1 dead_lettered=0" in caplog.text


async def test_expire_worker_cleanup_leases_logs_dead_letter_context(
    queue: WorkerCleanupQueue,
    clock: Clock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    work_pool_id = uuid4()
    message_id = await _enqueue_message(queue, work_pool_id=work_pool_id)

    with temporary_settings(
        {
            PREFECT_SERVER_WORKER_CHANNEL_CLEANUP_LEASE_SECONDS: 10.0,
            PREFECT_SERVER_WORKER_CHANNEL_CLEANUP_MAX_DELIVERY_ATTEMPTS: 1,
        }
    ):
        reservation = await queue.reserve(work_pool_id=work_pool_id)
        assert reservation is not None
        clock.advance(timedelta(seconds=11))

        with caplog.at_level(
            logging.WARNING,
            logger="prefect.server.worker_communication.cleanup_queue",
        ):
            result = await expire_worker_cleanup_leases(cleanup_queue=queue)

    assert [dead.message.message_id for dead in result.dead_lettered] == [message_id]
    assert result.redelivered == []
    log_text = caplog.text
    assert str(message_id) in log_text
    assert str(work_pool_id) in log_text
    assert CANCELLING_TIMEOUT_TEARDOWN in log_text
    assert "final_delivery_count=1" in log_text
    assert "reason=max_delivery_attempts_reached" in log_text
    assert "source=memory_cleanup_queue" in log_text


async def test_expire_worker_cleanup_leases_uses_configured_batch_size(
    queue: WorkerCleanupQueue,
    clock: Clock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_current_settings()
    monkeypatch.setattr(settings.server.services.worker_cleanup_queue, "batch_size", 1)
    work_pool_id = uuid4()
    first_message_id = await _enqueue_message(
        queue, work_pool_id=work_pool_id, idempotency_key="first"
    )
    second_message_id = await _enqueue_message(
        queue, work_pool_id=work_pool_id, idempotency_key="second"
    )

    with temporary_settings(
        {PREFECT_SERVER_WORKER_CHANNEL_CLEANUP_LEASE_SECONDS: 10.0}
    ):
        assert await queue.reserve(work_pool_id=work_pool_id) is not None
        assert await queue.reserve(work_pool_id=work_pool_id) is not None
        clock.advance(timedelta(seconds=11))

        first_result = await expire_worker_cleanup_leases(cleanup_queue=queue)
        second_result = await expire_worker_cleanup_leases(cleanup_queue=queue)

    assert len(first_result.redelivered) == 1
    assert len(second_result.redelivered) == 1
    assert {
        first_result.redelivered[0].message_id,
        second_result.redelivered[0].message_id,
    } == {first_message_id, second_message_id}
