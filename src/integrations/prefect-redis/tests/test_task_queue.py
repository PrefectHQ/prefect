"""Tests for the Redis-backed TaskQueue and MultiQueue."""

import asyncio
from uuid import uuid4

import pytest

from prefect.server.schemas.core import TaskRun
from prefect.server.schemas.states import Scheduled
from prefect_redis.task_queue import MultiQueue, TaskQueue


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
def reset_queues():
    """Reset the TaskQueue singleton cache between tests."""
    TaskQueue.reset()
    yield
    TaskQueue.reset()


class TestTaskQueue:
    async def test_put_and_get(self):
        queue = TaskQueue.for_key("test-key")
        task_run = _make_task_run("test-key")

        await queue.put(task_run)
        result = await queue.get()

        assert result.id == task_run.id
        assert result.task_key == task_run.task_key

    async def test_retry_takes_priority(self):
        queue = TaskQueue.for_key("test-key")
        scheduled = _make_task_run("test-key")
        retried = _make_task_run("test-key")

        await queue.put(scheduled)
        await queue.retry(retried)

        # Retry should come out first
        result = await queue.get()
        assert result.id == retried.id

        # Then scheduled
        result = await queue.get()
        assert result.id == scheduled.id

    async def test_fifo_order(self):
        queue = TaskQueue.for_key("test-key")
        runs = [_make_task_run("test-key") for _ in range(3)]

        for run in runs:
            await queue.put(run)

        for expected in runs:
            result = await queue.get()
            assert result.id == expected.id

    async def test_for_key_returns_singleton(self):
        q1 = TaskQueue.for_key("same-key")
        q2 = TaskQueue.for_key("same-key")
        assert q1 is q2

    async def test_for_key_different_keys(self):
        q1 = TaskQueue.for_key("key-a")
        q2 = TaskQueue.for_key("key-b")
        assert q1 is not q2

    async def test_enqueue_class_method(self):
        task_run = _make_task_run("enqueue-key")
        await TaskQueue.enqueue(task_run)

        queue = TaskQueue.for_key("enqueue-key")
        result = await queue.get()
        assert result.id == task_run.id

    async def test_get_blocks_until_available(self):
        queue = TaskQueue.for_key("blocking-key")
        task_run = _make_task_run("blocking-key")

        async def delayed_put():
            await asyncio.sleep(0.5)
            await queue.put(task_run)

        asyncio.create_task(delayed_put())
        result = await asyncio.wait_for(queue.get(), timeout=5)
        assert result.id == task_run.id

    async def test_get_nowait_raises(self):
        queue = TaskQueue.for_key("nowait-key")
        with pytest.raises(asyncio.QueueEmpty):
            queue.get_nowait()

    async def test_backpressure_on_put(self):
        """Queue with max size 2 should block on the 3rd put until consumed."""
        TaskQueue.configure_task_key("bp-key", scheduled_size=2, retry_size=2)
        queue = TaskQueue.for_key("bp-key")

        await queue.put(_make_task_run("bp-key"))
        await queue.put(_make_task_run("bp-key"))

        # Third put should block; verify it doesn't complete immediately
        third = _make_task_run("bp-key")
        put_task = asyncio.create_task(queue.put(third))
        await asyncio.sleep(0.3)
        assert not put_task.done()

        # Consume one to unblock
        await queue.get()
        await asyncio.wait_for(put_task, timeout=5)

    async def test_scheduled_size_limit(self):
        """put() blocks at scheduled_size limit; Redis list length matches."""
        TaskQueue.configure_task_key("limit-key", scheduled_size=2, retry_size=1)
        queue = TaskQueue.for_key("limit-key")

        await queue.put(_make_task_run("limit-key"))
        await queue.put(_make_task_run("limit-key"))

        # 3rd put should block (queue is full)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                queue.put(_make_task_run("limit-key")), timeout=0.5
            )

        # Assert Redis list length matches the configured limit
        redis = queue._redis()
        assert await redis.llen(queue._scheduled_key) == 2

    async def test_retry_size_limit(self):
        """retry() blocks at retry_size limit; Redis list length matches."""
        TaskQueue.configure_task_key(
            "retry-limit-key", scheduled_size=2, retry_size=1
        )
        queue = TaskQueue.for_key("retry-limit-key")

        await queue.retry(_make_task_run("retry-limit-key"))

        # 2nd retry should block (queue is full)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                queue.retry(_make_task_run("retry-limit-key")), timeout=0.5
            )

        redis = queue._redis()
        assert await redis.llen(queue._retry_key) == 1

    async def test_configure_task_key(self):
        """configure_task_key sets custom sizes on subsequently created queues."""
        TaskQueue.configure_task_key("cfg-key", scheduled_size=42, retry_size=7)
        queue = TaskQueue.for_key("cfg-key")
        assert queue._max_scheduled == 42
        assert queue._max_retry == 7

    async def test_reset_clears_singletons(self):
        """reset() clears the singleton cache; for_key returns new instances."""
        q1 = TaskQueue.for_key("rst-a")
        q2 = TaskQueue.for_key("rst-b")
        assert TaskQueue._task_queues  # not empty

        TaskQueue.reset()

        assert TaskQueue._task_queues == {}
        # New instances after reset
        q1_new = TaskQueue.for_key("rst-a")
        assert q1_new is not q1

    async def test_serialization_round_trip(self):
        """All TaskRun fields survive the JSON round-trip through Redis."""
        from prefect.server.schemas.states import StateDetails, StateType

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
        queue = TaskQueue.for_key("serde-key")
        await queue.put(original)
        result = await queue.get()

        assert result.id == original.id
        assert result.flow_run_id == original.flow_run_id
        assert result.task_key == original.task_key
        assert result.dynamic_key == original.dynamic_key
        assert result.state.type == original.state.type
        assert result.state.name == original.state.name
        assert result.state.message == original.state.message


class TestConcurrency:
    async def test_concurrent_producers_no_lost_writes(self):
        """N concurrent put() calls should not lose any writes."""
        queue = TaskQueue.for_key("conc-prod")
        runs = [_make_task_run("conc-prod") for _ in range(10)]

        await asyncio.gather(*(queue.put(r) for r in runs))

        redis = queue._redis()
        assert await redis.llen(queue._scheduled_key) == 10

        # Drain and verify all IDs present
        received_ids = set()
        for _ in range(10):
            result = await asyncio.wait_for(queue.get(), timeout=5)
            received_ids.add(result.id)
        assert received_ids == {r.id for r in runs}

    async def test_concurrent_put_respects_limit(self):
        """Concurrent puts never exceed the configured max size."""
        TaskQueue.configure_task_key("atomic-bp", scheduled_size=5, retry_size=5)
        queue = TaskQueue.for_key("atomic-bp")
        redis = queue._redis()

        runs = [_make_task_run("atomic-bp") for _ in range(10)]

        # Launch 10 concurrent producers against a limit of 5
        tasks = [asyncio.create_task(queue.put(r)) for r in runs]

        # Give producers time to fill and block
        await asyncio.sleep(0.5)

        # The list should never exceed the limit
        length = await redis.llen(queue._scheduled_key)
        assert length <= 5, f"List length {length} exceeded limit 5"

        # Consume items to unblock remaining producers
        for _ in range(10):
            await asyncio.wait_for(queue.get(), timeout=5)

        # All tasks should complete (no lost writes)
        await asyncio.wait_for(asyncio.gather(*tasks), timeout=10)

        # Queue should be fully drained
        assert await redis.llen(queue._scheduled_key) == 0

    async def test_concurrent_consumers_exclusive_delivery(self):
        """Multiple consumers on the same queue get each item exactly once."""
        queue = TaskQueue.for_key("conc-cons")
        runs = [_make_task_run("conc-cons") for _ in range(20)]
        for r in runs:
            await queue.put(r)

        received: list[str] = []
        lock = asyncio.Lock()

        async def consumer():
            while True:
                try:
                    result = await asyncio.wait_for(queue.get(), timeout=2)
                    async with lock:
                        received.append(str(result.id))
                except asyncio.TimeoutError:
                    return

        await asyncio.gather(*(consumer() for _ in range(5)))

        assert len(received) == 20, f"Expected 20, got {len(received)}"
        assert len(set(received)) == 20, "Duplicate deliveries detected"


class TestMultiQueue:
    async def test_get_from_multiple_keys(self):
        run_a = _make_task_run("key-a")
        run_b = _make_task_run("key-b")

        await TaskQueue.for_key("key-a").put(run_a)
        await TaskQueue.for_key("key-b").put(run_b)

        mq = MultiQueue(["key-a", "key-b"])
        results = set()
        results.add((await mq.get()).id)
        results.add((await mq.get()).id)

        assert results == {run_a.id, run_b.id}

    async def test_get_timeout_when_empty(self):
        mq = MultiQueue(["empty-key"])
        with pytest.raises(asyncio.TimeoutError):
            await mq.get()

    async def test_retry_priority_across_keys(self):
        scheduled = _make_task_run("key-a")
        retried = _make_task_run("key-b")

        await TaskQueue.for_key("key-a").put(scheduled)
        await TaskQueue.for_key("key-b").retry(retried)

        mq = MultiQueue(["key-a", "key-b"])
        # Retry should come first
        result = await mq.get()
        assert result.id == retried.id

    async def test_only_returns_subscribed_keys(self):
        """MultiQueue should never return items from unsubscribed keys."""
        run_a = _make_task_run("mq-a")
        run_b = _make_task_run("mq-b")
        run_c = _make_task_run("mq-c")

        await TaskQueue.for_key("mq-a").put(run_a)
        await TaskQueue.for_key("mq-b").put(run_b)
        await TaskQueue.for_key("mq-c").put(run_c)

        mq = MultiQueue(["mq-a", "mq-b"])  # NOT "mq-c"

        results = set()
        results.add((await mq.get()).id)
        results.add((await mq.get()).id)

        # Should timeout — nothing left in subscribed keys
        with pytest.raises(asyncio.TimeoutError):
            await mq.get()

        assert results == {run_a.id, run_b.id}
        # "mq-c" item should still be in Redis, untouched
        redis = TaskQueue.for_key("mq-c")._redis()
        assert await redis.llen(TaskQueue.for_key("mq-c")._scheduled_key) == 1
