"""Tests for the Redis Streams TaskQueueBackend."""

import asyncio
from uuid import uuid4

import pytest
from prefect_redis.task_queue import GROUP_NAME, TaskQueueBackend

from prefect.server.schemas.core import TaskRun
from prefect.server.schemas.states import Scheduled
from prefect.server.task_queue import DeliveredTaskRun


def _make_task_run(task_key: str = "test-task") -> TaskRun:
    return TaskRun(
        id=uuid4(),
        flow_run_id=uuid4(),
        task_key=task_key,
        dynamic_key=str(uuid4()),
        state=Scheduled(),
    )


@pytest.fixture(autouse=True)
async def backend():
    b = TaskQueueBackend()
    await b.reset()
    yield b
    await b.reset()


class TestStreamBasics:
    async def test_enqueue_and_dequeue(self, backend):
        task_run = _make_task_run("test-key")
        await backend.enqueue(task_run)
        delivered = await backend.dequeue_from_keys(["test-key"], timeout=5)

        assert delivered.task_run.id == task_run.id
        assert delivered.task_run.task_key == task_run.task_key
        assert delivered.ack_token is not None

    async def test_dequeue_timeout_when_empty(self, backend):
        with pytest.raises(asyncio.TimeoutError):
            await backend.dequeue_from_keys(["empty-key"], timeout=1)

    async def test_fifo_order(self, backend):
        runs = [_make_task_run("test-key") for _ in range(3)]
        for run in runs:
            await backend.enqueue(run)

        for expected in runs:
            delivered = await backend.dequeue_from_keys(["test-key"], timeout=5)
            assert delivered.task_run.id == expected.id

    async def test_dequeue_blocks_until_available(self, backend):
        task_run = _make_task_run("blocking-key")

        async def delayed_enqueue():
            await asyncio.sleep(0.5)
            await backend.enqueue(task_run)

        asyncio.create_task(delayed_enqueue())
        delivered = await backend.dequeue_from_keys(["blocking-key"], timeout=5)
        assert delivered.task_run.id == task_run.id


class TestStaleRecovery:
    async def test_stale_entry_is_recovered(self, backend):
        """An unacked entry past visibility timeout is reclaimed via
        XAUTOCLAIM and returned by _claim_one_stale_entry."""
        task_run = _make_task_run("recover-key")
        await backend.enqueue(task_run)

        delivered = await backend.dequeue_from_keys(["recover-key"], timeout=5)
        assert delivered.task_run.id == task_run.id

        backend._visibility_timeout = 0
        await asyncio.sleep(0.1)

        fresh = _make_task_run("recover-key")
        await backend.enqueue(fresh)

        # XAUTOCLAIM claims the stale entry and returns it directly
        d1 = await backend.dequeue_from_keys(["recover-key"], timeout=5)
        assert d1.task_run.id == task_run.id, "Stale entry should be recovered"

        await backend.ack(d1)

        d2 = await backend.dequeue_from_keys(["recover-key"], timeout=5)
        assert d2.task_run.id == fresh.id, (
            "Fresh entry should be served after stale is acked"
        )

    async def test_orphan_entries_are_skipped(self, backend):
        """XAUTOCLAIM orphan entries (data=None) are acked and skipped."""
        key = backend._stream_key("orphan-key")
        await backend._ensure_group(key)

        msg_id = await backend._redis.xadd(key, {"data": "dummy"})
        await backend._redis.xreadgroup(
            GROUP_NAME, backend._consumer, {key: ">"}, count=1
        )
        await backend._redis.xdel(key, msg_id)

        backend._visibility_timeout = 0
        await asyncio.sleep(0.1)

        task_run = _make_task_run("orphan-key")
        await backend.enqueue(task_run)

        delivered = await backend.dequeue_from_keys(["orphan-key"], timeout=5)
        assert delivered.task_run.id == task_run.id


class TestAck:
    async def test_ack_removes_from_pel(self, backend):
        task_run = _make_task_run("ack-key")
        await backend.enqueue(task_run)
        delivered = await backend.dequeue_from_keys(["ack-key"], timeout=5)

        stream_key = delivered.ack_token["stream_key"]
        pending = await backend._redis.xpending(stream_key, GROUP_NAME)
        pending_count = pending.get("pending") or pending.get(b"pending", 0)
        assert pending_count >= 1

        await backend.ack(delivered)

        pending = await backend._redis.xpending(stream_key, GROUP_NAME)
        pending_count = pending.get("pending") or pending.get(b"pending", 0)
        assert pending_count == 0

        assert await backend._redis.xlen(stream_key) == 0

    async def test_ack_noop_with_none_token(self, backend):
        delivered = DeliveredTaskRun(task_run=_make_task_run(), ack_token=None)
        await backend.ack(delivered)


class TestRetry:
    async def test_retry_is_noop_for_redis(self, backend):
        """retry() is a no-op for Redis — PEL handles redelivery."""
        task_run = _make_task_run("retry-key")
        await backend.retry(task_run)

        # retry() doesn't enqueue, so dequeue should timeout
        with pytest.raises(asyncio.TimeoutError):
            await backend.dequeue_from_keys(["retry-key"], timeout=1)


class TestDLQ:
    async def test_entry_moved_to_dlq_after_max_retries(self, backend):
        """After max_retries delivery attempts, entry is moved to DLQ.

        With max_retries=3: initial xreadgroup (td=1), first XAUTOCLAIM (td=2)
        returns the entry, second XAUTOCLAIM (td=3) hits the limit and moves
        to DLQ.
        """
        backend._max_retries = 3
        backend._visibility_timeout = 0

        task_run = _make_task_run("dlq-key")
        await backend.enqueue(task_run)

        stream_key = backend._stream_key("dlq-key")
        dlq_key = backend._dlq_key("dlq-key")

        # Initial dequeue via xreadgroup (times_delivered=1)
        delivered = await backend.dequeue_from_keys(["dlq-key"], timeout=5)
        assert delivered.task_run.id == task_run.id

        # First claim bumps to times_delivered=2 (under max_retries=3)
        await asyncio.sleep(0.1)
        recovered = await backend._claim_one_stale_entry("dlq-key")
        assert recovered is not None, "Should redeliver under max_retries"
        assert recovered.task_run.id == task_run.id

        # Second claim bumps to times_delivered=3 (at max_retries) → DLQ
        await asyncio.sleep(0.1)
        result = await backend._claim_one_stale_entry("dlq-key")
        assert result is None, "Should return None after DLQ move"

        pending = await backend._redis.xpending(stream_key, GROUP_NAME)
        pending_count = pending.get("pending") or pending.get(b"pending", 0)
        assert pending_count == 0, "Entry should be removed from PEL after DLQ"

        dlq_len = await backend._redis.xlen(dlq_key)
        assert dlq_len == 1, "Entry should be in DLQ stream"

    async def test_under_max_retries_redelivered(self, backend):
        """Entries under max_retries are redelivered via claim, not DLQ'd."""
        backend._max_retries = 5
        backend._visibility_timeout = 0

        task_run = _make_task_run("redeliver-key")
        await backend.enqueue(task_run)

        delivered = await backend.dequeue_from_keys(["redeliver-key"], timeout=5)
        assert delivered.task_run.id == task_run.id

        await asyncio.sleep(0.1)

        recovered = await backend._claim_one_stale_entry("redeliver-key")
        assert recovered is not None
        assert recovered.task_run.id == task_run.id

        dlq_key = backend._dlq_key("redeliver-key")
        dlq_len = await backend._redis.xlen(dlq_key)
        assert dlq_len == 0


class TestConsumerCleanup:
    async def test_idle_consumers_are_removed(self, backend):
        stream_key = backend._stream_key("cleanup-key")
        await backend._ensure_group(stream_key)

        await backend._redis.xadd(stream_key, {"data": "dummy"})
        await backend._redis.xreadgroup(
            GROUP_NAME, "old-dead-consumer", {stream_key: ">"}, count=1
        )
        pending = await backend._redis.xpending_range(
            stream_key,
            GROUP_NAME,
            min="-",
            max="+",
            count=10,
            consumername="old-dead-consumer",
        )
        for p in pending:
            msg_id = p.get("message_id") or p.get(b"message_id")
            await backend._redis.xack(stream_key, GROUP_NAME, msg_id)

        backend._consumer_idle_threshold_ms = 0

        await backend._cleanup_stale_consumers(["cleanup-key"])

        consumers = await backend._redis.xinfo_consumers(stream_key, GROUP_NAME)
        consumer_names = [c.get("name") or c.get(b"name") for c in consumers]
        assert b"old-dead-consumer" not in consumer_names
