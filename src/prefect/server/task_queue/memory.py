"""
In-memory task queue backend using asyncio.PriorityQueue.

Suitable for single-replica Prefect server deployments and testing.
"""

import asyncio
from dataclasses import dataclass, field
from enum import IntEnum
from itertools import count

import prefect.server.schemas as schemas
from prefect.logging import get_logger
from prefect.server.task_queue import DeliveredTaskRun
from prefect.settings import get_current_settings

logger = get_logger(__name__)


class _Priority(IntEnum):
    RETRY = 0
    SCHEDULED = 1


@dataclass
class _KeyQueue:
    """Per-key state: priority queue + semaphores for backpressure.

    A single PriorityQueue holds both scheduled and retry items so retries
    (lower _Priority value) are dequeued first.
    Separate semaphores enforce independent capacity limits for each type.
    """

    scheduled_sem: asyncio.Semaphore
    retry_sem: asyncio.Semaphore
    queue: asyncio.PriorityQueue = field(default_factory=asyncio.PriorityQueue)
    seq: count = field(default_factory=count)


class TaskQueueBackend:
    """In-memory implementation of the TaskQueueBackend protocol."""

    _instance: "TaskQueueBackend | None" = None
    _initialized: bool = False

    def __new__(cls, *args: object, **kwargs: object) -> "TaskQueueBackend":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        max_scheduled: int | None = None,
        max_retry: int | None = None,
    ) -> None:
        if self.__class__._initialized:
            return
        settings = get_current_settings().server.tasks.scheduling
        self._max_scheduled: int = (
            max_scheduled
            if max_scheduled is not None
            else settings.max_scheduled_queue_size
        )
        self._max_retry: int = (
            max_retry if max_retry is not None else settings.max_retry_queue_size
        )
        self._queues: dict[str, _KeyQueue] = {}
        self._condition: asyncio.Condition | None = None
        self._condition_loop: asyncio.AbstractEventLoop | None = None
        self.__class__._initialized = True

    def _get_condition(self) -> asyncio.Condition:
        """Return the shared Condition, creating it lazily on first use.

        Recreates the Condition if the event loop has changed (e.g., tests
        that create fresh event loops via TestClient).
        """
        loop = asyncio.get_running_loop()
        if self._condition is None or self._condition_loop is not loop:
            self._condition = asyncio.Condition()
            self._condition_loop = loop
        return self._condition

    def _get_or_create_queue(self, key: str) -> _KeyQueue:
        """Lazily create queue for a key."""
        if key not in self._queues:
            self._queues[key] = _KeyQueue(
                scheduled_sem=asyncio.Semaphore(self._max_scheduled),
                retry_sem=asyncio.Semaphore(self._max_retry),
            )
        return self._queues[key]

    async def reset(self) -> None:
        self._queues.clear()
        self._condition = None
        self.__class__._instance = None
        self.__class__._initialized = False

    async def enqueue(self, task_run: schemas.core.TaskRun) -> None:
        kq = self._get_or_create_queue(task_run.task_key)
        await kq.scheduled_sem.acquire()
        await kq.queue.put((_Priority.SCHEDULED, next(kq.seq), task_run))
        condition = self._get_condition()
        async with condition:
            # notify_all wakes all waiters across all keys; with per-key
            # dequeue loops only one will find an item. Acceptable trade-off
            # for simplicity vs per-key Conditions.
            condition.notify_all()

    async def retry(self, task_run: schemas.core.TaskRun) -> None:
        kq = self._get_or_create_queue(task_run.task_key)
        try:
            await asyncio.wait_for(kq.retry_sem.acquire(), timeout=5)
        except asyncio.TimeoutError:
            logger.warning(
                "Retry queue full for key %s, dropping retry for task %s",
                task_run.task_key,
                task_run.id,
            )
            return
        await kq.queue.put((_Priority.RETRY, next(kq.seq), task_run))
        condition = self._get_condition()
        async with condition:
            condition.notify_all()

    async def ack(self, delivered: DeliveredTaskRun) -> None:
        pass

    async def dequeue(
        self,
        key: str,
        timeout: float = 1,
    ) -> DeliveredTaskRun:
        condition = self._get_condition()

        async def _wait_for_item() -> DeliveredTaskRun:
            kq = self._get_or_create_queue(key)
            async with condition:
                while True:
                    try:
                        priority, _, task_run = kq.queue.get_nowait()
                        (
                            kq.retry_sem
                            if priority == _Priority.RETRY
                            else kq.scheduled_sem
                        ).release()
                        return DeliveredTaskRun(task_run=task_run)
                    except asyncio.QueueEmpty:
                        await condition.wait()

        return await asyncio.wait_for(_wait_for_item(), timeout=timeout)
