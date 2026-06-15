from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import pytest

from prefect.server.worker_communication.cleanup_queue import get_worker_cleanup_queue
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
