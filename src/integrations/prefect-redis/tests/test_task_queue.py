"""Tests for the Redis-backed TaskQueueBackend."""

import asyncio
import json
from uuid import uuid4

import pytest
from prefect_redis.task_queue import INFLIGHT_KEY, RESTORE_LOCK_KEY, TaskQueueBackend

from prefect.server.schemas.core import TaskRun
from prefect.server.schemas.states import Scheduled


def _make_task_run(task_key: str = "test-task") -> TaskRun:
    """Create a minimal TaskRun for testing."""
    return TaskRun(
        id=uuid4(),
        flow_run_id=uuid4(),
        task_key=task_key,
        dynamic_key=str(uuid4()),
        state=Scheduled(),
    )


@pytest.fixture(autouse=True)
async def backend():
    """Create a fresh Redis TaskQueueBackend and reset between tests."""
    b = TaskQueueBackend()
    await b.reset()
    yield b
    await b.reset()


class TestTaskQueueBackend:
    async def test_enqueue_and_dequeue(self, backend):
        task_run = _make_task_run("test-key")
        await backend.enqueue(task_run)
        result = await backend.dequeue_from_keys(["test-key"], timeout=5)

        assert result.id == task_run.id
        assert result.task_key == task_run.task_key

    async def test_retry_takes_priority(self, backend):
        scheduled = _make_task_run("test-key")
        retried = _make_task_run("test-key")

        await backend.enqueue(scheduled)
        await backend.retry(retried)

        # Retry should come out first
        result = await backend.dequeue_from_keys(["test-key"], timeout=5)
        assert result.id == retried.id

        # Then scheduled
        result = await backend.dequeue_from_keys(["test-key"], timeout=5)
        assert result.id == scheduled.id

    async def test_fifo_order(self, backend):
        runs = [_make_task_run("test-key") for _ in range(3)]

        for run in runs:
            await backend.enqueue(run)

        for expected in runs:
            result = await backend.dequeue_from_keys(["test-key"], timeout=5)
            assert result.id == expected.id

    async def test_dequeue_blocks_until_available(self, backend):
        task_run = _make_task_run("blocking-key")

        async def delayed_enqueue():
            await asyncio.sleep(0.5)
            await backend.enqueue(task_run)

        asyncio.create_task(delayed_enqueue())
        result = await backend.dequeue_from_keys(["blocking-key"], timeout=5)
        assert result.id == task_run.id

    async def test_retry_fifo_order(self, backend):
        """Multiple retry items come out in FIFO order."""
        runs = [_make_task_run("test-key") for _ in range(3)]

        for run in runs:
            await backend.retry(run)

        for expected in runs:
            result = await backend.dequeue_from_keys(["test-key"], timeout=5)
            assert result.id == expected.id

    async def test_serialization_round_trip(self, backend):
        """All TaskRun fields survive the JSON round-trip through Redis."""
        from prefect.server.schemas.states import StateDetails

        original = TaskRun(
            id=uuid4(),
            flow_run_id=uuid4(),
            task_key="serde-key",
            dynamic_key="dk-123",
            state=Scheduled(
                name="AwaitingRetry",
                message="Retrying after transient error",
                state_details=StateDetails(
                    flow_run_id=uuid4(),
                    task_run_id=uuid4(),
                ),
            ),
        )
        await backend.enqueue(original)
        result = await backend.dequeue_from_keys(["serde-key"], timeout=5)

        assert result.id == original.id
        assert result.flow_run_id == original.flow_run_id
        assert result.task_key == original.task_key
        assert result.dynamic_key == original.dynamic_key
        assert result.state.type == original.state.type
        assert result.state.name == original.state.name
        assert result.state.message == original.state.message


class TestConcurrency:
    async def test_concurrent_producers_no_lost_writes(self, backend):
        """N concurrent enqueue() calls should not lose any writes."""
        runs = [_make_task_run("conc-prod") for _ in range(10)]

        await asyncio.gather(*(backend.enqueue(r) for r in runs))

        redis = backend._redis
        assert await redis.llen(backend._scheduled_key("conc-prod")) == 10

        # Drain and verify all IDs present
        received_ids = set()
        for _ in range(10):
            result = await backend.dequeue_from_keys(["conc-prod"], timeout=5)
            received_ids.add(result.id)
        assert received_ids == {r.id for r in runs}

    async def test_concurrent_consumers_exclusive_delivery(self, backend):
        """Multiple consumers on the same queue get each item exactly once."""
        runs = [_make_task_run("conc-cons") for _ in range(20)]
        for r in runs:
            await backend.enqueue(r)

        received: list[str] = []
        lock = asyncio.Lock()

        async def consumer():
            while True:
                try:
                    result = await backend.dequeue_from_keys(["conc-cons"], timeout=2)
                    async with lock:
                        received.append(str(result.id))
                except asyncio.TimeoutError:
                    return

        await asyncio.gather(*(consumer() for _ in range(5)))

        assert len(received) == 20, f"Expected 20, got {len(received)}"
        assert len(set(received)) == 20, "Duplicate deliveries detected"


class TestDequeueFromKeys:
    async def test_dequeue_from_multiple_keys(self, backend):
        run_a = _make_task_run("key-a")
        run_b = _make_task_run("key-b")

        await backend.enqueue(run_a)
        await backend.enqueue(run_b)

        results = set()
        results.add((await backend.dequeue_from_keys(["key-a", "key-b"], timeout=2)).id)
        results.add((await backend.dequeue_from_keys(["key-a", "key-b"], timeout=2)).id)

        assert results == {run_a.id, run_b.id}

    async def test_dequeue_timeout_when_empty(self, backend):
        with pytest.raises(asyncio.TimeoutError):
            await backend.dequeue_from_keys(["empty-key"], timeout=1)

    async def test_dequeue_retry_priority_within_key(self, backend):
        """Retry items for a key are served before scheduled items for that same key."""
        scheduled = _make_task_run("key-a")
        retried = _make_task_run("key-a")

        await backend.enqueue(scheduled)
        await backend.retry(retried)

        # Retry should come first (same key, retry has priority)
        result = await backend.dequeue_from_keys(["key-a"], timeout=2)
        assert result.id == retried.id

    async def test_dequeue_cross_key_retry_vs_scheduled(self, backend):
        """BRPOP key ordering means key-a's scheduled item is checked before key-b's retry."""
        scheduled_a = _make_task_run("xkey-a")
        retry_b = _make_task_run("xkey-b")

        await backend.enqueue(scheduled_a)
        await backend.retry(retry_b)

        # First call: xkey-a is checked first
        # BRPOP list: [retry_a(empty), scheduled_a, retry_b, scheduled_b(empty)]
        # → scheduled_a wins because it's checked before retry_b
        first = await backend.dequeue_from_keys(["xkey-a", "xkey-b"], timeout=2)
        assert first.id == scheduled_a.id

        second = await backend.dequeue_from_keys(["xkey-a", "xkey-b"], timeout=2)
        assert second.id == retry_b.id

    async def test_dequeue_only_returns_subscribed_keys(self, backend):
        """dequeue_from_keys should never return items from unsubscribed keys."""
        run_a = _make_task_run("mq-a")
        run_b = _make_task_run("mq-b")
        run_c = _make_task_run("mq-c")

        await backend.enqueue(run_a)
        await backend.enqueue(run_b)
        await backend.enqueue(run_c)

        results = set()
        results.add((await backend.dequeue_from_keys(["mq-a", "mq-b"], timeout=2)).id)
        results.add((await backend.dequeue_from_keys(["mq-a", "mq-b"], timeout=2)).id)

        # Should timeout — nothing left in subscribed keys
        with pytest.raises(asyncio.TimeoutError):
            await backend.dequeue_from_keys(["mq-a", "mq-b"], timeout=1)

        assert results == {run_a.id, run_b.id}
        # "mq-c" item should still be in Redis, untouched
        redis = backend._redis
        assert await redis.llen(backend._scheduled_key("mq-c")) == 1


class TestDequeueFromKeysFairness:
    async def test_round_robin_prevents_starvation(self, backend):
        """With round-robin, a busy key_a does not starve key_b."""
        # Fill key_a with 5 items, key_b with 1 item
        for _ in range(5):
            await backend.enqueue(_make_task_run("starve_a"))
        await backend.enqueue(_make_task_run("starve_b"))

        results = []
        for _ in range(6):
            try:
                task_run = await backend.dequeue_from_keys(
                    ["starve_a", "starve_b"], timeout=1
                )
                results.append(task_run.task_key)
            except asyncio.TimeoutError:
                break

        # key_b should appear before all key_a items are drained
        assert "starve_b" in results[:4], (
            f"key_b should be served before all key_a items drain, got: {results}"
        )

    async def test_interleaved_retry_priority(self, backend):
        """Retry items for a key are served before scheduled items for that key."""
        scheduled_run = _make_task_run("interleave_key")
        retry_run = _make_task_run("interleave_key")

        await backend.enqueue(scheduled_run)
        await backend.retry(retry_run)

        first = await backend.dequeue_from_keys(["interleave_key"], timeout=2)
        assert first.id == retry_run.id, "Retry item should be served before scheduled"


class TestInflightTracking:
    async def test_inflight_tracked_after_dequeue(self, backend):
        """Dequeued task run appears in the inflight hash."""
        task_run = _make_task_run("inflight-key")
        await backend.enqueue(task_run)

        result = await backend.dequeue_from_keys(["inflight-key"], timeout=5)

        raw = await backend._redis.hget(INFLIGHT_KEY, str(result.id))
        assert raw is not None
        entry = json.loads(raw)
        assert entry["data"] == result.model_dump_json()
        assert "ts" in entry

    async def test_ack_removes_from_inflight(self, backend):
        """ack() removes the task run from the inflight hash."""
        task_run = _make_task_run("ack-key")
        await backend.enqueue(task_run)

        result = await backend.dequeue_from_keys(["ack-key"], timeout=5)
        assert await backend._redis.hget(INFLIGHT_KEY, str(result.id)) is not None

        await backend.ack(result)
        assert await backend._redis.hget(INFLIGHT_KEY, str(result.id)) is None

    async def test_stale_inflight_restored_on_dequeue(self, backend):
        """Stale inflight entries are re-enqueued via retry on next dequeue."""
        stale_run = _make_task_run("stale-key")

        # Plant a stale inflight entry (timestamp in the past)
        import time

        stale_entry = json.dumps(
            {
                "data": stale_run.model_dump_json(),
                "ts": time.time() - backend._visibility_timeout - 1,
            }
        )
        await backend._redis.hset(INFLIGHT_KEY, str(stale_run.id), stale_entry)

        # Enqueue a fresh task so dequeue_from_keys doesn't block forever
        fresh_run = _make_task_run("stale-key")
        await backend.enqueue(fresh_run)

        # The restore sweep runs before BRPOP, moving the stale task to retry.
        # BRPOP then picks up the restored task (retry has priority).
        result = await backend.dequeue_from_keys(["stale-key"], timeout=5)
        assert result.id == stale_run.id, (
            "Restored stale task should be dequeued first (retry priority)"
        )

        # The fresh task should still be in the scheduled queue
        sched_len = await backend._redis.llen(backend._scheduled_key("stale-key"))
        assert sched_len == 1

    async def test_restore_skipped_when_locked(self, backend):
        """If another replica holds the restore lock, sweep is skipped."""
        task_run = _make_task_run("locked-key")

        # Plant a stale inflight entry
        import time

        stale_entry = json.dumps(
            {
                "data": task_run.model_dump_json(),
                "ts": time.time() - backend._visibility_timeout - 1,
            }
        )
        await backend._redis.hset(INFLIGHT_KEY, str(task_run.id), stale_entry)

        # Acquire the restore lock externally (simulating another replica)
        lock = backend._redis.lock(RESTORE_LOCK_KEY, timeout=30)
        await lock.acquire()

        try:
            # Enqueue a fresh task so dequeue doesn't block
            fresh_run = _make_task_run("locked-key")
            await backend.enqueue(fresh_run)

            await backend.dequeue_from_keys(["locked-key"], timeout=5)

            # Stale entry should still be in inflight (sweep was skipped)
            assert await backend._redis.hget(INFLIGHT_KEY, str(task_run.id)) is not None

            # Retry queue should be empty (stale task was NOT restored)
            retry_len = await backend._redis.llen(backend._retry_key("locked-key"))
            assert retry_len == 0
        finally:
            await lock.release()
