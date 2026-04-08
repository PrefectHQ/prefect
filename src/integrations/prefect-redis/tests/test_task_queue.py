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
        delivered = await backend.dequeue("test-key", timeout=5)

        assert delivered.task_run.id == task_run.id
        assert delivered.task_run.task_key == task_run.task_key
        assert delivered.ack_token is not None

    async def test_dequeue_timeout_when_empty(self, backend):
        with pytest.raises(asyncio.TimeoutError):
            await backend.dequeue("empty-key", timeout=1)

    async def test_fifo_order(self, backend):
        runs = [_make_task_run("test-key") for _ in range(3)]
        for run in runs:
            await backend.enqueue(run)

        for expected in runs:
            delivered = await backend.dequeue("test-key", timeout=5)
            assert delivered.task_run.id == expected.id

    async def test_dequeue_blocks_until_available(self, backend):
        task_run = _make_task_run("blocking-key")

        async def delayed_enqueue():
            await asyncio.sleep(0.5)
            await backend.enqueue(task_run)

        asyncio.create_task(delayed_enqueue())
        delivered = await backend.dequeue("blocking-key", timeout=5)
        assert delivered.task_run.id == task_run.id


class TestStaleRecovery:
    async def test_stale_entry_is_recovered(self, backend):
        """An unacked entry past visibility timeout is reclaimed via
        XAUTOCLAIM and returned by _claim_one_stale_entry."""
        task_run = _make_task_run("recover-key")
        await backend.enqueue(task_run)

        delivered = await backend.dequeue("recover-key", timeout=5)
        assert delivered.task_run.id == task_run.id

        backend._visibility_timeout = 0
        await asyncio.sleep(0.1)

        fresh = _make_task_run("recover-key")
        await backend.enqueue(fresh)

        # XAUTOCLAIM claims the stale entry and returns it directly
        d1 = await backend.dequeue("recover-key", timeout=5)
        assert d1.task_run.id == task_run.id, "Stale entry should be recovered"

        await backend.ack(d1)

        d2 = await backend.dequeue("recover-key", timeout=5)
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

        delivered = await backend.dequeue("orphan-key", timeout=5)
        assert delivered.task_run.id == task_run.id


class TestAck:
    async def test_ack_removes_from_pel(self, backend):
        task_run = _make_task_run("ack-key")
        await backend.enqueue(task_run)
        delivered = await backend.dequeue("ack-key", timeout=5)

        stream_key = delivered.ack_token["stream_key"]
        pending = await backend._redis.xpending(stream_key, GROUP_NAME)
        pending_count = pending.get("pending", pending.get(b"pending", 0))
        assert pending_count >= 1

        await backend.ack(delivered)

        pending = await backend._redis.xpending(stream_key, GROUP_NAME)
        pending_count = pending.get("pending", pending.get(b"pending", 0))
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
            await backend.dequeue("retry-key", timeout=1)


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
        delivered = await backend.dequeue("dlq-key", timeout=5)
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
        pending_count = pending.get("pending", pending.get(b"pending", 0))
        assert pending_count == 0, "Entry should be removed from PEL after DLQ"

        dlq_len = await backend._redis.xlen(dlq_key)
        assert dlq_len == 1, "Entry should be in DLQ stream"

    async def test_under_max_retries_redelivered(self, backend):
        """Entries under max_retries are redelivered via claim, not DLQ'd."""
        backend._max_retries = 5
        backend._visibility_timeout = 0

        task_run = _make_task_run("redeliver-key")
        await backend.enqueue(task_run)

        delivered = await backend.dequeue("redeliver-key", timeout=5)
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
            msg_id = p.get("message_id", p.get(b"message_id"))
            await backend._redis.xack(stream_key, GROUP_NAME, msg_id)

        await asyncio.sleep(0.01)

        backend._consumer_idle_threshold_ms = 0
        # Reset throttle so the call isn't skipped
        backend._throttle_last__cleanup_stale_consumers = 0.0

        await backend._cleanup_stale_consumers("cleanup-key")

        consumers = await backend._redis.xinfo_consumers(stream_key, GROUP_NAME)
        consumer_names = [c.get("name", c.get(b"name")) for c in consumers]
        assert b"old-dead-consumer" not in consumer_names

    async def test_active_consumers_not_removed(self, backend):
        """Consumers with pending entries are not removed even if idle."""
        stream_key = backend._stream_key("active-key")
        await backend._ensure_group(stream_key)

        await backend._redis.xadd(stream_key, {"data": "dummy"})
        await backend._redis.xreadgroup(
            GROUP_NAME, "busy-consumer", {stream_key: ">"}, count=1
        )
        # Don't ack — pel_count > 0

        await asyncio.sleep(0.01)
        backend._consumer_idle_threshold_ms = 0
        backend._throttle_last__cleanup_stale_consumers = 0.0

        await backend._cleanup_stale_consumers("active-key")

        consumers = await backend._redis.xinfo_consumers(stream_key, GROUP_NAME)
        consumer_names = [c.get("name", c.get(b"name")) for c in consumers]
        assert b"busy-consumer" in consumer_names


class TestMultiKeyIsolation:
    async def test_keys_are_isolated(self, backend):
        """Tasks enqueued on different keys don't cross-pollinate."""
        run_a = _make_task_run("key-a")
        run_b = _make_task_run("key-b")
        await backend.enqueue(run_a)
        await backend.enqueue(run_b)

        d_a = await backend.dequeue("key-a", timeout=5)
        assert d_a.task_run.id == run_a.id

        d_b = await backend.dequeue("key-b", timeout=5)
        assert d_b.task_run.id == run_b.id

    async def test_dequeue_on_wrong_key_times_out(self, backend):
        """Dequeue on a key with no entries times out, even if other keys have data."""
        await backend.enqueue(_make_task_run("has-data"))

        with pytest.raises(asyncio.TimeoutError):
            await backend.dequeue("no-data", timeout=1)


class TestConcurrentConsumers:
    async def test_no_duplicate_delivery(self, backend):
        """Multiple concurrent consumers on the same key each get unique entries."""
        num_tasks = 20
        runs = [_make_task_run("shared-key") for _ in range(num_tasks)]
        for run in runs:
            await backend.enqueue(run)

        delivered_ids: set[str] = set()
        lock = asyncio.Lock()

        async def consumer():
            while True:
                try:
                    d = await backend.dequeue("shared-key", timeout=2)
                    async with lock:
                        delivered_ids.add(str(d.task_run.id))
                    await backend.ack(d)
                except asyncio.TimeoutError:
                    return

        await asyncio.gather(*[consumer() for _ in range(4)])

        expected_ids = {str(r.id) for r in runs}
        assert delivered_ids == expected_ids, (
            "Every task should be delivered exactly once"
        )

    async def test_concurrent_enqueue_dequeue(self, backend):
        """Enqueue and dequeue happening concurrently don't lose entries."""
        num_tasks = 15
        runs = [_make_task_run("concurrent-key") for _ in range(num_tasks)]
        delivered_ids: set[str] = set()
        lock = asyncio.Lock()

        async def producer():
            for run in runs:
                await backend.enqueue(run)
                await asyncio.sleep(0.01)

        async def consumer():
            while len(delivered_ids) < num_tasks:
                try:
                    d = await backend.dequeue("concurrent-key", timeout=3)
                    async with lock:
                        delivered_ids.add(str(d.task_run.id))
                    await backend.ack(d)
                except asyncio.TimeoutError:
                    continue

        await asyncio.gather(producer(), consumer())

        expected_ids = {str(r.id) for r in runs}
        assert delivered_ids == expected_ids


class TestAckPreventsReclaim:
    async def test_acked_entry_not_reclaimed(self, backend):
        """After ack, XAUTOCLAIM does not return the entry."""
        backend._visibility_timeout = 0
        task_run = _make_task_run("ack-reclaim-key")
        await backend.enqueue(task_run)

        delivered = await backend.dequeue("ack-reclaim-key", timeout=5)
        await backend.ack(delivered)

        await asyncio.sleep(0.1)
        result = await backend._claim_one_stale_entry("ack-reclaim-key")
        assert result is None, "Acked entry should not be reclaimed"


class TestDLQContent:
    async def test_dlq_preserves_task_data(self, backend):
        """DLQ entries contain the original task run data."""
        backend._max_retries = 2
        backend._visibility_timeout = 0

        task_run = _make_task_run("dlq-data-key")
        await backend.enqueue(task_run)

        # Initial dequeue (times_delivered=1)
        await backend.dequeue("dlq-data-key", timeout=5)

        # Claim bumps to times_delivered=2 (at max_retries) → DLQ
        await asyncio.sleep(0.1)
        result = await backend._claim_one_stale_entry("dlq-data-key")
        assert result is None

        dlq_key = backend._dlq_key("dlq-data-key")
        entries = await backend._redis.xrange(dlq_key)
        assert len(entries) == 1

        _, fields = entries[0]
        data_field = fields.get(b"data")
        assert data_field is not None, "DLQ entry should contain original data"
        restored = TaskRun.model_validate_json(data_field)
        assert restored.id == task_run.id


class TestReset:
    async def test_reset_clears_all_streams(self, backend):
        """reset() removes all stream keys and resets singleton state."""
        for i in range(3):
            await backend.enqueue(_make_task_run(f"reset-key-{i}"))

        await backend.reset()

        cursor = 0
        found_keys = []
        while True:
            cursor, keys = await backend._redis.scan(
                cursor, match=f"{KEY_PREFIX}:*", count=100
            )
            found_keys.extend(keys)
            if cursor == 0:
                break

        assert found_keys == [], "All stream keys should be deleted after reset"

    async def test_reset_allows_reuse(self, backend):
        """After reset, enqueue/dequeue works normally."""
        await backend.enqueue(_make_task_run("pre-reset-key"))
        await backend.reset()

        # Re-initialize after reset
        fresh = TaskQueueBackend()
        task_run = _make_task_run("post-reset-key")
        await fresh.enqueue(task_run)
        delivered = await fresh.dequeue("post-reset-key", timeout=5)
        assert delivered.task_run.id == task_run.id


class TestConnectionRecovery:
    async def test_dequeue_retries_on_connection_error(self, backend):
        """dequeue() reconnects and retries after a Redis connection error."""
        task_run = _make_task_run("reconnect-key")
        await backend.enqueue(task_run)

        # Poison the connection pool so the next command fails
        original_redis = backend._redis
        await original_redis.connection_pool.disconnect()

        # dequeue should recover via its retry loop
        delivered = await backend.dequeue("reconnect-key", timeout=10)
        assert delivered.task_run.id == task_run.id

    async def test_enqueue_after_pool_disconnect(self, backend):
        """Enqueue recovers after a connection pool reset."""
        # Disconnect and get a fresh client via dequeue's recovery path
        await backend._redis.connection_pool.disconnect()

        # The pool auto-reconnects on the next command for non-blocking ops
        task_run = _make_task_run("pool-recovery-key")
        await backend.enqueue(task_run)

        delivered = await backend.dequeue("pool-recovery-key", timeout=5)
        assert delivered.task_run.id == task_run.id


class TestEnsureGroupIdempotency:
    async def test_ensure_group_idempotent(self, backend):
        """Calling _ensure_group multiple times does not error."""
        key = backend._stream_key("idempotent-key")
        await backend._ensure_group(key)
        await backend._ensure_group(key)

        # Force bypass the cache to test the BUSYGROUP path
        backend._initialized_groups.discard(key)
        await backend._ensure_group(key)

    async def test_ensure_group_creates_stream(self, backend):
        """_ensure_group with mkstream=True creates the stream key."""
        key = backend._stream_key("mkstream-key")
        exists_before = await backend._redis.exists(key)
        assert exists_before == 0

        await backend._ensure_group(key)
        exists_after = await backend._redis.exists(key)
        assert exists_after == 1


class TestThrottle:
    async def test_cleanup_throttled(self, backend):
        """Cleanup is skipped when called within the throttle interval."""
        stream_key = backend._stream_key("throttle-key")
        await backend._ensure_group(stream_key)

        await backend._redis.xadd(stream_key, {"data": "dummy"})
        await backend._redis.xreadgroup(
            GROUP_NAME, "stale-consumer", {stream_key: ">"}, count=1
        )
        # Ack so pel_count=0 and consumer is eligible for removal
        pending = await backend._redis.xpending_range(
            stream_key,
            GROUP_NAME,
            min="-",
            max="+",
            count=10,
            consumername="stale-consumer",
        )
        for p in pending:
            msg_id = p.get("message_id", p.get(b"message_id"))
            await backend._redis.xack(stream_key, GROUP_NAME, msg_id)

        await asyncio.sleep(0.01)
        backend._consumer_idle_threshold_ms = 0

        # First call should execute (set throttle to recent time)
        backend._throttle_last__cleanup_stale_consumers = 0.0
        backend._consumer_cleanup_interval = 60
        await backend._cleanup_stale_consumers("throttle-key")

        # Second immediate call should be throttled (skipped)
        # Re-add a consumer to check it's NOT cleaned up this time
        await backend._redis.xadd(stream_key, {"data": "dummy2"})
        await backend._redis.xreadgroup(
            GROUP_NAME, "stale-consumer-2", {stream_key: ">"}, count=1
        )
        pending = await backend._redis.xpending_range(
            stream_key,
            GROUP_NAME,
            min="-",
            max="+",
            count=10,
            consumername="stale-consumer-2",
        )
        for p in pending:
            msg_id = p.get("message_id", p.get(b"message_id"))
            await backend._redis.xack(stream_key, GROUP_NAME, msg_id)

        await asyncio.sleep(0.01)
        await backend._cleanup_stale_consumers("throttle-key")

        consumers = await backend._redis.xinfo_consumers(stream_key, GROUP_NAME)
        consumer_names = [c.get("name", c.get(b"name")) for c in consumers]
        # stale-consumer-2 should still exist because cleanup was throttled
        assert b"stale-consumer-2" in consumer_names


class TestCorruptEntry:
    async def test_missing_data_field_raises(self, backend):
        """A stream entry without a 'data' field raises ValueError."""
        key = backend._stream_key("corrupt-key")
        await backend._ensure_group(key)

        await backend._redis.xadd(key, {"not_data": "garbage"})

        with pytest.raises(ValueError, match="missing 'data' field"):
            await backend.dequeue("corrupt-key", timeout=5)
