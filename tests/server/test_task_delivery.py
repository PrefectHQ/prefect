import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import AsyncGenerator
from uuid import uuid4

import anyio
import pytest
from docket import Docket, Worker
from redis.exceptions import ConnectionError as RedisConnectionError

from prefect.server.schemas.core import TaskRun
from prefect.server.schemas.states import Scheduled
from prefect.server.task_delivery import (
    TaskDeliveryUnavailable,
    TaskRunDeliveryManager,
    TaskRunSubscription,
    _delivery_key,
    _queue_key,
    deliver_task_run,
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


@asynccontextmanager
async def delivery_system(
    visibility_timeout: timedelta = timedelta(seconds=1),
) -> AsyncGenerator[tuple[Docket, TaskRunDeliveryManager], None]:
    async with Docket(
        name=f"test-{uuid4()}", url="memory://", execution_ttl=timedelta(0)
    ) as docket:
        docket.register(deliver_task_run)
        manager = TaskRunDeliveryManager(docket, visibility_timeout)
        async with Worker(
            docket,
            concurrency=100,
            minimum_check_interval=timedelta(milliseconds=5),
            scheduling_resolution=timedelta(milliseconds=5),
        ) as worker:
            worker_task = asyncio.create_task(worker.run_forever())
            try:
                yield docket, manager
            finally:
                worker_task.cancel()
                await asyncio.gather(worker_task, return_exceptions=True)


async def wait_for_delivery_completion(
    docket: Docket, task_run: TaskRun, timeout: float = 2
) -> None:
    with anyio.fail_after(timeout):
        while await docket.get_execution(_delivery_key(task_run)) is not None:
            await asyncio.sleep(0.01)


async def test_delivers_and_acknowledges_task_run() -> None:
    async with delivery_system() as (docket, manager):
        task_run = make_task_run()

        async with manager.subscribe([task_run.task_key]) as subscription:
            await manager.publish(task_run)
            delivery = await subscription.receive()
            await subscription.acknowledge(delivery)

            assert delivery.task_run.id == task_run.id
            await wait_for_delivery_completion(docket, task_run)

            with pytest.raises(asyncio.TimeoutError):
                await subscription.receive(timeout=0.01)


async def test_acceptance_survives_docket_cancellation_connection_loss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with delivery_system(timedelta(milliseconds=20)) as (docket, manager):
        task_run = make_task_run()

        async with manager.subscribe([task_run.task_key]) as subscription:
            await manager.publish(task_run)
            delivery = await subscription.receive()

            async def fail_cancel(key: str) -> None:
                raise RedisConnectionError("simulated Redis failover")

            monkeypatch.setattr(docket, "cancel", fail_cancel)
            await subscription.acknowledge(delivery)
            await wait_for_delivery_completion(docket, task_run)

            with pytest.raises(asyncio.TimeoutError):
                await subscription.receive(timeout=0.03)


async def test_subscriptions_only_claim_matching_task_keys() -> None:
    async with delivery_system() as (_, manager):
        task_a = make_task_run("task-a")
        task_b = make_task_run("task-b")

        async with (
            manager.subscribe(["task-a"]) as subscription_a,
            manager.subscribe(["task-b"]) as subscription_b,
        ):
            await manager.publish(task_b)
            await manager.publish(task_a)

            delivery_a = await subscription_a.receive()
            delivery_b = await subscription_b.receive()
            await subscription_a.acknowledge(delivery_a)
            await subscription_b.acknowledge(delivery_b)

            assert delivery_a.task_run.id == task_a.id
            assert delivery_b.task_run.id == task_b.id


async def test_subscription_receives_from_many_task_keys() -> None:
    async with delivery_system() as (_, manager):
        task_runs = [make_task_run(f"task-{index}") for index in range(100)]

        async with manager.subscribe(
            [task_run.task_key for task_run in task_runs]
        ) as subscription:
            for task_run in task_runs:
                await manager.publish(task_run)

            deliveries = []
            for _ in task_runs:
                delivery = await subscription.receive(timeout=5)
                deliveries.append(delivery)
                await subscription.acknowledge(delivery)

        assert {delivery.task_run.id for delivery in deliveries} == {
            task_run.id for task_run in task_runs
        }


async def test_delivery_queue_uses_docket_key_namespace() -> None:
    docket = Docket(
        name="background-tasks",
        url="redis+cluster://localhost:6379/0",
    )

    assert _queue_key(docket, "example.task").startswith(
        "{background-tasks}:task-runs:ready:"
    )


async def test_subscription_reconnects_after_redis_connection_loss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("prefect.server.task_delivery._RECONNECTION_DELAY", 0)

    async with delivery_system() as (_, manager):
        task_run = make_task_run()
        subscription = manager.subscribe([task_run.task_key])
        original_pop_one = subscription._pop_one
        attempts = 0

        async def fail_first_pop():
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise RedisConnectionError("simulated Redis failover")
            return await original_pop_one()

        monkeypatch.setattr(
            TaskRunSubscription,
            "_pop_one",
            lambda self: fail_first_pop(),
        )

        async with subscription:
            await manager.publish(task_run)
            delivery = await subscription.receive()
            await subscription.acknowledge(delivery)

        assert delivery.task_run.id == task_run.id
        assert attempts >= 2


async def test_redelivers_after_subscription_disconnects() -> None:
    async with delivery_system(timedelta(milliseconds=50)) as (_, manager):
        task_run = make_task_run()

        async with manager.subscribe([task_run.task_key]) as first:
            await manager.publish(task_run)
            first_delivery = await first.receive()

        async with manager.subscribe([task_run.task_key]) as second:
            second_delivery = await second.receive()
            await second.acknowledge(second_delivery)

        assert second_delivery.task_run.id == first_delivery.task_run.id
        assert second_delivery.delivery_id == first_delivery.delivery_id


async def test_renewal_prevents_redelivery_while_worker_is_connected() -> None:
    async with delivery_system(timedelta(milliseconds=50)) as (_, manager):
        task_run = make_task_run()

        first = manager.subscribe([task_run.task_key])
        await first.__aenter__()
        first_closed = False
        try:
            async with manager.subscribe([task_run.task_key]) as second:
                await manager.publish(task_run)
                delivery = await first.receive()
                await asyncio.sleep(0.08)

                with pytest.raises(asyncio.TimeoutError):
                    await second.receive(timeout=0.01)

                await first.__aexit__(None, None, None)
                first_closed = True
                redelivery = await second.receive()
                await second.acknowledge(redelivery)
        finally:
            if not first_closed:
                await first.__aexit__(None, None, None)

        assert redelivery.delivery_id == delivery.delivery_id


async def test_unclaimed_delivery_does_not_accumulate_duplicates() -> None:
    async with delivery_system(timedelta(milliseconds=50)) as (_, manager):
        task_run = make_task_run()
        await manager.publish(task_run)

        # Allow several visibility intervals to pass without a subscriber.
        await asyncio.sleep(0.2)

        async with manager.subscribe([task_run.task_key]) as subscription:
            delivery = await subscription.receive()
            await subscription.acknowledge(delivery)

            with pytest.raises(asyncio.TimeoutError):
                await subscription.receive(timeout=0.03)


async def test_publication_is_idempotent() -> None:
    async with delivery_system() as (_, manager):
        task_run = make_task_run()

        async with manager.subscribe([task_run.task_key]) as subscription:
            await manager.publish(task_run)
            await manager.publish(task_run)
            delivery = await subscription.receive()
            await subscription.acknowledge(delivery)

            with pytest.raises(asyncio.TimeoutError):
                await subscription.receive(timeout=0.01)


async def test_scheduled_deliveries_are_fifo() -> None:
    async with delivery_system() as (_, manager):
        task_runs = [make_task_run() for _ in range(10)]
        async with manager.subscribe(["example.task"]) as subscription:
            for task_run in task_runs:
                await manager.publish(task_run)
            deliveries = [await subscription.receive() for _ in task_runs]
            for delivery in deliveries:
                await subscription.acknowledge(delivery)

        assert [delivery.task_run.id for delivery in deliveries] == [
            task_run.id for task_run in task_runs
        ]


async def test_retry_deliveries_have_priority() -> None:
    async with delivery_system() as (_, manager):
        scheduled = make_task_run()
        retry = make_task_run()
        retry.state = Scheduled(name="AwaitingRetry")
        async with manager.subscribe(["example.task"]) as subscription:
            await manager.publish(scheduled)
            await manager.publish(retry)
            first = await subscription.receive()
            second = await subscription.receive()
            await subscription.acknowledge(first)
            await subscription.acknowledge(second)

        assert first.task_run.id == retry.id
        assert second.task_run.id == scheduled.id


async def test_scheduled_queue_applies_backpressure() -> None:
    async with Docket(
        name=f"test-{uuid4()}", url="memory://", execution_ttl=timedelta(0)
    ) as docket:
        docket.register(deliver_task_run)
        manager = TaskRunDeliveryManager(
            docket,
            timedelta(seconds=1),
            max_scheduled_size=1,
            max_retry_size=1,
        )
        first = make_task_run()
        second = make_task_run()
        async with (
            Worker(
                docket,
                minimum_check_interval=timedelta(milliseconds=5),
                scheduling_resolution=timedelta(milliseconds=5),
            ) as worker,
            manager.subscribe(["example.task"]) as subscription,
        ):
            worker_task = asyncio.create_task(worker.run_forever())
            await manager.publish(first)
            blocked = asyncio.create_task(manager.publish(second))
            await asyncio.sleep(0.05)
            assert not blocked.done()
            delivery = await subscription.receive()
            await blocked
            await subscription.acknowledge(delivery)
            second_delivery = await subscription.receive()
            await subscription.acknowledge(second_delivery)
            worker_task.cancel()
            await asyncio.gather(worker_task, return_exceptions=True)


async def test_docket_schedules_delivery() -> None:
    async with delivery_system() as (_, manager):
        task_run = make_task_run()

        async with manager.subscribe([task_run.task_key]) as subscription:
            await manager.schedule(
                task_run,
                when=now("UTC") + timedelta(milliseconds=100),
            )

            with pytest.raises(asyncio.TimeoutError):
                await subscription.receive(timeout=0.02)

            delivery = await subscription.receive(timeout=2)
            await subscription.acknowledge(delivery)

        assert delivery.task_run.id == task_run.id


async def test_docket_worker_restart_recovers_unacknowledged_delivery() -> None:
    async with Docket(
        name=f"test-{uuid4()}", url="memory://", execution_ttl=timedelta(0)
    ) as docket:
        docket.register(deliver_task_run)
        manager = TaskRunDeliveryManager(docket, timedelta(milliseconds=50))
        task_run = make_task_run()

        first_worker = Worker(
            docket,
            redelivery_timeout=timedelta(milliseconds=50),
            minimum_check_interval=timedelta(milliseconds=5),
            scheduling_resolution=timedelta(milliseconds=5),
        )
        async with first_worker:
            run = asyncio.create_task(first_worker.run_forever())
            await manager.publish(task_run)
            await asyncio.sleep(0.02)
            run.cancel()
            await asyncio.gather(run, return_exceptions=True)

        await asyncio.sleep(0.06)
        async with (
            Worker(
                docket,
                redelivery_timeout=timedelta(milliseconds=50),
                minimum_check_interval=timedelta(milliseconds=5),
                scheduling_resolution=timedelta(milliseconds=5),
            ) as second_worker,
            manager.subscribe([task_run.task_key]) as subscription,
        ):
            run = asyncio.create_task(second_worker.run_forever())
            delivery = await subscription.receive(timeout=2)
            await subscription.acknowledge(delivery)
            await wait_for_delivery_completion(docket, task_run)
            run.cancel()
            await asyncio.gather(run, return_exceptions=True)

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
