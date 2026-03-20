"""
Redis-backed task queue for delivering background task runs to TaskWorkers.

Drop-in replacement for prefect.server.task_queue when running multiple
Prefect server replicas. Activated by setting:
    PREFECT_TASK_SCHEDULING_BACKEND=prefect_redis.task_queue
"""

import asyncio
from typing import Dict, List, Optional, Tuple

from typing_extensions import Self

import prefect.server.schemas as schemas
from prefect.logging import get_logger
from prefect.settings import (
    PREFECT_TASK_SCHEDULING_MAX_RETRY_QUEUE_SIZE,
    PREFECT_TASK_SCHEDULING_MAX_SCHEDULED_QUEUE_SIZE,
)
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


class TaskQueue:
    _task_queues: Dict[str, Self] = {}

    default_scheduled_max_size: int = (
        PREFECT_TASK_SCHEDULING_MAX_SCHEDULED_QUEUE_SIZE.value()
    )
    default_retry_max_size: int = PREFECT_TASK_SCHEDULING_MAX_RETRY_QUEUE_SIZE.value()

    _queue_size_configs: Dict[str, Tuple[int, int]] = {}
    _conditional_lpush = None

    task_key: str
    _scheduled_key: str
    _retry_key: str
    _max_scheduled: int
    _max_retry: int

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
                task_key,
                (cls.default_scheduled_max_size, cls.default_retry_max_size),
            )
            cls._task_queues[task_key] = cls(task_key, *sizes)
        return cls._task_queues[task_key]

    @classmethod
    def _get_conditional_lpush(cls, redis):
        if cls._conditional_lpush is None:
            cls._conditional_lpush = redis.register_script(_CONDITIONAL_LPUSH_SCRIPT)
        return cls._conditional_lpush

    @classmethod
    def reset(cls) -> None:
        """A unit testing utility to reset the state of the task queues subsystem."""
        cls._task_queues.clear()
        cls._conditional_lpush = None

    def __init__(
        self, task_key: str, scheduled_queue_size: int, retry_queue_size: int
    ):
        self.task_key = task_key
        self._scheduled_key = f"{KEY_PREFIX}:{task_key}:scheduled"
        self._retry_key = f"{KEY_PREFIX}:{task_key}:retry"
        self._max_scheduled = scheduled_queue_size
        self._max_retry = retry_queue_size

    def _redis(self):
        return get_async_redis_client(decode_responses=False)

    async def get(self) -> schemas.core.TaskRun:
        """Block until a task run is available, checking retries first."""
        redis = self._redis()
        while True:
            # Priority: retry queue first
            data = await redis.rpop(self._retry_key)
            if data:
                return schemas.core.TaskRun.model_validate_json(data)

            # BRPOP on scheduled queue with 1s timeout, then loop back to
            # check retries again
            result = await redis.brpop(self._scheduled_key, timeout=1)
            if result:
                _, data = result
                return schemas.core.TaskRun.model_validate_json(data)

    def get_nowait(self) -> schemas.core.TaskRun:
        raise asyncio.QueueEmpty(
            "get_nowait is not supported by the Redis task queue backend"
        )

    async def put(self, task_run: schemas.core.TaskRun) -> None:
        """LPUSH onto the scheduled list with atomic backpressure."""
        redis = self._redis()
        script = self._get_conditional_lpush(redis)
        data = task_run.model_dump_json()
        while True:
            result = await script(keys=[self._scheduled_key], args=[data, self._max_scheduled])
            if result != -1:
                return
            await asyncio.sleep(0.1)

    async def retry(self, task_run: schemas.core.TaskRun) -> None:
        """LPUSH onto the retry list with atomic backpressure."""
        redis = self._redis()
        script = self._get_conditional_lpush(redis)
        data = task_run.model_dump_json()
        while True:
            result = await script(keys=[self._retry_key], args=[data, self._max_retry])
            if result != -1:
                return
            await asyncio.sleep(0.1)


class MultiQueue:
    """A queue that can pull tasks from any of a number of Redis-backed task queues."""

    _queues: List[TaskQueue]

    def __init__(self, task_keys: List[str]):
        self._queues = [TaskQueue.for_key(task_key) for task_key in task_keys]

    async def get(self) -> schemas.core.TaskRun:
        """Gets the next task_run from any of the given queues.

        Checks all retry keys first (RPOP), then does a BRPOP across all
        scheduled keys with a 1s timeout. Raises asyncio.TimeoutError if
        nothing is available (matches the asyncio.wait_for pattern in
        task_runs.py).
        """
        redis = self._queues[0]._redis() if self._queues else get_async_redis_client(decode_responses=False)

        # Check all retry queues first
        for queue in self._queues:
            data = await redis.rpop(queue._retry_key)
            if data:
                return schemas.core.TaskRun.model_validate_json(data)

        # BRPOP across all scheduled keys with 1s timeout
        scheduled_keys = [q._scheduled_key for q in self._queues]
        if scheduled_keys:
            result = await redis.brpop(scheduled_keys, timeout=1)
            if result:
                _, data = result
                return schemas.core.TaskRun.model_validate_json(data)

        raise asyncio.TimeoutError
