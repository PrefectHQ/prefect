"""Durable delivery of deferred task runs to TaskWorkers."""

from __future__ import annotations

import hashlib
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, AsyncGenerator, ClassVar

import orjson

import prefect.server.schemas as schemas
from prefect.settings import get_current_settings

if TYPE_CHECKING:
    from docket import Docket, Queue, QueueMessage

_DELIVERY_QUEUE_NAME = "prefect-task-runs"
_DELIVERY_GROUP = "prefect-task-workers"


class _TaskDeliveryUnavailable(RuntimeError):
    """Raised when task delivery has not been configured."""


@dataclass(frozen=True)
class _TaskRunDelivery:
    """A deferred task run claimed from Docket for a TaskWorker."""

    task_run: schemas.core.TaskRun
    message: QueueMessage


class _TaskRunSubscription:
    """A TaskWorker subscription to one or more task-key topics."""

    def __init__(
        self,
        queue: Queue,
        task_keys: list[str],
        visibility_timeout: timedelta,
        max_retry_size: int,
    ) -> None:
        priorities = {
            _topic(task_key, kind): 0 if kind == "retry" else 1
            for task_key in task_keys
            for kind in ("retry", "scheduled")
        }
        self._subscription = queue.subscribe(
            priorities,
            visibility_timeout=visibility_timeout,
            group=_DELIVERY_GROUP,
        )
        self._max_retry_size = max_retry_size
        self._outstanding: dict[str, _TaskRunDelivery] = {}

    async def __aenter__(self) -> "_TaskRunSubscription":
        await self._subscription.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        try:
            for delivery in list(self._outstanding.values()):
                await delivery.message.release(
                    _topic(delivery.task_run.task_key, "retry"),
                    max_size=self._max_retry_size,
                )
                self._outstanding.pop(delivery.message.key, None)
        finally:
            await self._subscription.__aexit__(exc_type, exc, traceback)

    async def receive(self, timeout: float = 1) -> _TaskRunDelivery:
        """Receive a task run matching this subscription."""
        message = await self._subscription.receive(timeout=timeout)
        delivery = _TaskRunDelivery(
            task_run=schemas.core.TaskRun.model_validate(orjson.loads(message.data)),
            message=message,
        )
        self._outstanding[message.key] = delivery
        return delivery

    async def acknowledge(self, delivery: _TaskRunDelivery) -> None:
        """Acknowledge a task run accepted by the connected TaskWorker."""
        await delivery.message.acknowledge()
        self._outstanding.pop(delivery.message.key, None)


class _TaskRunDeliveryManager:
    """Publish deferred task runs and create TaskWorker subscriptions."""

    _active: ClassVar["_TaskRunDeliveryManager | None"] = None

    def __init__(
        self,
        docket: Docket,
        visibility_timeout: timedelta,
        max_scheduled_size: int | None = None,
        max_retry_size: int | None = None,
    ) -> None:
        scheduling = get_current_settings().server.tasks.scheduling
        self._visibility_timeout = visibility_timeout
        self._max_scheduled_size = (
            max_scheduled_size
            if max_scheduled_size is not None
            else scheduling.max_scheduled_queue_size
        )
        self._max_retry_size = (
            max_retry_size
            if max_retry_size is not None
            else scheduling.max_retry_queue_size
        )
        self._queue = docket.queue(_DELIVERY_QUEUE_NAME)

    @classmethod
    def active(cls) -> "_TaskRunDeliveryManager":
        if cls._active is None:
            raise _TaskDeliveryUnavailable("Task delivery is not running")
        return cls._active

    async def schedule(self, task_run: schemas.core.TaskRun) -> bool:
        """Publish one deferred task-run state for keyed delivery."""
        kind = _delivery_kind(task_run)
        max_size = self._max_retry_size if kind == "retry" else self._max_scheduled_size
        return await self._queue.put(
            _topic(task_run.task_key, kind),
            orjson.dumps(task_run.model_dump(mode="json")),
            key=_delivery_key(task_run),
            max_size=max_size,
        )

    def subscribe(self, task_keys: list[str]) -> _TaskRunSubscription:
        return _TaskRunSubscription(
            self._queue,
            task_keys,
            self._visibility_timeout,
            self._max_retry_size,
        )


async def schedule_task_run_delivery(task_run: schemas.core.TaskRun) -> None:
    """Schedule a deferred task run for delivery through Docket."""
    await _TaskRunDeliveryManager.active().schedule(task_run)


def _task_run_delivery_subscription(task_keys: list[str]) -> _TaskRunSubscription:
    """Subscribe to deferred task runs matching one or more task keys."""
    return _TaskRunDeliveryManager.active().subscribe(task_keys)


@asynccontextmanager
async def task_run_delivery_lifespan(
    docket: Docket,
    *,
    visibility_timeout: timedelta,
) -> AsyncGenerator[None, None]:
    """Configure deferred task delivery for an API process."""
    manager = _TaskRunDeliveryManager(docket, visibility_timeout)
    if _TaskRunDeliveryManager._active is not None:
        raise RuntimeError("Task delivery is already running")
    _TaskRunDeliveryManager._active = manager
    try:
        yield
    finally:
        if _TaskRunDeliveryManager._active is manager:
            _TaskRunDeliveryManager._active = None


def _topic(task_key: str, kind: str) -> str:
    route = hashlib.blake2b(task_key.encode(), digest_size=16).hexdigest()
    return f"{route}:{kind}"


def _delivery_kind(task_run: schemas.core.TaskRun) -> str:
    return (
        "retry"
        if task_run.state is not None and task_run.state.name == "AwaitingRetry"
        else "scheduled"
    )


def _delivery_key(task_run: schemas.core.TaskRun) -> str:
    state_id = task_run.state_id
    if state_id is None and task_run.state is not None:
        state_id = task_run.state.id
    return f"task-run:{task_run.id}:{state_id}"
