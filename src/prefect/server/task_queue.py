"""
Implements an in-memory task queue for delivering background task runs to TaskWorkers.
"""

import asyncio
from typing import Dict, List, Optional, Tuple

from typing_extensions import Self

import prefect.server.schemas as schemas
from prefect.settings import (
    PREFECT_TASK_SCHEDULING_MAX_RETRY_QUEUE_SIZE,
    PREFECT_TASK_SCHEDULING_MAX_SCHEDULED_QUEUE_SIZE,
)


class TaskQueue:
    _task_queues: Dict[str, Self] = {}

    default_scheduled_max_size: int = (
        PREFECT_TASK_SCHEDULING_MAX_SCHEDULED_QUEUE_SIZE.value()
    )
    default_retry_max_size: int = PREFECT_TASK_SCHEDULING_MAX_RETRY_QUEUE_SIZE.value()

    _queue_size_configs: Dict[str, Tuple[int, int]] = {}

    task_key: str
    _scheduled_queue: asyncio.Queue
    _retry_queue: asyncio.Queue

    @classmethod
    async def enqueue(cls, task_run: schemas.core.TaskRun) -> None:
        await cls.for_key(task_run.task_key).put(task_run)

    @classmethod
    def configure_task_key(
        cls,
        task_key: str,
        scheduled_size: Optional[int] = None,
        retry_size: Optional[int] = None,
    ) -> None:
        scheduled_size = scheduled_size or cls.default_scheduled_max_size
        retry_size = retry_size or cls.default_retry_max_size
        cls._queue_size_configs[task_key] = (scheduled_size, retry_size)

    @classmethod
    def for_key(cls, task_key: str) -> Self:
        if task_key not in cls._task_queues:
            sizes = cls._queue_size_configs.get(
                task_key, (cls.default_scheduled_max_size, cls.default_retry_max_size)
            )
            cls._task_queues[task_key] = cls(task_key, *sizes)
        return cls._task_queues[task_key]

    @classmethod
    def reset(cls) -> None:
        """A unit testing utility to reset the state of the task queues subsystem"""
        cls._task_queues.clear()
        cls._scheduled_tasks_already_restored = False

    def __init__(self, task_key: str, scheduled_queue_size: int, retry_queue_size: int):
        self.task_key = task_key
        self._scheduled_queue = asyncio.Queue(maxsize=scheduled_queue_size)
        self._retry_queue = asyncio.Queue(maxsize=retry_queue_size)

    async def get(self) -> schemas.core.TaskRun:
        # First, check if there's anything in the retry queue
        try:
            return self._retry_queue.get_nowait()
        except asyncio.QueueEmpty:
            return await self._scheduled_queue.get()

    def get_nowait(self) -> schemas.core.TaskRun:
        # First, check if there's anything in the retry queue
        try:
            return self._retry_queue.get_nowait()
        except asyncio.QueueEmpty:
            return self._scheduled_queue.get_nowait()

    async def put(self, task_run: schemas.core.TaskRun) -> None:
        await self._scheduled_queue.put(task_run)

    async def retry(self, task_run: schemas.core.TaskRun) -> None:
        await self._retry_queue.put(task_run)


class MultiQueue:
    """A queue that can pull tasks from from any of a number of task queues"""

    _queues: List[TaskQueue]

    def __init__(self, task_keys: List[str]):
        self._queues = [TaskQueue.for_key(task_key) for task_key in task_keys]

    async def get(self) -> schemas.core.TaskRun:
        """Gets the next task_run from any of the given queues"""
        while True:
            for queue in self._queues:
                try:
                    return queue.get_nowait()
                except asyncio.QueueEmpty:
                    continue
            await asyncio.sleep(0.01)
