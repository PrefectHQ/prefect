"""
In-memory task queue backend using asyncio.Queue.

Suitable for single-replica Prefect server deployments and testing.
"""

import asyncio

import prefect.server.schemas as schemas
from prefect.server.task_queue import TaskQueueBackend as _TaskQueueBackend
from prefect.settings import get_current_settings


class TaskQueueBackend(_TaskQueueBackend):
    """In-memory implementation of the TaskQueueBackend protocol.

    Singleton — __new__ returns the same instance on every call, so all
    callers of get_task_queue_backend() share the same queues. Matches the
    ConcurrencyLeaseStorage singleton pattern.
    """

    _instance: "TaskQueueBackend | None" = None
    _initialized: bool = False

    def __new__(cls) -> "TaskQueueBackend":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self.__class__._initialized:
            return
        settings = get_current_settings().server.tasks.scheduling
        self._max_scheduled: int = settings.max_scheduled_queue_size
        self._max_retry: int = settings.max_retry_queue_size
        self._queues: dict[str, tuple[asyncio.Queue, asyncio.Queue]] = {}
        self.__class__._initialized = True

    def _get_or_create_queues(self, key: str) -> tuple[asyncio.Queue, asyncio.Queue]:
        """Lazily create queue pair for a key."""
        if key not in self._queues:
            self._queues[key] = (
                asyncio.Queue(maxsize=self._max_scheduled),
                asyncio.Queue(maxsize=self._max_retry),
            )
        return self._queues[key]

    def configure(
        self,
        scheduled_size: int | None = None,
        retry_size: int | None = None,
    ) -> None:
        """Set global queue size limits. Defaults come from settings."""
        settings = get_current_settings().server.tasks.scheduling
        self._max_scheduled = (
            scheduled_size
            if scheduled_size is not None
            else settings.max_scheduled_queue_size
        )
        self._max_retry = (
            retry_size if retry_size is not None else settings.max_retry_queue_size
        )

    async def reset(self) -> None:
        self._queues.clear()
        self.__class__._instance = None
        self.__class__._initialized = False

    async def enqueue(self, task_run: schemas.core.TaskRun) -> None:
        scheduled, _ = self._get_or_create_queues(task_run.task_key)
        await scheduled.put(task_run)

    async def retry(self, task_run: schemas.core.TaskRun) -> None:
        _, retry_q = self._get_or_create_queues(task_run.task_key)
        await retry_q.put(task_run)

    async def get(self, key: str) -> schemas.core.TaskRun:
        """Block until a task run is available. Retry queue has priority."""
        scheduled, retry_q = self._get_or_create_queues(key)
        while True:
            try:
                return retry_q.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                return scheduled.get_nowait()
            except asyncio.QueueEmpty:
                pass
            await asyncio.sleep(0.01)

    async def get_many(
        self,
        keys: list[str],
        timeout: float = 1,
        offset: int = 0,
    ) -> schemas.core.TaskRun:
        ordered = self.prioritize_keys(keys, offset)
        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            for key in ordered:
                scheduled, retry_q = self._get_or_create_queues(key)
                try:
                    return retry_q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    return scheduled.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            if asyncio.get_running_loop().time() >= deadline:
                raise asyncio.TimeoutError
            await asyncio.sleep(0.01)

    @staticmethod
    def prioritize_keys(task_keys: list[str], offset: int) -> list[str]:
        n = len(task_keys)
        if n == 0:
            return task_keys
        i = offset % n
        return task_keys[i:] + task_keys[:i]
