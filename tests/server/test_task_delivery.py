import asyncio
from datetime import timedelta
from uuid import uuid4

import pytest
from docket import Docket, Worker

from prefect.server.schemas.core import TaskRun
from prefect.server.task_delivery import (
    TaskDeliveryUnavailable,
    TaskRunDeliveryManager,
    publish_task_run,
    task_run_delivery_lifespan,
)
from prefect.types._datetime import now


def make_task_run(task_key: str = "example.task") -> TaskRun:
    return TaskRun(
        id=uuid4(),
        flow_run_id=None,
        task_key=task_key,
        dynamic_key=f"{task_key}-{uuid4()}",
    )


async def test_delivers_and_acknowledges_task_run() -> None:
    async with Docket(name=f"test-{uuid4()}", url="memory://") as docket:
        manager = TaskRunDeliveryManager(docket, timedelta(seconds=1))
        task_run = make_task_run()

        async with manager.subscribe([task_run.task_key], "worker-1") as subscription:
            await manager.publish(task_run)
            delivery = await subscription.receive()
            await subscription.acknowledge(delivery)

            assert delivery.task_run.id == task_run.id
            with pytest.raises(asyncio.TimeoutError):
                await subscription.receive(timeout=0.01)


async def test_subscriptions_only_claim_matching_task_keys() -> None:
    async with Docket(name=f"test-{uuid4()}", url="memory://") as docket:
        manager = TaskRunDeliveryManager(docket, timedelta(seconds=1))
        task_a = make_task_run("task-a")
        task_b = make_task_run("task-b")

        async with (
            manager.subscribe(["task-a"], "worker-a") as subscription_a,
            manager.subscribe(["task-b"], "worker-b") as subscription_b,
        ):
            await manager.publish(task_b)
            await manager.publish(task_a)

            delivery_a = await subscription_a.receive()
            delivery_b = await subscription_b.receive()

            assert delivery_a.task_run.id == task_a.id
            assert delivery_b.task_run.id == task_b.id


async def test_subscription_receives_from_many_task_keys() -> None:
    async with Docket(name=f"test-{uuid4()}", url="memory://") as docket:
        manager = TaskRunDeliveryManager(docket, timedelta(seconds=1))
        task_runs = [make_task_run(f"task-{index}") for index in range(100)]

        async with manager.subscribe(
            [task_run.task_key for task_run in task_runs], "worker"
        ) as subscription:
            for task_run in task_runs:
                await manager.publish(task_run)

            deliveries = [await subscription.receive() for _ in task_runs]

        assert {delivery.task_run.id for delivery in deliveries} == {
            task_run.id for task_run in task_runs
        }


async def test_redelivers_after_visibility_timeout() -> None:
    async with Docket(name=f"test-{uuid4()}", url="memory://") as docket:
        manager = TaskRunDeliveryManager(docket, timedelta(milliseconds=10))
        task_run = make_task_run()

        async with manager.subscribe([task_run.task_key], "worker-1") as first:
            await manager.publish(task_run)
            first_delivery = await first.receive()

        await asyncio.sleep(0.02)
        async with manager.subscribe([task_run.task_key], "worker-2") as second:
            second_delivery = await second.receive()

        assert second_delivery.task_run.id == first_delivery.task_run.id
        assert second_delivery.message_id == first_delivery.message_id


async def test_renewal_prevents_redelivery_while_worker_is_connected() -> None:
    async with Docket(name=f"test-{uuid4()}", url="memory://") as docket:
        manager = TaskRunDeliveryManager(docket, timedelta(milliseconds=30))
        task_run = make_task_run()

        async with (
            manager.subscribe([task_run.task_key], "worker-1") as first,
            manager.subscribe([task_run.task_key], "worker-2") as second,
        ):
            await manager.publish(task_run)
            delivery = await first.receive()
            await asyncio.sleep(0.02)
            await first.renew()
            await asyncio.sleep(0.02)

            with pytest.raises(asyncio.TimeoutError):
                await second.receive(timeout=0.005)

            await asyncio.sleep(0.02)
            redelivery = await second.receive()

        assert redelivery.message_id == delivery.message_id


async def test_publication_is_idempotent() -> None:
    async with Docket(name=f"test-{uuid4()}", url="memory://") as docket:
        manager = TaskRunDeliveryManager(docket, timedelta(seconds=1))
        task_run = make_task_run()

        async with manager.subscribe([task_run.task_key], "worker-1") as subscription:
            await manager.publish(task_run)
            await manager.publish(task_run)
            delivery = await subscription.receive()
            await subscription.acknowledge(delivery)

            with pytest.raises(asyncio.TimeoutError):
                await subscription.receive(timeout=0.01)


async def test_docket_schedules_publication() -> None:
    async with Docket(name=f"test-{uuid4()}", url="memory://") as docket:
        manager = TaskRunDeliveryManager(docket, timedelta(seconds=1))
        task_run = make_task_run()
        docket.register(publish_task_run)

        async with (
            Worker(docket) as worker,
            manager.subscribe([task_run.task_key], "worker-1") as subscription,
        ):
            await manager.schedule(
                task_run,
                when=now("UTC") + timedelta(milliseconds=50),
            )

            with pytest.raises(asyncio.TimeoutError):
                await subscription.receive(timeout=0.01)

            await worker.run_until_finished()
            delivery = await subscription.receive()

        assert delivery.task_run.id == task_run.id


async def test_lifespan_exposes_manager() -> None:
    async with Docket(name=f"test-{uuid4()}", url="memory://") as docket:
        with pytest.raises(TaskDeliveryUnavailable):
            TaskRunDeliveryManager.active()

        async with task_run_delivery_lifespan(
            docket, visibility_timeout=timedelta(seconds=1)
        ) as manager:
            assert TaskRunDeliveryManager.active() is manager

        with pytest.raises(TaskDeliveryUnavailable):
            TaskRunDeliveryManager.active()
