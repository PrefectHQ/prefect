"""Tests for the Redis Streams TaskQueueBackend."""

import asyncio
from uuid import uuid4

import pytest
from prefect_redis.task_queue import GROUP_NAME, KEY_PREFIX, TaskQueueBackend

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

    async def test_retry_takes_priority(self, backend):
        scheduled = _make_task_run("test-key")
        retried = _make_task_run("test-key")

        await backend.enqueue(scheduled)
        await backend.retry(retried)

        first = await backend.dequeue_from_keys(["test-key"], timeout=5)
        assert first.task_run.id == retried.id

        second = await backend.dequeue_from_keys(["test-key"], timeout=5)
        assert second.task_run.id == scheduled.id

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
        """An unacked entry past visibility timeout is re-added to the stream."""
        task_run = _make_task_run("recover-key")
        await backend.enqueue(task_run)

        delivered = await backend.dequeue_from_keys(["recover-key"], timeout=5)
        assert delivered.task_run.id == task_run.id

        backend._visibility_timeout = 0
        backend._recovery_interval = 0
        await asyncio.sleep(0.1)

        fresh = _make_task_run("recover-key")
        await backend.enqueue(fresh)

        # Recovery puts the stale entry in buffer; dequeue returns it
        d1 = await backend.dequeue_from_keys(["recover-key"], timeout=5)
        assert d1.task_run.id == task_run.id, "Stale entry should be recovered"

        # Ack it so recovery doesn't reclaim it again
        await backend.ack(d1)

        # Fresh entry should now be available via Lua or blocking read
        d2 = await backend.dequeue_from_keys(["recover-key"], timeout=5)
        assert d2.task_run.id == fresh.id, (
            "Fresh entry should be served after stale is acked"
        )

    async def test_orphan_entries_are_skipped(self, backend):
        """XAUTOCLAIM orphan entries (data=None) are acked and skipped."""
        key = backend._scheduled_key("orphan-key")
        await backend._ensure_group(key)

        msg_id = await backend._redis.xadd(key, {"data": "dummy"})
        await backend._redis.xreadgroup(
            GROUP_NAME, backend._consumer, {key: ">"}, count=1
        )
        await backend._redis.xdel(key, msg_id)

        backend._visibility_timeout = 0
        backend._recovery_interval = 0
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

        # Entry should also be deleted from stream
        assert await backend._redis.xlen(stream_key) == 0

    async def test_ack_noop_with_none_token(self, backend):
        delivered = DeliveredTaskRun(task_run=_make_task_run(), ack_token=None)
        await backend.ack(delivered)


class TestConsumerCleanup:
    async def test_idle_consumers_are_removed(self, backend):
        stream_key = backend._scheduled_key("cleanup-key")
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
        assert "old-dead-consumer" not in consumer_names


class TestFairness:
    async def test_round_robin_prevents_starvation(self, backend):
        for _ in range(5):
            await backend.enqueue(_make_task_run("starve_a"))
        await backend.enqueue(_make_task_run("starve_b"))

        results = []
        for _ in range(6):
            try:
                delivered = await backend.dequeue_from_keys(
                    ["starve_a", "starve_b"], timeout=1
                )
                results.append(delivered.task_run.task_key)
            except asyncio.TimeoutError:
                break

        assert "starve_b" in results[:4], (
            f"key_b should be served before all key_a items drain, got: {results}"
        )

    async def test_retry_priority_within_key(self, backend):
        scheduled = _make_task_run("priority-key")
        retried = _make_task_run("priority-key")

        await backend.enqueue(scheduled)
        await backend.retry(retried)

        first = await backend.dequeue_from_keys(["priority-key"], timeout=2)
        assert first.task_run.id == retried.id


class TestBuffer:
    async def test_buffer_drains_before_redis(self, backend):
        """Multiple items from blocking read are buffered and drained in order."""
        # Enqueue on two different keys
        run_a = _make_task_run("buf-a")
        run_b = _make_task_run("buf-b")
        await backend.enqueue(run_a)
        await backend.enqueue(run_b)

        # First dequeue: Lua finds one, or blocking read returns both
        d1 = await backend.dequeue_from_keys(["buf-a", "buf-b"], timeout=5)

        # Second dequeue: should come from buffer (no Redis call needed for the item)
        d2 = await backend.dequeue_from_keys(["buf-a", "buf-b"], timeout=5)

        received = {d1.task_run.id, d2.task_run.id}
        assert received == {run_a.id, run_b.id}

    async def test_expired_buffer_items_are_dropped(self, backend):
        """Buffer items older than buffer_ttl are dropped."""
        run = _make_task_run("expire-key")
        await backend.enqueue(run)

        delivered = await backend.dequeue_from_keys(["expire-key"], timeout=5)
        await backend.ack(delivered)

        # Manually insert an expired item into the buffer
        fake = DeliveredTaskRun(
            task_run=_make_task_run("expire-key"),
            ack_token={
                "stream_key": f"{KEY_PREFIX}:expire-key:scheduled",
                "msg_id": "0-0",
            },
        )
        stream_key = fake.ack_token["stream_key"]
        from collections import deque as deque_type

        if stream_key not in backend._key_buffers:
            backend._key_buffers[stream_key] = deque_type()
        backend._key_buffers[stream_key].append(
            (0.0, fake)
        )  # timestamp 0 = long expired

        # Enqueue a real task
        real = _make_task_run("expire-key")
        await backend.enqueue(real)

        # Should skip expired buffer item and get the real one
        result = await backend.dequeue_from_keys(["expire-key"], timeout=5)
        assert result.task_run.id == real.id
