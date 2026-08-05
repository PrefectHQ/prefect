"""In-memory delivery for Prefect background tasks."""

import asyncio
from types import TracebackType
from typing import ClassVar, Self

from prefect.server.schemas.core import TaskRun
from prefect.server.task_queue import TaskQueueDelivery, TaskQueuePriority
from prefect.settings import (
    PREFECT_TASK_SCHEDULING_MAX_RETRY_QUEUE_SIZE,
    PREFECT_TASK_SCHEDULING_MAX_SCHEDULED_QUEUE_SIZE,
)


class TaskQueue:
    _task_queues: ClassVar[dict[str, Self]] = {}

    default_scheduled_max_size: int = (
        PREFECT_TASK_SCHEDULING_MAX_SCHEDULED_QUEUE_SIZE.value()
    )
    default_retry_max_size: int = PREFECT_TASK_SCHEDULING_MAX_RETRY_QUEUE_SIZE.value()

    _queue_size_configs: ClassVar[dict[str, tuple[int, int]]] = {}

    @classmethod
    async def enqueue(cls, task_run: TaskRun) -> None:
        await cls.for_key(task_run.task_key).put(task_run)

    @classmethod
    def configure_task_key(
        cls,
        task_key: str,
        scheduled_size: int | None = None,
        retry_size: int | None = None,
    ) -> None:
        scheduled_size = scheduled_size or cls.default_scheduled_max_size
        retry_size = retry_size or cls.default_retry_max_size
        cls._queue_size_configs[task_key] = (scheduled_size, retry_size)

    @classmethod
    def for_key(cls, task_key: str) -> Self:
        if task_key not in cls._task_queues:
            sizes = cls._queue_size_configs.get(
                task_key,
                (cls.default_scheduled_max_size, cls.default_retry_max_size),
            )
            cls._task_queues[task_key] = cls(task_key, *sizes)
        return cls._task_queues[task_key]

    @classmethod
    def reset(cls) -> None:
        """Reset the process-local queues. Intended for tests."""
        cls._task_queues.clear()

    def __init__(
        self, task_key: str, scheduled_queue_size: int, retry_queue_size: int
    ) -> None:
        self.task_key = task_key
        self._scheduled_queue: asyncio.Queue[TaskRun] = asyncio.Queue(
            maxsize=scheduled_queue_size
        )
        self._retry_queue: asyncio.Queue[TaskRun] = asyncio.Queue(
            maxsize=retry_queue_size
        )

    async def get(self) -> TaskRun:
        try:
            return self._retry_queue.get_nowait()
        except asyncio.QueueEmpty:
            return await self._scheduled_queue.get()

    def get_nowait(self) -> TaskRun:
        try:
            return self._retry_queue.get_nowait()
        except asyncio.QueueEmpty:
            return self._scheduled_queue.get_nowait()

    async def put(self, task_run: TaskRun) -> None:
        await self._scheduled_queue.put(task_run)

    async def retry(self, task_run: TaskRun) -> None:
        await self._retry_queue.put(task_run)


class MultiQueue:
    """A queue that pulls task runs from any of a set of task queues."""

    def __init__(self, task_keys: list[str]) -> None:
        self._queues = [TaskQueue.for_key(task_key) for task_key in task_keys]

    async def get(self) -> TaskRun:
        while True:
            for queue in self._queues:
                try:
                    return queue.get_nowait()
                except asyncio.QueueEmpty:
                    continue
            await asyncio.sleep(0.01)


class Publisher:
    async def publish(
        self,
        task_run: TaskRun,
        priority: TaskQueuePriority = TaskQueuePriority.SCHEDULED,
    ) -> None:
        queue = TaskQueue.for_key(task_run.task_key)
        if priority is TaskQueuePriority.RETRY:
            await queue.retry(task_run)
        else:
            await queue.put(task_run)


class Consumer:
    def __init__(self, task_keys: list[str], consumer_id: str) -> None:
        self._queue = MultiQueue(task_keys)
        self._publisher = Publisher()
        self._outstanding: dict[int, TaskQueueDelivery] = {}

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await asyncio.gather(
            *(self.release(delivery) for delivery in list(self._outstanding.values()))
        )

    async def get(self) -> TaskQueueDelivery:
        delivery = TaskQueueDelivery(task_run=await self._queue.get())
        self._outstanding[id(delivery)] = delivery
        return delivery

    async def acknowledge(self, delivery: TaskQueueDelivery) -> None:
        self._outstanding.pop(id(delivery), None)

    async def release(self, delivery: TaskQueueDelivery) -> None:
        await self._publisher.publish(delivery.task_run, TaskQueuePriority.RETRY)
        self._outstanding.pop(id(delivery), None)
