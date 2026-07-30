# pyright: reportPrivateUsage=false

import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import AsyncGenerator
from uuid import uuid4

import pytest
from docket import Docket

from prefect.server.schemas.core import TaskRun
from prefect.server.schemas.states import Scheduled
from prefect.server.task_delivery import (
    _TaskDeliveryUnavailable,
    _TaskRunDeliveryManager,
    task_run_delivery_lifespan,
)


def make_task_run(task_key: str = "example.task") -> TaskRun:
    return TaskRun(
        id=uuid4(),
        flow_run_id=None,
        task_key=task_key,
        dynamic_key=f"{task_key}-{uuid4()}",
        state=Scheduled(),
    )


@asynccontextmanager
async def delivery_system(
    visibility_timeout: timedelta = timedelta(seconds=1),
    *,
    max_scheduled_size: int | None = None,
    max_retry_size: int | None = None,
) -> AsyncGenerator[_TaskRunDeliveryManager, None]:
    async with Docket(name=f"test-{uuid4()}", url="memory://") as docket:
        yield _TaskRunDeliveryManager(
            docket,
            visibility_timeout,
            max_scheduled_size=max_scheduled_size,
            max_retry_size=max_retry_size,
        )


async def test_delivers_and_acknowledges_task_run():
    async with delivery_system() as manager:
        task_run = make_task_run()

        async with manager.subscribe([task_run.task_key]) as subscription:
            assert await manager.schedule(task_run)
            delivery = await subscription.receive()
            await subscription.acknowledge(delivery)

            assert delivery.task_run.id == task_run.id
            with pytest.raises(asyncio.TimeoutError):
                await subscription.receive(timeout=0.01)


async def test_subscriptions_only_claim_matching_task_keys():
    async with delivery_system() as manager:
        task_a = make_task_run("task-a")
        task_b = make_task_run("task-b")

        async with (
            manager.subscribe(["task-a"]) as subscription_a,
            manager.subscribe(["task-b"]) as subscription_b,
        ):
            await manager.schedule(task_b)
            await manager.schedule(task_a)

            delivery_a = await subscription_a.receive()
            delivery_b = await subscription_b.receive()
            await subscription_a.acknowledge(delivery_a)
            await subscription_b.acknowledge(delivery_b)

        assert delivery_a.task_run.id == task_a.id
        assert delivery_b.task_run.id == task_b.id


async def test_subscription_receives_from_many_task_keys():
    async with delivery_system() as manager:
        task_runs = [make_task_run(f"task-{index}") for index in range(100)]

        async with manager.subscribe(
            [task_run.task_key for task_run in task_runs]
        ) as subscription:
            for task_run in task_runs:
                await manager.schedule(task_run)

            deliveries = []
            for _ in task_runs:
                delivery = await subscription.receive(timeout=5)
                deliveries.append(delivery)
                await subscription.acknowledge(delivery)

        assert {delivery.task_run.id for delivery in deliveries} == {
            task_run.id for task_run in task_runs
        }


async def test_disconnect_immediately_releases_delivery_to_retry_lane():
    async with delivery_system(timedelta(minutes=5)) as manager:
        task_run = make_task_run()

        async with manager.subscribe([task_run.task_key]) as first:
            await manager.schedule(task_run)
            first_delivery = await first.receive()

        async with manager.subscribe([task_run.task_key]) as second:
            redelivery = await second.receive(timeout=1)
            await second.acknowledge(redelivery)

        assert redelivery.task_run.id == first_delivery.task_run.id


async def test_publication_is_idempotent_while_queued():
    async with delivery_system() as manager:
        task_run = make_task_run()

        assert await manager.schedule(task_run)
        assert not await manager.schedule(task_run)

        async with manager.subscribe([task_run.task_key]) as subscription:
            delivery = await subscription.receive()
            await subscription.acknowledge(delivery)

        assert await manager.schedule(task_run)


async def test_scheduled_deliveries_are_fifo():
    async with delivery_system() as manager:
        task_runs = [make_task_run() for _ in range(10)]
        for task_run in task_runs:
            await manager.schedule(task_run)

        async with manager.subscribe(["example.task"]) as subscription:
            deliveries = []
            for _ in task_runs:
                delivery = await subscription.receive()
                deliveries.append(delivery)
                await subscription.acknowledge(delivery)

        assert [delivery.task_run.id for delivery in deliveries] == [
            task_run.id for task_run in task_runs
        ]


async def test_retry_deliveries_have_priority():
    async with delivery_system() as manager:
        scheduled = make_task_run("task-a")
        retry = make_task_run("task-b")
        retry.state = Scheduled(name="AwaitingRetry")
        await manager.schedule(scheduled)
        await manager.schedule(retry)

        async with manager.subscribe(["task-a", "task-b"]) as subscription:
            first = await subscription.receive()
            await subscription.acknowledge(first)
            second = await subscription.receive()
            await subscription.acknowledge(second)

        assert first.task_run.id == retry.id
        assert second.task_run.id == scheduled.id


async def test_scheduled_queue_applies_backpressure():
    async with delivery_system(
        max_scheduled_size=1,
        max_retry_size=1,
    ) as manager:
        first = make_task_run()
        second = make_task_run()
        await manager.schedule(first)
        blocked = asyncio.create_task(manager.schedule(second))
        await asyncio.sleep(0.05)
        assert not blocked.done()

        async with manager.subscribe(["example.task"]) as subscription:
            delivery = await subscription.receive()
            await subscription.acknowledge(delivery)
            await blocked
            second_delivery = await subscription.receive()
            await subscription.acknowledge(second_delivery)


async def test_retry_queue_applies_backpressure():
    async with delivery_system(
        max_scheduled_size=1,
        max_retry_size=1,
    ) as manager:
        first = make_task_run()
        first.state = Scheduled(name="AwaitingRetry")
        second = make_task_run()
        second.state = Scheduled(name="AwaitingRetry")
        await manager.schedule(first)
        blocked = asyncio.create_task(manager.schedule(second))
        await asyncio.sleep(0.05)
        assert not blocked.done()

        async with manager.subscribe(["example.task"]) as subscription:
            delivery = await subscription.receive()
            await subscription.acknowledge(delivery)
            await blocked
            second_delivery = await subscription.receive()
            await subscription.acknowledge(second_delivery)


async def test_lifespan_exposes_manager():
    async with Docket(name=f"test-{uuid4()}", url="memory://") as docket:
        with pytest.raises(_TaskDeliveryUnavailable):
            _TaskRunDeliveryManager.active()

        async with task_run_delivery_lifespan(
            docket, visibility_timeout=timedelta(seconds=1)
        ):
            _TaskRunDeliveryManager.active()
            with pytest.raises(RuntimeError, match="already running"):
                async with task_run_delivery_lifespan(
                    docket, visibility_timeout=timedelta(seconds=1)
                ):
                    pass

        with pytest.raises(_TaskDeliveryUnavailable):
            _TaskRunDeliveryManager.active()


# pyright: reportPrivateUsage=false
