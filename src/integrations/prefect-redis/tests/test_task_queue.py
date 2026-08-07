import asyncio
from uuid import uuid4

import pytest
from prefect_redis.task_queue import Consumer, Publisher, RedisTaskQueueSettings

from prefect.server.schemas.core import TaskRun
from prefect.server.task_queue import TaskQueuePriority


def task_run(task_key: str = "tasks.example") -> TaskRun:
    return TaskRun(
        id=uuid4(),
        flow_run_id=None,
        task_key=task_key,
        dynamic_key=str(uuid4()),
    )


async def test_only_delivers_registered_task_keys() -> None:
    expected = task_run("tasks.expected")
    unexpected = task_run("tasks.unexpected")
    publisher = Publisher()
    await publisher.publish(unexpected)
    await publisher.publish(expected)

    async with Consumer([expected.task_key], "worker") as consumer:
        delivery = await consumer.get()
        assert delivery.task_run.id == expected.id
        await consumer.acknowledge(delivery)


async def test_competing_consumers_deliver_each_run_once() -> None:
    runs = [task_run() for _ in range(10)]
    publisher = Publisher()
    for run in runs:
        await publisher.publish(run)

    async with (
        Consumer([runs[0].task_key], "worker-a") as first,
        Consumer([runs[0].task_key], "worker-b") as second,
    ):
        deliveries = []
        for consumer in [first, second] * 5:
            delivery = await consumer.get()
            deliveries.append(delivery)
            await consumer.acknowledge(delivery)

    assert {delivery.task_run.id for delivery in deliveries} == {run.id for run in runs}


async def test_retries_are_delivered_before_scheduled_runs() -> None:
    scheduled = task_run()
    retry = task_run()
    publisher = Publisher()
    await publisher.publish(scheduled)
    await publisher.publish(retry, TaskQueuePriority.RETRY)

    async with Consumer([scheduled.task_key], "worker") as consumer:
        first = await consumer.get()
        await consumer.acknowledge(first)
        second = await consumer.get()
        await consumer.acknowledge(second)

    assert [first.task_run.id, second.task_run.id] == [retry.id, scheduled.id]


async def test_graceful_disconnect_releases_unacknowledged_run() -> None:
    run = task_run()
    await Publisher().publish(run)

    async with Consumer([run.task_key], "departing-worker") as consumer:
        delivery = await consumer.get()
        assert delivery.task_run.id == run.id

    async with Consumer([run.task_key], "replacement-worker") as consumer:
        redelivered = await consumer.get()
        await consumer.acknowledge(redelivered)

    assert redelivered.task_run.id == run.id


async def test_failed_server_delivery_is_reclaimed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PREFECT_REDIS_TASK_QUEUE_VISIBILITY_TIMEOUT", "1")
    run = task_run()
    await Publisher().publish(run)

    failed = Consumer([run.task_key], "failed-server")
    await failed.__aenter__()
    delivery = await failed.get()
    assert delivery.task_run.id == run.id
    # Deliberately omit __aexit__, as if the server process was killed.

    await asyncio.sleep(1)
    async with Consumer([run.task_key], "replacement-server") as replacement:
        redelivered = await replacement.get()
        await replacement.acknowledge(redelivered)

    assert redelivered.task_run.id == run.id


async def test_acknowledged_run_is_not_redelivered() -> None:
    run = task_run()
    await Publisher().publish(run)

    async with Consumer([run.task_key], "first-worker") as consumer:
        delivery = await consumer.get()
        await consumer.acknowledge(delivery)

    async with Consumer([run.task_key], "second-worker") as consumer:
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(consumer.get(), timeout=0.1)


def test_settings_are_scoped_to_prefect_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PREFECT_REDIS_TASK_QUEUE_VISIBILITY_TIMEOUT", "42")
    assert RedisTaskQueueSettings().visibility_timeout == 42
