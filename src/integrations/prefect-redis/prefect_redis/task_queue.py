"""
Redis-backed task queue for delivering background task runs to TaskWorkers.

Drop-in replacement for prefect.server.task_queue.memory when running multiple
Prefect server replicas. Activated by setting:
    PREFECT_TASK_SCHEDULING_BACKEND=prefect_redis.task_queue
"""

import asyncio

from redis.asyncio import Redis

import prefect.server.schemas as schemas
from prefect.logging import get_logger
from prefect.server.task_queue import prioritize_keys
from prefect_redis.client import get_async_redis_client

logger = get_logger(__name__)

KEY_PREFIX = "prefect:tq"


class TaskQueueBackend:
    """Redis-backed implementation of the TaskQueueBackend protocol."""

    _instance: "TaskQueueBackend | None" = None
    _initialized: bool = False

    def __new__(cls, *args: object, **kwargs: object) -> "TaskQueueBackend":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self.__class__._initialized:
            return
        self._redis: Redis = get_async_redis_client(decode_responses=False)
        self._offset: int = 0
        self.__class__._initialized = True

    def _scheduled_key(self, task_key: str) -> str:
        return f"{KEY_PREFIX}:{task_key}:scheduled"

    def _retry_key(self, task_key: str) -> str:
        return f"{KEY_PREFIX}:{task_key}:retry"

    async def reset(self) -> None:
        """Clear Redis queue data and singleton cache. Test utility."""
        self.__class__._instance = None
        self.__class__._initialized = False
        cursor = 0
        while True:
            cursor, keys = await self._redis.scan(
                cursor, match=f"{KEY_PREFIX}:*", count=100
            )
            if keys:
                await self._redis.delete(*keys)
            if cursor == 0:
                break

    async def enqueue(self, task_run: schemas.core.TaskRun) -> None:
        """LPUSH onto the scheduled list."""
        await self._redis.lpush(
            self._scheduled_key(task_run.task_key),
            task_run.model_dump_json(),
        )

    async def retry(self, task_run: schemas.core.TaskRun) -> None:
        """LPUSH onto the retry list."""
        await self._redis.lpush(
            self._retry_key(task_run.task_key),
            task_run.model_dump_json(),
        )

    async def dequeue_from_keys(
        self,
        keys: list[str],
        timeout: float = 1,
    ) -> schemas.core.TaskRun:
        if not keys:
            raise asyncio.TimeoutError

        ordered = prioritize_keys(keys, self._offset)

        all_redis_keys: list[str] = []
        for key in ordered:
            all_redis_keys.append(self._retry_key(key))
            all_redis_keys.append(self._scheduled_key(key))

        result = await self._redis.brpop(all_redis_keys, timeout=timeout)
        if result is None:
            raise asyncio.TimeoutError
        _, data = result
        self._offset += 1
        return schemas.core.TaskRun.model_validate_json(data)
