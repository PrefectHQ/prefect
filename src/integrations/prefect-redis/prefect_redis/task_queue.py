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
        """Claim one stale PEL entry from the consumer group.

        Loops through stale entries, skipping orphans and ineligible
        entries, until it finds one to deliver or exhausts stale entries.
        """
        stream_key = self._stream_key(key)
        min_idle_ms = self._visibility_timeout * 1000

        while True:
            try:
                result = await self._redis.xautoclaim(
                    stream_key,
                    GROUP_NAME,
                    self._consumer,
                    min_idle_time=min_idle_ms,
                    start_id="0-0",
                    count=1,
                )
            except ResponseError:
                return None

            _, claimed, _ = result
            if not claimed:
                return None

            msg_id, fields = claimed[0]
            if fields is None:
                await self._redis.xack(stream_key, GROUP_NAME, msg_id)
                continue

            if await self._check_retry_eligibility(key, stream_key, msg_id, fields):
                return self._parse_stream_result(stream_key, msg_id, fields)

    async def _check_retry_eligibility(
        self,
        key: str,
        stream_key: str,
        msg_id: bytes | str,
        fields: dict,
    ) -> bool:
        """Check if a claimed entry is eligible for redelivery.

        Returns True if under max_retries. Returns False if over
        max_retries (moved to DLQ atomically via Lua script).
        """
        pending_info = await self._redis.xpending_range(
            stream_key,
            GROUP_NAME,
            min=msg_id,
            max=msg_id,
            count=1,
        )
        if not pending_info:
            return True

        info = pending_info[0]
        times_delivered = info.get("times_delivered") or info.get(b"times_delivered", 0)
        if times_delivered < self._max_retries:
            return True

        if not fields:
            # Corrupted entry with no fields — can't move to DLQ, just ack it
            await self._redis.xack(stream_key, GROUP_NAME, msg_id)
            return False

        dlq_key = self._dlq_key(key)
        flat_fields = [v for pair in fields.items() for v in pair]
        script = self._get_dlq_script()
        await script(
            keys=[stream_key, dlq_key],
            args=[GROUP_NAME, msg_id] + flat_fields,
        )
        logger.warning(
            f"Task moved to DLQ after {times_delivered} delivery attempts: {msg_id}"
        )
        return False

    @throttle(lambda self: self._consumer_cleanup_interval)
    async def _cleanup_stale_consumers(self, keys: list[str]) -> None:
        for key in keys:
            stream_key = self._stream_key(key)
            try:
                consumers = await self._redis.xinfo_consumers(stream_key, GROUP_NAME)
            except ResponseError:
                continue
            for consumer in consumers:
                name = consumer.get("name") or consumer.get(b"name", b"")
                name_str = name.decode() if isinstance(name, bytes) else str(name)
                if name_str == self._consumer:
                    continue
                idle = consumer.get("idle") or consumer.get(b"idle", 0)
                pel_count = consumer.get("pending") or consumer.get(b"pel-count", 0)
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

    def _parse_stream_result(
        self,
        stream_key: bytes | str,
        msg_id: bytes | str,
        fields: dict,
    ) -> DeliveredTaskRun:
        sk = stream_key.decode() if isinstance(stream_key, bytes) else stream_key
        mid = msg_id.decode() if isinstance(msg_id, bytes) else msg_id
        data = fields.get(b"data")
        task_run = schemas.core.TaskRun.model_validate_json(data)
        return DeliveredTaskRun(
            task_run=task_run,
            ack_token={"stream_key": sk, "msg_id": mid},
        )

    async def dequeue_from_keys(
        self,
        keys: list[str],
        timeout: float = 1,
    ) -> DeliveredTaskRun:
        backoff = 1
        while True:
            try:
                return await self._dequeue_from_keys_inner(keys, timeout)
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

    async def _dequeue_from_keys_inner(
        self,
        keys: list[str],
        timeout: float = 1,
    ) -> DeliveredTaskRun:
        key = keys[0]
        stream_key = self._stream_key(key)
        await self._ensure_group(stream_key)

        await self._cleanup_stale_consumers(keys)

        # Step 1: Claim one stale entry from dead consumers (throttled)
        recovered = await self._claim_one_stale_entry(key)
        if recovered:
            return recovered

        # Step 2: Block for new entries
        timeout_ms = max(int(timeout * 1000), 1)
        result = await self._redis.xreadgroup(
            GROUP_NAME,
            self._consumer,
            streams={stream_key: ">"},
            count=1,
            block=timeout_ms,
        )
        if not result:
            raise asyncio.TimeoutError

        stream_key_r, entries = result[0]
        msg_id, fields = entries[0]
        return self._parse_stream_result(stream_key_r, msg_id, fields)
