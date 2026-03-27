"""
Redis-backed task queue for delivering background task runs to TaskWorkers.

Drop-in replacement for prefect.server.task_queue.memory when running multiple
Prefect server replicas. Activated by setting:
    PREFECT_TASK_SCHEDULING_BACKEND=prefect_redis.task_queue

Uses an ack emulation pattern (similar to Celery/Kombu's QoS class)
for in-flight tracking. After BRPOP, task runs are written to an inflight hash.
On successful delivery (ack), they are removed. Stale entries are periodically
restored to the retry queue by a single replica using non-blocking redis lock.
"""

import asyncio
import json
import time

from redis.asyncio import Redis

import prefect.server.schemas as schemas
from prefect.logging import get_logger
from prefect.server.task_queue import prioritize_keys
from prefect.settings import get_current_settings
from prefect_redis.client import get_async_redis_client

logger = get_logger(__name__)

KEY_PREFIX = "prefect:tq"
INFLIGHT_KEY = f"{KEY_PREFIX}:inflight"
RESTORE_LOCK_KEY = f"{KEY_PREFIX}:restore_lock"


class TaskQueueBackend:
    """Redis-backed implementation of the TaskQueueBackend protocol."""

    _instance: "TaskQueueBackend | None" = None
    _initialized: bool = False

    def __new__(cls, *args: object, **kwargs: object) -> "TaskQueueBackend":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        visibility_timeout: int | None = None,
    ) -> None:
        if self.__class__._initialized:
            return
        settings = get_current_settings().server.tasks.scheduling
        self._visibility_timeout: int = (
            visibility_timeout
            if visibility_timeout is not None
            else settings.inflight_visibility_timeout
        )
        self._redis: Redis = get_async_redis_client(decode_responses=False)
        self._offset: int = 0
        self.__class__._initialized = True

    def _scheduled_key(self, task_key: str) -> str:
        return f"{KEY_PREFIX}:{task_key}:scheduled"

    def _retry_key(self, task_key: str) -> str:
        return f"{KEY_PREFIX}:{task_key}:retry"

    async def _restore_stale_inflight(self) -> None:
        """Re-enqueue in-flight task runs that have exceeded the visibility timeout.

        Uses a non-blocking distributed lock so only one replica sweeps at a
        time. If the lock is held, this call is a no-op.
        """
        lock = self._redis.lock(
            RESTORE_LOCK_KEY,
            timeout=self._visibility_timeout,
        )
        if not await lock.acquire(blocking=False):
            return

        try:
            entries = await self._redis.hgetall(INFLIGHT_KEY)
            now = time.time()
            for task_run_id, raw in entries.items():
                entry = json.loads(raw)
                if now - entry["ts"] > self._visibility_timeout:
                    task_run = schemas.core.TaskRun.model_validate_json(entry["data"])
                    await self.retry(task_run)
                    await self._redis.hdel(INFLIGHT_KEY, task_run_id)
                    logger.info(f"Restored stale in-flight task run {task_run_id!r}")
        finally:
            await lock.release()

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

    async def ack(self, task_run: schemas.core.TaskRun) -> None:
        """Remove a task run from the inflight hash after successful delivery."""
        await self._redis.hdel(INFLIGHT_KEY, str(task_run.id))

    async def dequeue_from_keys(
        self,
        keys: list[str],
        timeout: float = 1,
    ) -> schemas.core.TaskRun:
        await self._restore_stale_inflight()

        ordered = prioritize_keys(keys, self._offset)

        all_redis_keys: list[str] = []
        for key in ordered:
            all_redis_keys.append(self._retry_key(key))
            all_redis_keys.append(self._scheduled_key(key))

        result = await self._redis.brpop(all_redis_keys, timeout=timeout)
        if result is None:
            raise asyncio.TimeoutError
        _, data = result

        task_run = schemas.core.TaskRun.model_validate_json(data)
        self._offset += 1
        await self._redis.hset(
            INFLIGHT_KEY,
            str(task_run.id),
            json.dumps({"data": data.decode(), "ts": time.time()}),
        )

        return task_run
