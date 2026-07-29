from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import pytest
from pydantic import ValidationError

from prefect._internal.uuid7 import uuid7
from prefect.server.worker_communication.cleanup_queue import (
    cleanup_queue_message_id,
    enqueue_pending_claim_teardown,
    get_worker_cleanup_queue,
)
from prefect.server.worker_communication.cleanup_queue import memory as memory_module
from prefect.server.worker_communication.cleanup_queue.memory import WorkerCleanupQueue
from prefect.settings import (
    PREFECT_SERVER_WORKER_CHANNEL_CLEANUP_QUEUE_STORAGE,
    temporary_settings,
)
from prefect.settings.context import get_current_settings
from prefect.testing.standard_test_suites import WorkerCleanupQueueStandardTestSuite


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
    clock = Clock(datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc))
    monkeypatch.setattr(memory_module, "now", lambda timezone: clock.current)
    return clock


class TestMemoryWorkerCleanupQueue(WorkerCleanupQueueStandardTestSuite):
    pass


def test_cleanup_queue_message_id_uses_stable_producer_namespace():
    key = (
        "pending_claim_teardown.v1:"
        "00000000-0000-0000-0000-000000000001:"
        "00000000-0000-0000-0000-000000000002"
    )

    assert str(cleanup_queue_message_id(key)) == (
        "5bafa77f-395f-542c-8cb6-6b49c698f3df"
    )
    assert cleanup_queue_message_id(key) == cleanup_queue_message_id(key)
    assert cleanup_queue_message_id(f"{key}:different") != cleanup_queue_message_id(key)


def test_cleanup_queue_message_id_rejects_empty_producer_identity():
    with pytest.raises(ValueError, match="non-empty"):
        cleanup_queue_message_id("")


async def test_enqueue_pending_claim_teardown_authors_strict_queue_payload(
    queue: WorkerCleanupQueue,
) -> None:
    work_pool_id = uuid4()
    work_queue_id = uuid4()
    flow_run_id = uuid4()
    claim_id = uuid7()
    execution_id = uuid7()

    message = await enqueue_pending_claim_teardown(
        queue,
        work_pool_id=work_pool_id,
        work_queue_id=work_queue_id,
        flow_run_id=flow_run_id,
        claim_id=claim_id,
        execution_id=execution_id,
        infrastructure_pid="provider/resource",
        data={"region": "us-east"},
    )

    expected_key = f"pending_claim_teardown.v1:{flow_run_id}:{claim_id}"
    assert message.message_id == cleanup_queue_message_id(expected_key)
    assert message.idempotency_key == expected_key
    assert message.kind == "pending_claim_teardown.v1"
    assert message.work_pool_id == work_pool_id
    assert message.work_queue_id == work_queue_id
    assert message.target == {
        "flow_run_id": str(flow_run_id),
        "claim_id": str(claim_id),
        "execution_id": str(execution_id),
        "infrastructure_pid": "provider/resource",
    }
    assert "work_pool_id" not in message.target
    assert "work_queue_id" not in message.target
    assert message.data == {"region": "us-east"}

    duplicate = await enqueue_pending_claim_teardown(
        queue,
        work_pool_id=work_pool_id,
        work_queue_id=uuid4(),
        flow_run_id=flow_run_id,
        claim_id=claim_id,
        execution_id=uuid7(),
        infrastructure_pid="different/resource",
    )

    assert duplicate == message


@pytest.mark.parametrize("identifier", ["claim_id", "execution_id"])
async def test_enqueue_pending_claim_teardown_requires_protocol_uuid7(
    queue: WorkerCleanupQueue,
    identifier: str,
) -> None:
    identifiers = {
        "claim_id": uuid7(),
        "execution_id": uuid7(),
    }
    identifiers[identifier] = uuid4()

    with pytest.raises(ValidationError):
        await enqueue_pending_claim_teardown(
            queue,
            work_pool_id=uuid4(),
            flow_run_id=uuid4(),
            **identifiers,
        )


async def test_get_worker_cleanup_queue_uses_default_in_memory_backend() -> None:
    settings = get_current_settings()

    assert (
        settings.server.worker_channel.cleanup_queue_storage
        == "prefect.server.worker_communication.cleanup_queue.memory"
    )
    assert isinstance(get_worker_cleanup_queue(), WorkerCleanupQueue)


async def test_get_worker_cleanup_queue_rejects_interface_module() -> None:
    with temporary_settings(
        {
            PREFECT_SERVER_WORKER_CHANNEL_CLEANUP_QUEUE_STORAGE: "prefect.server.worker_communication.cleanup_queue"
        }
    ):
        with pytest.raises(
            ValueError, match="concrete WorkerCleanupQueue implementation"
        ):
            get_worker_cleanup_queue()


async def test_wait_for_wakeup_handles_asyncio_timeout(
    queue: WorkerCleanupQueue,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def raise_timeout(awaitable: Any, timeout: float | None) -> None:
        if hasattr(awaitable, "close"):
            awaitable.close()
        raise asyncio.TimeoutError

    monkeypatch.setattr(memory_module.asyncio, "wait_for", raise_timeout)

    assert await queue.wait_for_wakeup(uuid4(), timeout=1) is None
