"""Tests for the Redis-backed TaskQueueBackend."""

import asyncio
from uuid import uuid4

import pytest

from prefect.server.schemas.core import TaskRun
from prefect.server.schemas.states import Scheduled
from prefect.server.task_queue import get_task_queue_backend


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
    """Create a fresh TaskQueueBackend and reset between tests."""
    b = get_task_queue_backend()
    await b.reset()
    yield b
    await b.reset()


class TestTaskQueueBackend:
    async def test_enqueue_and_get(self, backend):
        task_run = _make_task_run("test-key")
        await backend.enqueue(task_run)
        result = await backend.get("test-key")

        assert result.id == task_run.id
        assert result.task_key == task_run.task_key

    async def test_retry_takes_priority(self, backend):
        scheduled = _make_task_run("test-key")
        retried = _make_task_run("test-key")

        await backend.enqueue(scheduled)
        await backend.retry(retried)

        # Retry should come out first
        result = await backend.get("test-key")
        assert result.id == retried.id

        # Then scheduled
        result = await backend.get("test-key")
        assert result.id == scheduled.id

    async def test_fifo_order(self, backend):
        runs = [_make_task_run("test-key") for _ in range(3)]

        for run in runs:
            await backend.enqueue(run)

        for expected in runs:
            result = await backend.get("test-key")
            assert result.id == expected.id

    async def test_get_blocks_until_available(self, backend):
        task_run = _make_task_run("blocking-key")

        async def delayed_enqueue():
            await asyncio.sleep(0.5)
            await backend.enqueue(task_run)

        asyncio.create_task(delayed_enqueue())
        result = await asyncio.wait_for(backend.get("blocking-key"), timeout=5)
        assert result.id == task_run.id

    async def test_backpressure_on_enqueue(self, backend):
        """Queue with max size 2 should block on the 3rd enqueue until consumed."""
        backend.configure(scheduled_size=2, retry_size=2)

        await backend.enqueue(_make_task_run("bp-key"))
        await backend.enqueue(_make_task_run("bp-key"))

        # Third enqueue should block; verify it doesn't complete immediately
        third = _make_task_run("bp-key")
        put_task = asyncio.create_task(backend.enqueue(third))
        await asyncio.sleep(0.3)
        assert not put_task.done()

        # Consume one to unblock
        await backend.get("bp-key")
        await asyncio.wait_for(put_task, timeout=5)

    async def test_scheduled_size_limit(self, backend):
        """enqueue() blocks at scheduled_size limit; Redis list length matches."""
        backend.configure(scheduled_size=2, retry_size=1)

        await backend.enqueue(_make_task_run("limit-key"))
        await backend.enqueue(_make_task_run("limit-key"))

        # 3rd enqueue should block (queue is full)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                backend.enqueue(_make_task_run("limit-key")), timeout=0.5
            )

        # Assert Redis list length matches the configured limit
        redis = backend._redis
        assert await redis.llen(backend._scheduled_key("limit-key")) == 2

    async def test_retry_size_limit(self, backend):
        """retry() blocks at retry_size limit; Redis list length matches."""
        backend.configure(scheduled_size=2, retry_size=1)

        await backend.retry(_make_task_run("retry-limit-key"))

        # 2nd retry should block (queue is full)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                backend.retry(_make_task_run("retry-limit-key")), timeout=0.5
            )

        redis = backend._redis
        assert await redis.llen(backend._retry_key("retry-limit-key")) == 1

    async def test_configure(self, backend):
        """configure() sets custom sizes."""
        backend.configure(scheduled_size=42, retry_size=7)
        assert backend._max_scheduled == 42
        assert backend._max_retry == 7

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
        result = await backend.get("serde-key")

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
            result = await asyncio.wait_for(backend.get("conc-prod"), timeout=5)
            received_ids.add(result.id)
        assert received_ids == {r.id for r in runs}

    async def test_concurrent_enqueue_respects_limit(self, backend):
        """Concurrent enqueues never exceed the configured max size."""
        backend.configure(scheduled_size=5, retry_size=5)
        redis = backend._redis

        runs = [_make_task_run("atomic-bp") for _ in range(10)]

        # Launch 10 concurrent producers against a limit of 5
        tasks = [asyncio.create_task(backend.enqueue(r)) for r in runs]

        # Give producers time to fill and block
        await asyncio.sleep(0.5)

        # The list should never exceed the limit
        length = await redis.llen(backend._scheduled_key("atomic-bp"))
        assert length <= 5, f"List length {length} exceeded limit 5"

        # Consume items to unblock remaining producers
        for _ in range(10):
            await asyncio.wait_for(backend.get("atomic-bp"), timeout=5)

        # All tasks should complete (no lost writes)
        await asyncio.wait_for(asyncio.gather(*tasks), timeout=10)

        # Queue should be fully drained
        assert await redis.llen(backend._scheduled_key("atomic-bp")) == 0

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
                    result = await asyncio.wait_for(backend.get("conc-cons"), timeout=2)
                    async with lock:
                        received.append(str(result.id))
                except asyncio.TimeoutError:
                    return

        await asyncio.gather(*(consumer() for _ in range(5)))

        assert len(received) == 20, f"Expected 20, got {len(received)}"
        assert len(set(received)) == 20, "Duplicate deliveries detected"


class TestGetMany:
    async def test_get_many_from_multiple_keys(self, backend):
        run_a = _make_task_run("key-a")
        run_b = _make_task_run("key-b")

        await backend.enqueue(run_a)
        await backend.enqueue(run_b)

        results = set()
        results.add(
            (await backend.get_many(["key-a", "key-b"], timeout=2, offset=0)).id
        )
        results.add(
            (await backend.get_many(["key-a", "key-b"], timeout=2, offset=1)).id
        )

        assert results == {run_a.id, run_b.id}

    async def test_get_many_timeout_when_empty(self, backend):
        with pytest.raises(asyncio.TimeoutError):
            await backend.get_many(["empty-key"], timeout=1, offset=0)

    async def test_get_many_retry_priority_within_key(self, backend):
        """Retry items for a key are served before scheduled items for that same key."""
        scheduled = _make_task_run("key-a")
        retried = _make_task_run("key-a")

        await backend.enqueue(scheduled)
        await backend.retry(retried)

        # Retry should come first (same key, retry has priority)
        result = await backend.get_many(["key-a"], timeout=2, offset=0)
        assert result.id == retried.id

    async def test_get_many_only_returns_subscribed_keys(self, backend):
        """get_many should never return items from unsubscribed keys."""
        run_a = _make_task_run("mq-a")
        run_b = _make_task_run("mq-b")
        run_c = _make_task_run("mq-c")

        await backend.enqueue(run_a)
        await backend.enqueue(run_b)
        await backend.enqueue(run_c)

        results = set()
        results.add((await backend.get_many(["mq-a", "mq-b"], timeout=2, offset=0)).id)
        results.add((await backend.get_many(["mq-a", "mq-b"], timeout=2, offset=1)).id)

        # Should timeout — nothing left in subscribed keys
        with pytest.raises(asyncio.TimeoutError):
            await backend.get_many(["mq-a", "mq-b"], timeout=1, offset=2)

        assert results == {run_a.id, run_b.id}
        # "mq-c" item should still be in Redis, untouched
        redis = backend._redis
        assert await redis.llen(backend._scheduled_key("mq-c")) == 1


class TestGetManyFairness:
    async def test_round_robin_prevents_starvation(self, backend):
        """With round-robin, a busy key_a does not starve key_b."""
        # Fill key_a with 5 items, key_b with 1 item
        for _ in range(5):
            await backend.enqueue(_make_task_run("starve_a"))
        await backend.enqueue(_make_task_run("starve_b"))

        results = []
        for i in range(6):
            try:
                task_run = await backend.get_many(
                    ["starve_a", "starve_b"], timeout=1, offset=i
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

        first = await backend.get_many(["interleave_key"], timeout=2, offset=0)
        assert first.id == retry_run.id, "Retry item should be served before scheduled"
