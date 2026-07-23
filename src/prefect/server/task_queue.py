"""
Durable delivery of deferred task runs to connected task workers.

Task runs are scheduled through Docket so every API replica observes the same
queue. A Docket worker on the replica that owns a compatible task-worker
WebSocket performs the delivery and does not acknowledge it until the remote
worker acknowledges receipt.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import AsyncGenerator, ClassVar

import anyio
from docket import CurrentExecution, Docket, Worker
from docket.dependencies import AdmissionBlocked
from docket.execution import Execution

import prefect.server.schemas as schemas


class TaskQueueUnavailable(RuntimeError):
    """Raised when the task delivery Docket has not been started."""


class TaskDeliveryUnavailable(RuntimeError):
    """Raised when no local task worker can accept a task run."""


@dataclass(eq=False)
class TaskDelivery:
    task_run: schemas.core.TaskRun
    acknowledged: asyncio.Future[None]


@dataclass(eq=False)
class TaskWorkerSubscription:
    task_keys: frozenset[str]
    client_id: str
    deliveries: asyncio.Queue[TaskDelivery] = field(default_factory=asyncio.Queue)
    closed: bool = False


class TaskQueue:
    """Process-local routing around a shared Docket delivery queue."""

    _docket: ClassVar[Docket | None] = None
    _subscriptions: ClassVar[list[TaskWorkerSubscription]] = []
    _lock: ClassVar[asyncio.Lock | None] = None
    _subscriptions_changed: ClassVar[asyncio.Condition | None] = None
    _next_subscription: ClassVar[dict[str, int]] = {}

    @classmethod
    def configure(cls, docket: Docket) -> None:
        if cls._docket is not None and cls._docket is not docket:
            raise RuntimeError("The task delivery queue is already configured")
        cls._docket = docket
        cls._subscriptions = []
        cls._lock = asyncio.Lock()
        cls._subscriptions_changed = asyncio.Condition(cls._lock)
        cls._next_subscription = {}

    @classmethod
    def reset(cls, docket: Docket | None = None) -> None:
        if docket is not None and cls._docket is not docket:
            return

        for subscription in cls._subscriptions:
            subscription.closed = True
            while not subscription.deliveries.empty():
                delivery = subscription.deliveries.get_nowait()
                if not delivery.acknowledged.done():
                    delivery.acknowledged.set_exception(
                        TaskDeliveryUnavailable("Task-worker subscription closed")
                    )

        cls._docket = None
        cls._subscriptions = []
        cls._lock = None
        cls._subscriptions_changed = None
        cls._next_subscription = {}

    @classmethod
    async def enqueue(
        cls,
        task_run: schemas.core.TaskRun,
        *,
        when: datetime | None = None,
    ) -> Execution:
        if cls._docket is None:
            raise TaskQueueUnavailable("The task delivery queue is not running")

        return await cls._docket.add(
            deliver_task_run,
            # Repeated publication of one state transition is idempotent while
            # its delivery is active. A retry has a new state ID and receives
            # a distinct delivery.
            key=cls._delivery_key(task_run),
            when=when,
        )(task_run)

    @staticmethod
    def _delivery_key(task_run: schemas.core.TaskRun) -> str:
        state_id = task_run.state_id
        if state_id is None and task_run.state is not None:
            state_id = task_run.state.id
        return f"task-run:{task_run.id}:{state_id}"

    @classmethod
    @asynccontextmanager
    async def subscribe(
        cls, task_keys: list[str], client_id: str
    ) -> AsyncGenerator[TaskWorkerSubscription, None]:
        if cls._lock is None:
            raise TaskQueueUnavailable("The task delivery queue is not running")

        subscription = TaskWorkerSubscription(
            task_keys=frozenset(task_keys), client_id=client_id
        )
        async with cls._lock:
            cls._subscriptions.append(subscription)
            assert cls._subscriptions_changed is not None
            cls._subscriptions_changed.notify_all()

        try:
            yield subscription
        finally:
            async with cls._lock:
                subscription.closed = True
                if subscription in cls._subscriptions:
                    cls._subscriptions.remove(subscription)
                assert cls._subscriptions_changed is not None
                cls._subscriptions_changed.notify_all()

                while not subscription.deliveries.empty():
                    delivery = subscription.deliveries.get_nowait()
                    if not delivery.acknowledged.done():
                        delivery.acknowledged.set_exception(
                            TaskDeliveryUnavailable(
                                "Task-worker subscription disconnected"
                            )
                        )

    @classmethod
    async def deliver(cls, task_run: schemas.core.TaskRun) -> None:
        subscription = await cls._claim_subscription(task_run.task_key)
        if subscription is None:
            raise TaskDeliveryUnavailable(
                f"No task worker is connected for task key {task_run.task_key!r}"
            )

        acknowledged = asyncio.get_running_loop().create_future()
        delivery = TaskDelivery(task_run=task_run, acknowledged=acknowledged)
        await subscription.deliveries.put(delivery)
        try:
            await acknowledged
        except Exception as exc:
            raise TaskDeliveryUnavailable(
                f"Task worker {subscription.client_id!r} disconnected before "
                f"acknowledging task run {task_run.id}"
            ) from exc

    @classmethod
    async def _claim_subscription(cls, task_key: str) -> TaskWorkerSubscription | None:
        if cls._lock is None:
            return None

        async with cls._lock:
            eligible = [
                subscription
                for subscription in cls._subscriptions
                if not subscription.closed and task_key in subscription.task_keys
            ]
            if not eligible:
                return None

            offset = cls._next_subscription.get(task_key, 0) % len(eligible)
            subscription = eligible[offset]
            cls._next_subscription[task_key] = offset + 1
            return subscription

    @classmethod
    async def wait_for_subscriptions(cls, *, present: bool) -> None:
        condition = cls._subscriptions_changed
        if condition is None:
            raise TaskQueueUnavailable("The task delivery queue is not running")

        async with condition:
            await condition.wait_for(lambda: bool(cls._subscriptions) == present)


async def deliver_task_run(
    task_run: schemas.core.TaskRun,
    execution: Execution = CurrentExecution(),
) -> None:
    """Deliver a task run through a compatible WebSocket on this API replica."""
    try:
        await TaskQueue.deliver(task_run)
    except TaskDeliveryUnavailable as exc:
        raise AdmissionBlocked(
            execution,
            reason=str(exc),
            retry_delay=timedelta(seconds=1),
        ) from exc


@asynccontextmanager
async def task_queue_lifespan(
    docket: Docket,
    *,
    concurrency: int = 100,
    redelivery_timeout: timedelta,
) -> AsyncGenerator[None, None]:
    """Run the Docket worker responsible for deferred task-run delivery."""
    docket.register(deliver_task_run)
    TaskQueue.configure(docket)

    async def run_workers_when_subscribed() -> None:
        while True:
            await TaskQueue.wait_for_subscriptions(present=True)
            async with Worker(
                docket,
                concurrency=concurrency,
                redelivery_timeout=redelivery_timeout,
                schedule_automatic_tasks=False,
            ) as worker:
                run_task = asyncio.create_task(
                    worker.run_forever(),
                    name=f"{docket.name} - task delivery worker",
                )
                no_subscriptions = asyncio.create_task(
                    TaskQueue.wait_for_subscriptions(present=False),
                    name=f"{docket.name} - wait for task-worker disconnect",
                )
                try:
                    done, _ = await asyncio.wait(
                        (run_task, no_subscriptions),
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    if run_task in done:
                        await run_task
                        raise RuntimeError(
                            "Task delivery Docket worker exited unexpectedly"
                        )
                    no_subscriptions.result()
                finally:
                    if not no_subscriptions.done():
                        no_subscriptions.cancel()
                        await asyncio.gather(no_subscriptions, return_exceptions=True)
            await run_task

    try:
        async with anyio.create_task_group() as task_group:
            task_group.start_soon(
                run_workers_when_subscribed,
                name=f"{docket.name} - task delivery supervisor",
            )
            try:
                yield
            finally:
                task_group.cancel_scope.cancel()
    finally:
        TaskQueue.reset(docket)
