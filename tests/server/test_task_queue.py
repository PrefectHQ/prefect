import asyncio
from datetime import timedelta
from uuid import uuid4

from docket import Docket

from prefect.server.schemas.core import TaskRun
from prefect.server.task_queue import (
    TaskDeliveryUnavailable,
    TaskQueue,
    task_queue_lifespan,
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
    async with Docket(
        name=f"test-task-delivery-{uuid4()}",
        url="memory://",
        execution_ttl=timedelta(0),
    ) as docket:
        async with task_queue_lifespan(docket, redelivery_timeout=timedelta(seconds=1)):
            task_run = make_task_run()
            async with TaskQueue.subscribe([task_run.task_key], "worker-1") as worker:
                await TaskQueue.enqueue(task_run)
                delivery = await asyncio.wait_for(worker.deliveries.get(), timeout=2)
                assert delivery.task_run.id == task_run.id
                delivery.acknowledged.set_result(None)


async def test_delivers_multiple_runs_before_acknowledgement() -> None:
    async with Docket(
        name=f"test-task-delivery-{uuid4()}",
        url="memory://",
        execution_ttl=timedelta(0),
    ) as docket:
        async with task_queue_lifespan(
            docket,
            concurrency=10,
            redelivery_timeout=timedelta(seconds=1),
        ):
            task_runs = [make_task_run() for _ in range(10)]
            async with TaskQueue.subscribe(
                [task_runs[0].task_key], "worker-1"
            ) as worker:
                for task_run in task_runs:
                    await TaskQueue.enqueue(task_run)

                deliveries = [
                    await asyncio.wait_for(worker.deliveries.get(), timeout=2)
                    for _ in task_runs
                ]
                assert {delivery.task_run.id for delivery in deliveries} == {
                    task_run.id for task_run in task_runs
                }
                for delivery in deliveries:
                    delivery.acknowledged.set_result(None)


async def test_waits_until_compatible_worker_connects() -> None:
    async with Docket(
        name=f"test-task-delivery-{uuid4()}",
        url="memory://",
        execution_ttl=timedelta(0),
    ) as docket:
        async with task_queue_lifespan(docket, redelivery_timeout=timedelta(seconds=1)):
            task_run = make_task_run()
            await TaskQueue.enqueue(task_run)
            await asyncio.sleep(0.1)

            async with TaskQueue.subscribe([task_run.task_key], "worker-1") as worker:
                delivery = await asyncio.wait_for(worker.deliveries.get(), timeout=2)
                assert delivery.task_run.id == task_run.id
                delivery.acknowledged.set_result(None)


async def test_redelivers_after_worker_disconnects_before_acknowledgement() -> None:
    async with Docket(
        name=f"test-task-delivery-{uuid4()}",
        url="memory://",
        execution_ttl=timedelta(0),
    ) as docket:
        async with task_queue_lifespan(docket, redelivery_timeout=timedelta(seconds=1)):
            task_run = make_task_run()
            async with TaskQueue.subscribe([task_run.task_key], "worker-1") as worker:
                await TaskQueue.enqueue(task_run)
                first_delivery = await asyncio.wait_for(
                    worker.deliveries.get(), timeout=2
                )
                first_delivery.acknowledged.set_exception(
                    TaskDeliveryUnavailable("simulated disconnect")
                )

            async with TaskQueue.subscribe([task_run.task_key], "worker-2") as worker:
                second_delivery = await asyncio.wait_for(
                    worker.deliveries.get(), timeout=2
                )
                assert second_delivery.task_run.id == task_run.id
                second_delivery.acknowledged.set_result(None)


async def test_stable_task_run_key_deduplicates_repeated_enqueue() -> None:
    async with Docket(
        name=f"test-task-delivery-{uuid4()}",
        url="memory://",
        execution_ttl=timedelta(0),
    ) as docket:
        async with task_queue_lifespan(docket, redelivery_timeout=timedelta(seconds=1)):
            task_run = make_task_run()
            await TaskQueue.enqueue(task_run)
            await TaskQueue.enqueue(task_run)

            async with TaskQueue.subscribe([task_run.task_key], "worker-1") as worker:
                delivery = await asyncio.wait_for(worker.deliveries.get(), timeout=2)
                delivery.acknowledged.set_result(None)

                try:
                    await asyncio.wait_for(worker.deliveries.get(), timeout=0.2)
                except asyncio.TimeoutError:
                    pass
                else:
                    raise AssertionError("Task run was delivered more than once")


async def test_honors_scheduled_delivery_time() -> None:
    async with Docket(
        name=f"test-task-delivery-{uuid4()}",
        url="memory://",
        execution_ttl=timedelta(0),
    ) as docket:
        async with task_queue_lifespan(docket, redelivery_timeout=timedelta(seconds=1)):
            task_run = make_task_run()
            async with TaskQueue.subscribe([task_run.task_key], "worker-1") as worker:
                await TaskQueue.enqueue(
                    task_run, when=now("UTC") + timedelta(seconds=0.2)
                )

                try:
                    await asyncio.wait_for(worker.deliveries.get(), timeout=0.05)
                except asyncio.TimeoutError:
                    pass
                else:
                    raise AssertionError("Task run was delivered before its schedule")

                delivery = await asyncio.wait_for(worker.deliveries.get(), timeout=2)
                delivery.acknowledged.set_result(None)
