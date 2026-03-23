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
from prefect.server.task_queue import TaskQueueBackend as _TaskQueueBackend
from prefect.settings import get_current_settings
from prefect_redis.client import get_async_redis_client

logger = get_logger(__name__)

KEY_PREFIX = "prefect:tq"

# Lua: atomically LPUSH only if list length < max_size. Returns new length or -1.
_CONDITIONAL_LPUSH_SCRIPT = """
if redis.call('LLEN', KEYS[1]) < tonumber(ARGV[2]) then
    return redis.call('LPUSH', KEYS[1], ARGV[1])
else
    return -1
end
"""


class TaskQueueBackend(_TaskQueueBackend):
    """Redis-backed implementation of the TaskQueueBackend protocol.

    Singleton — __new__ returns the same instance on every call, so all
    callers of get_task_queue_backend() share configuration state. Matches
    the ConcurrencyLeaseStorage singleton pattern.
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
        self._conditional_lpush = None
        self._redis: Redis = get_async_redis_client(decode_responses=False)
        self.__class__._initialized = True

    def _scheduled_key(self, task_key: str) -> str:
        return f"{KEY_PREFIX}:{task_key}:scheduled"

    def _retry_key(self, task_key: str) -> str:
        return f"{KEY_PREFIX}:{task_key}:retry"

    def _get_conditional_lpush(self):
        if self._conditional_lpush is None:
            self._conditional_lpush = self._redis.register_script(
                _CONDITIONAL_LPUSH_SCRIPT
            )
        return self._conditional_lpush

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
        """Clear all configuration state and flush Redis queue data. Test utility."""
        self._conditional_lpush = None
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
        """LPUSH onto the scheduled list with atomic backpressure."""
        script = self._get_conditional_lpush()
        data = task_run.model_dump_json()
        while True:
            result = await script(
                keys=[self._scheduled_key(task_run.task_key)],
                args=[data, self._max_scheduled],
            )
            if result != -1:
                return
            await asyncio.sleep(0.1)

    async def retry(self, task_run: schemas.core.TaskRun) -> None:
        """LPUSH onto the retry list with atomic backpressure."""
        script = self._get_conditional_lpush()
        data = task_run.model_dump_json()
        while True:
            result = await script(
                keys=[self._retry_key(task_run.task_key)],
                args=[data, self._max_retry],
            )
            if result != -1:
                return
            await asyncio.sleep(0.1)

    async def get(self, key: str) -> schemas.core.TaskRun:
        """Block until a task run is available. Retry queue has priority."""
        _, data = await self._redis.brpop(
            self._retry_key(key), self._scheduled_key(key)
        )
        return schemas.core.TaskRun.model_validate_json(data)

    async def get_many(
        self,
        keys: list[str],
        timeout: float = 1,
        offset: int = 0,
    ) -> schemas.core.TaskRun:
        ordered = self.prioritize_keys(keys, offset)

        # BRPOP returns immediately if data exists, no need for separate RPOP pass.
        # Interleave retry+scheduled per key so retries have priority within each key.
        all_keys: list[str] = []
        for key in ordered:
            all_keys.append(self._retry_key(key))
            all_keys.append(self._scheduled_key(key))

        if not all_keys:
            raise asyncio.TimeoutError

        result = await self._redis.brpop(all_keys, timeout=timeout)
        if result:
            _, data = result
            return schemas.core.TaskRun.model_validate_json(data)
        raise asyncio.TimeoutError

    @staticmethod
    def prioritize_keys(task_keys: list[str], offset: int) -> list[str]:
        n = len(task_keys)
        if n == 0:
            return task_keys
        i = offset % n
        return task_keys[i:] + task_keys[:i]
