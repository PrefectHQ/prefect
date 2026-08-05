"""Delivery primitives for standalone background task runs."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from enum import IntEnum
from functools import lru_cache
from types import TracebackType
from typing import Any, Protocol, Self, runtime_checkable

from prefect.server.schemas.core import TaskRun
from prefect.settings import PREFECT_MESSAGING_BROKER


class TaskQueuePriority(IntEnum):
    """The delivery priority for a background task run."""

    RETRY = 0
    SCHEDULED = 1


@dataclass(frozen=True)
class TaskQueueDelivery:
    """A task run reserved by a consumer for delivery to a TaskWorker."""

    task_run: TaskRun
    token: Any = None


class TaskQueuePublisher(Protocol):
    async def publish(
        self,
        task_run: TaskRun,
        priority: TaskQueuePriority = TaskQueuePriority.SCHEDULED,
    ) -> None: ...


class TaskQueueConsumer(Protocol):
    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None: ...

    async def get(self) -> TaskQueueDelivery: ...

    async def acknowledge(self, delivery: TaskQueueDelivery) -> None: ...

    async def release(self, delivery: TaskQueueDelivery) -> None: ...


@runtime_checkable
class TaskQueueModule(Protocol):
    Publisher: type[TaskQueuePublisher]
    Consumer: type[TaskQueueConsumer]


def _task_queue_module_path() -> str:
    messaging_module = PREFECT_MESSAGING_BROKER.value()
    if messaging_module == "prefect_redis.messaging":
        return "prefect_redis.task_queue"
    return "prefect.server.task_queue.memory"


@lru_cache
def _task_queue_module(module_path: str) -> TaskQueueModule:
    module = importlib.import_module(module_path)
    if not isinstance(module, TaskQueueModule):
        raise TypeError(
            f"Module {module_path!r} must export TaskQueue Publisher and Consumer "
            "classes."
        )
    return module


def create_task_queue_publisher() -> TaskQueuePublisher:
    """Create a publisher for the configured background task queue."""
    return _task_queue_module(_task_queue_module_path()).Publisher()


def create_task_queue_consumer(
    task_keys: list[str], consumer_id: str
) -> TaskQueueConsumer:
    """Create a consumer subscribed to a set of background task keys."""
    return _task_queue_module(_task_queue_module_path()).Consumer(
        task_keys, consumer_id
    )


# These process-local classes were historically public from this module.
from prefect.server.task_queue.memory import MultiQueue, TaskQueue
