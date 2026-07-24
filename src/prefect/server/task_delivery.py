"""Durable delivery of deferred task runs to TaskWorkers."""

from __future__ import annotations

import asyncio
import hashlib
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import AsyncGenerator, ClassVar

import orjson
from docket import CurrentDocket, Docket, Perpetual
from redis.exceptions import ConnectionError as RedisConnectionError

import prefect.server.schemas as schemas
from prefect.logging import get_logger

_RECONNECTION_DELAY = 0.5
_READY = "ready"
_CLAIMED = "claimed"
_logger = get_logger(__name__)


class TaskDeliveryUnavailable(RuntimeError):
    """Raised when task delivery has not been configured."""


@dataclass(frozen=True)
class TaskRunDelivery:
    task_run: schemas.core.TaskRun
    delivery_id: str
    queue: str
    message: bytes


class TaskRunSubscription:
    """A TaskWorker subscription to one or more task-key queues."""

    def __init__(
        self,
        docket: Docket,
        task_keys: list[str],
        visibility_timeout: timedelta,
    ) -> None:
        self._docket = docket
        self._queues = [_queue_key(docket, task_key) for task_key in task_keys]
        self._visibility_timeout = visibility_timeout
        self._outstanding: dict[str, TaskRunDelivery] = {}
        self._visibility_renewer: asyncio.Task[None] | None = None

    async def __aenter__(self) -> "TaskRunSubscription":
        self._visibility_renewer = asyncio.create_task(self._renew_visibility())
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        if self._visibility_renewer is not None:
            self._visibility_renewer.cancel()
            await asyncio.gather(self._visibility_renewer, return_exceptions=True)

        deliveries = list(self._outstanding.values())
        self._outstanding.clear()
        for delivery in deliveries:
            try:
                await self._requeue(delivery)
            except RedisConnectionError:
                # The Docket execution offers the run again after the visibility
                # timeout if this API process cannot return it explicitly.
                pass

    async def receive(self, timeout: float = 1) -> TaskRunDelivery:
        """Receive a task run matching this subscription."""
        return await asyncio.wait_for(self._receive_one(), timeout=timeout)

    async def _receive_one(self) -> TaskRunDelivery:
        while True:
            try:
                result = await self._pop_one()
                if result is None:
                    continue

                queue, message = result
                queue = _decode(queue)
                envelope = orjson.loads(message)
                delivery_id = envelope["delivery_id"]

                async with self._docket.redis() as redis:
                    if await redis.exists(_acked_key(self._docket, delivery_id)):
                        await redis.delete(_queued_key(self._docket, delivery_id))
                        continue
                    await redis.set(
                        _queued_key(self._docket, delivery_id),
                        _CLAIMED,
                        ex=self._visibility_timeout,
                    )

                delivery = TaskRunDelivery(
                    task_run=schemas.core.TaskRun.model_validate(envelope["task_run"]),
                    delivery_id=delivery_id,
                    queue=queue,
                    message=message,
                )
                self._outstanding[delivery_id] = delivery
                return delivery
            except RedisConnectionError:
                _logger.warning(
                    "Lost the Redis connection while receiving a task delivery; "
                    "retrying in %.1f seconds",
                    _RECONNECTION_DELAY,
                    exc_info=True,
                )
                await asyncio.sleep(_RECONNECTION_DELAY)

    async def _pop_one(self) -> tuple[bytes, bytes] | None:
        async with self._docket.redis() as redis:
            return await redis.brpop(self._queues, timeout=1)

    async def acknowledge(self, delivery: TaskRunDelivery) -> None:
        """Acknowledge a task run accepted by the connected TaskWorker."""
        async with self._docket.redis() as redis:
            await redis.set(
                _acked_key(self._docket, delivery.delivery_id),
                "1",
                ex=_delivery_ttl(self._visibility_timeout),
            )
            await redis.delete(_queued_key(self._docket, delivery.delivery_id))
            await redis.lrem(delivery.queue, 0, delivery.message)

        self._outstanding.pop(delivery.delivery_id, None)
        # The acceptance marker is authoritative if cancellation races a
        # reschedule or Redis becomes unavailable after the writes above.
        try:
            await self._docket.cancel(delivery.delivery_id)
        except RedisConnectionError:
            _logger.warning(
                "Accepted task delivery %s, but could not cancel its Docket "
                "execution; it will stop when Docket next observes the acceptance",
                delivery.delivery_id,
                exc_info=True,
            )
        else:
            try:
                async with self._docket.redis() as redis:
                    await redis.delete(_acked_key(self._docket, delivery.delivery_id))
            except RedisConnectionError:
                # The marker has a bounded TTL and is safe to leave behind.
                _logger.warning(
                    "Accepted and cancelled task delivery %s, but could not "
                    "remove its acceptance marker",
                    delivery.delivery_id,
                    exc_info=True,
                )

    async def _requeue(self, delivery: TaskRunDelivery) -> None:
        async with self._docket.redis() as redis:
            if await redis.exists(_acked_key(self._docket, delivery.delivery_id)):
                return
            await redis.rpush(delivery.queue, delivery.message)
            await redis.set(
                _queued_key(self._docket, delivery.delivery_id),
                _READY,
                ex=self._visibility_timeout * 2,
            )

    async def _renew_visibility(self) -> None:
        interval = max(0.001, self._visibility_timeout.total_seconds() / 4)
        while True:
            await asyncio.sleep(interval)
            try:
                async with self._docket.redis() as redis:
                    for delivery_id in list(self._outstanding):
                        await redis.set(
                            _queued_key(self._docket, delivery_id),
                            _CLAIMED,
                            xx=True,
                            ex=self._visibility_timeout,
                        )
            except RedisConnectionError:
                _logger.warning(
                    "Lost the Redis connection while renewing task delivery visibility",
                    exc_info=True,
                )


class TaskRunDeliveryManager:
    """Schedules Docket executions and creates keyed TaskWorker subscriptions."""

    _active: ClassVar["TaskRunDeliveryManager | None"] = None

    def __init__(self, docket: Docket, visibility_timeout: timedelta) -> None:
        self._docket = docket
        self._visibility_timeout = visibility_timeout

    @classmethod
    def active(cls) -> "TaskRunDeliveryManager":
        if cls._active is None:
            raise TaskDeliveryUnavailable("Task delivery is not running")
        return cls._active

    async def schedule(
        self,
        task_run: schemas.core.TaskRun,
        *,
        when: datetime | None = None,
    ) -> None:
        await self._docket.add(
            deliver_task_run,
            key=_delivery_key(task_run),
            when=when,
        )(task_run, self._visibility_timeout.total_seconds())

    async def publish(self, task_run: schemas.core.TaskRun) -> None:
        await self.schedule(task_run)

    def subscribe(self, task_keys: list[str]) -> TaskRunSubscription:
        return TaskRunSubscription(
            self._docket,
            task_keys,
            self._visibility_timeout,
        )


async def schedule_task_run_delivery(
    task_run: schemas.core.TaskRun,
    *,
    when: datetime | None = None,
) -> None:
    """Schedule a deferred task run for delivery through Docket."""
    await TaskRunDeliveryManager.active().schedule(task_run, when=when)


async def deliver_task_run(
    task_run: schemas.core.TaskRun,
    visibility_timeout_seconds: float,
    perpetual: Perpetual = Perpetual(),
    docket: Docket = CurrentDocket(),
) -> None:
    """Offer a task run until a TaskWorker acknowledges it."""
    visibility_timeout = timedelta(seconds=visibility_timeout_seconds)
    delivery_id = _delivery_key(task_run)
    queued = _queued_key(docket, delivery_id)
    acked = _acked_key(docket, delivery_id)

    async with docket.redis() as redis:
        if await redis.exists(acked):
            await redis.delete(queued)
            perpetual.cancel()
            return

        newly_ready = await redis.set(
            queued,
            _READY,
            nx=True,
            ex=visibility_timeout * 2,
        )

        if newly_ready:
            await redis.rpush(
                _queue_key(docket, task_run.task_key),
                orjson.dumps(
                    {
                        "delivery_id": delivery_id,
                        "task_run": task_run.model_dump(mode="json"),
                    }
                ),
            )
        else:
            delivery_status = await redis.get(queued)
            if delivery_status is not None and _decode(delivery_status) == _READY:
                # Keep the marker alive while the delivery remains in the ready list.
                # A subscriber changes it to a visibility-limited claim after BRPOP.
                await redis.expire(queued, visibility_timeout * 2)

    perpetual.after(visibility_timeout)


@asynccontextmanager
async def task_run_delivery_lifespan(
    docket: Docket,
    *,
    visibility_timeout: timedelta,
) -> AsyncGenerator[TaskRunDeliveryManager, None]:
    """Configure deferred task delivery for an API process."""
    manager = TaskRunDeliveryManager(docket, visibility_timeout)
    if TaskRunDeliveryManager._active is not None:
        raise RuntimeError("Task delivery is already running")
    TaskRunDeliveryManager._active = manager
    try:
        yield manager
    finally:
        if TaskRunDeliveryManager._active is manager:
            TaskRunDeliveryManager._active = None


def _queue_key(docket: Docket, task_key: str) -> str:
    route = hashlib.blake2b(task_key.encode(), digest_size=16).hexdigest()
    return docket.key(f"task-runs:ready:{route}")


def _delivery_key(task_run: schemas.core.TaskRun) -> str:
    state_id = task_run.state_id
    if state_id is None and task_run.state is not None:
        state_id = task_run.state.id
    return f"task-run:{task_run.id}:{state_id}"


def _delivery_marker_key(docket: Docket, delivery_id: str, marker: str) -> str:
    delivery = hashlib.blake2b(delivery_id.encode(), digest_size=16).hexdigest()
    return docket.key(f"task-runs:{delivery}:{marker}")


def _queued_key(docket: Docket, delivery_id: str) -> str:
    return _delivery_marker_key(docket, delivery_id, "queued")


def _acked_key(docket: Docket, delivery_id: str) -> str:
    return _delivery_marker_key(docket, delivery_id, "acked")


def _delivery_ttl(visibility_timeout: timedelta) -> int:
    return max(3600, int(visibility_timeout.total_seconds() * 10))


def _decode(value: bytes | str) -> str:
    return value.decode() if isinstance(value, bytes) else value
