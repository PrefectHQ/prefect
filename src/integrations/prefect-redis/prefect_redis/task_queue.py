"""
Redis Streams task queue for delivering background task runs to TaskWorkers.

Uses consumer groups (PEL) for atomic inflight tracking and XAUTOCLAIM for
crash recovery. At-least-once delivery — no gap between dequeue and inflight
tracking. Single stream per task key; PEL is the retry mechanism.

Activated by setting:
    PREFECT_TASK_SCHEDULING_BACKEND=prefect_redis.task_queue

Requires Redis/Valkey 6.2+ for XAUTOCLAIM.
"""

import asyncio
import functools
import time
from typing import Callable
from uuid import uuid4

from redis.asyncio import Redis
from redis.exceptions import RedisError, ResponseError

import prefect.server.schemas as schemas
from prefect.logging import get_logger
from prefect.server.task_queue import DeliveredTaskRun
from prefect.settings import get_current_settings
from prefect_redis.client import clear_cached_clients, get_async_redis_client

logger = get_logger(__name__)

KEY_PREFIX = "prefect:tqs"
GROUP_NAME = "task_workers"

_ACK_AND_DEL_SCRIPT = """
redis.call('XACK', KEYS[1], ARGV[1], ARGV[2])
redis.call('XDEL', KEYS[1], ARGV[2])
return 1
"""

_MOVE_TO_DLQ_SCRIPT = """
redis.call('XADD', KEYS[2], '*', unpack(ARGV, 3))
redis.call('XACK', KEYS[1], ARGV[1], ARGV[2])
redis.call('XDEL', KEYS[1], ARGV[2])
return 1
"""


def throttle(interval_getter: Callable):
    """Skip calls that happen within interval seconds of the last call."""

    def decorator(fn):
        attr = f"_throttle_last_{fn.__name__}"

        @functools.wraps(fn)
        async def wrapper(self, *args, **kwargs):
            now = time.time()
            if now - getattr(self, attr, 0.0) < interval_getter(self):
                return None
            setattr(self, attr, now)
            return await fn(self, *args, **kwargs)

        return wrapper

    return decorator


class TaskQueueBackend:
    """Redis Streams implementation of the TaskQueueBackend protocol."""

    _instance: "TaskQueueBackend | None" = None
    _initialized: bool = False

    def __new__(cls, *args: object, **kwargs: object) -> "TaskQueueBackend":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self.__class__._initialized:
            return
        settings = get_current_settings().server.tasks.scheduling
        self._visibility_timeout: int = settings.inflight_visibility_timeout
        self._max_retries: int = settings.stream_max_retries
        self._redis: Redis = get_async_redis_client(decode_responses=False)
        self._consumer: str = str(uuid4())
        self._initialized_groups: set[str] = set()
        self._consumer_cleanup_interval: int = settings.stream_consumer_cleanup_interval
        self._consumer_idle_threshold_ms: int = (
            settings.stream_consumer_idle_threshold * 1000
        )
        self._dequeue_block_ms: int = settings.dequeue_block_ms
        self._dequeue_semaphore: asyncio.Semaphore | None = (
            asyncio.Semaphore(settings.dequeue_max_concurrency)
            if settings.dequeue_max_concurrency is not None
            else None
        )
        self._ack_script = None
        self._dlq_script = None
        self.__class__._initialized = True

        logger.info(f"Stream task queue consumer: {self._consumer}")

    def _stream_key(self, task_key: str) -> str:
        return f"{KEY_PREFIX}:{task_key}"

    def _dlq_key(self, task_key: str) -> str:
        return f"{KEY_PREFIX}:{task_key}:dlq"

    def _get_ack_script(self):
        if self._ack_script is None:
            self._ack_script = self._redis.register_script(_ACK_AND_DEL_SCRIPT)
        return self._ack_script

    def _get_dlq_script(self):
        if self._dlq_script is None:
            self._dlq_script = self._redis.register_script(_MOVE_TO_DLQ_SCRIPT)
        return self._dlq_script

    async def _ensure_group(self, stream_key: str) -> None:
        if stream_key in self._initialized_groups:
            return
        try:
            await self._redis.xgroup_create(
                stream_key, GROUP_NAME, id="0", mkstream=True
            )
        except ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise
        self._initialized_groups.add(stream_key)

    async def _claim_one_stale_entry(self, key: str) -> DeliveredTaskRun | None:
        """Claim one stale PEL entry via XAUTOCLAIM.

        Skips orphans (deleted from stream, still in PEL) and entries that
        have exceeded max_retries (moved to DLQ). Uses the XAUTOCLAIM cursor
        to avoid rescanning already-processed entries.
        """
        stream_key = self._stream_key(key)
        min_idle_ms = self._visibility_timeout * 1000
        cursor: bytes | str = b"0-0"

        for _ in range(10):
            try:
                result = await self._redis.xautoclaim(
                    stream_key,
                    GROUP_NAME,
                    self._consumer,
                    min_idle_time=min_idle_ms,
                    start_id=cursor,
                    count=1,
                )
            except ResponseError:
                return None

            cursor, claimed, _ = result
            if not claimed:
                return None

            msg_id, fields = claimed[0]

            if fields is None:
                await self._redis.xack(stream_key, GROUP_NAME, msg_id)
                continue

            pending_info = await self._redis.xpending_range(
                stream_key,
                GROUP_NAME,
                min=msg_id,
                max=msg_id,
                count=1,
            )
            if pending_info:
                times_delivered = pending_info[0].get(
                    "times_delivered",
                    pending_info[0].get(b"times_delivered", 0),
                )
                if times_delivered >= self._max_retries:
                    if not fields:
                        await self._redis.xack(stream_key, GROUP_NAME, msg_id)
                    else:
                        dlq_key = self._dlq_key(key)
                        flat = [v for pair in fields.items() for v in pair]
                        await self._get_dlq_script()(
                            keys=[stream_key, dlq_key],
                            args=[GROUP_NAME, msg_id] + flat,
                        )
                        logger.warning(
                            "Task moved to DLQ after %d delivery attempts: %s",
                            times_delivered,
                            msg_id,
                        )
                    continue

            return self._parse_stream_result(stream_key, msg_id, fields)

        return None

    @throttle(lambda self: self._consumer_cleanup_interval)
    async def _cleanup_stale_consumers(self, key: str) -> None:
        stream_key = self._stream_key(key)
        try:
            consumers = await self._redis.xinfo_consumers(stream_key, GROUP_NAME)
        except ResponseError:
            return
        for consumer in consumers:
            name = consumer.get("name", consumer.get(b"name", b""))
            name_str = name.decode() if isinstance(name, bytes) else str(name)
            if name_str == self._consumer:
                continue
            idle = consumer.get("idle", consumer.get(b"idle", 0))
            pel_count = consumer.get("pending", consumer.get(b"pending", 0))
            if idle > self._consumer_idle_threshold_ms and pel_count == 0:
                await self._redis.xgroup_delconsumer(stream_key, GROUP_NAME, name)

    def _reset_connection_state(self) -> None:
        self._initialized_groups.clear()
        self._ack_script = None
        self._dlq_script = None

    async def reset(self) -> None:
        self._reset_connection_state()
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
        key = self._stream_key(task_run.task_key)
        await self._ensure_group(key)
        await self._redis.xadd(key, {"data": task_run.model_dump_json()})

    async def retry(self, task_run: schemas.core.TaskRun) -> None:
        # No-op for Redis: entry stays in PEL, XAUTOCLAIM recovers.
        pass

    async def ack(self, delivered: DeliveredTaskRun) -> None:
        if delivered.ack_token is None:
            return
        stream_key = delivered.ack_token["stream_key"]
        msg_id = delivered.ack_token["msg_id"]
        script = self._get_ack_script()
        await script(keys=[stream_key], args=[GROUP_NAME, msg_id])

    @staticmethod
    def _to_str(value: bytes | str) -> str:
        return value.decode() if isinstance(value, bytes) else value

    def _parse_stream_result(
        self,
        stream_key: bytes | str,
        msg_id: bytes | str,
        fields: dict,
    ) -> DeliveredTaskRun:
        data = fields.get(b"data")
        task_run = schemas.core.TaskRun.model_validate_json(data)
        return DeliveredTaskRun(
            task_run=task_run,
            ack_token={
                "stream_key": self._to_str(stream_key),
                "msg_id": self._to_str(msg_id),
            },
        )

    async def dequeue(
        self,
        key: str,
        timeout: float = 1,
    ) -> DeliveredTaskRun:
        backoff = 1
        while True:
            try:
                if self._dequeue_semaphore is not None:
                    async with self._dequeue_semaphore:
                        return await self._dequeue_inner(key)
                return await self._dequeue_inner(key)
            except asyncio.TimeoutError:
                raise
            except RedisError:
                logger.warning(
                    f"Redis connection error, retrying in {backoff}s",
                    exc_info=True,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)
                await clear_cached_clients()
                self._redis = get_async_redis_client(decode_responses=False)
                self._reset_connection_state()

    async def _dequeue_inner(self, key: str) -> DeliveredTaskRun:
        stream_key = self._stream_key(key)
        await self._ensure_group(stream_key)

        await self._cleanup_stale_consumers(key)

        recovered = await self._claim_one_stale_entry(key)
        if recovered:
            return recovered

        result = await self._redis.xreadgroup(
            GROUP_NAME,
            self._consumer,
            streams={stream_key: ">"},
            count=1,
            block=self._dequeue_block_ms,
        )
        if not result:
            raise asyncio.TimeoutError

        stream_key_r, entries = result[0]
        msg_id, fields = entries[0]
        return self._parse_stream_result(stream_key_r, msg_id, fields)
