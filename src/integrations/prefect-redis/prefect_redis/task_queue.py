"""
Redis Streams task queue for delivering background task runs to TaskWorkers.

Uses consumer groups (PEL) for atomic inflight tracking and XAUTOCLAIM for
crash recovery. At-least-once delivery — no gap between dequeue and inflight
tracking.

Activated by setting:
    PREFECT_TASK_SCHEDULING_BACKEND=prefect_redis.task_queue

Requires Redis/Valkey 6.2+ for XAUTOCLAIM.
"""

import asyncio
import time
from collections import deque
from uuid import uuid4

from redis.asyncio import Redis
from redis.exceptions import RedisError, ResponseError

import prefect.server.schemas as schemas
from prefect.logging import get_logger
from prefect.server.task_queue import DeliveredTaskRun
from prefect.settings import get_current_settings
from prefect_redis.client import get_async_redis_client

logger = get_logger(__name__)

KEY_PREFIX = "prefect:tqs"
GROUP_NAME = "task_workers"

_CLAIM_EXACTLY_ONE_SCRIPT = """
for i = 1, #KEYS do
    local result = redis.call('XREADGROUP', 'GROUP', ARGV[1], ARGV[2],
                              'COUNT', 1, 'STREAMS', KEYS[i], '>')
    if result and #result > 0 and #result[1][2] > 0 then
        return result
    end
end
return nil
"""


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
        self._redis: Redis = get_async_redis_client(decode_responses=False)
        self._consumer: str = str(uuid4())
        self._offset: int = 0
        self._initialized_groups: set[str] = set()
        self._last_recovery_time: float = 0.0
        self._recovery_interval: int = settings.stream_recovery_interval
        self._last_consumer_cleanup_time: float = 0.0
        self._consumer_cleanup_interval: int = settings.stream_consumer_cleanup_interval
        self._consumer_idle_threshold_ms: int = (
            settings.stream_consumer_idle_threshold * 1000
        )
        self._key_buffers: dict[str, deque[tuple[float, DeliveredTaskRun]]] = {}
        self._buffer_ttl: int = max(self._visibility_timeout - 10, 1)
        self._peek_and_claim_script = None
        self.__class__._initialized = True

        logger.info(f"Stream task queue consumer: {self._consumer}")

    def _scheduled_key(self, task_key: str) -> str:
        return f"{KEY_PREFIX}:{task_key}:scheduled"

    def _retry_key(self, task_key: str) -> str:
        return f"{KEY_PREFIX}:{task_key}:retry"

    def _prioritize_keys(self, keys: list[str]) -> list[str]:
        n = len(keys)
        if n == 0:
            return keys
        i = self._offset % n
        return keys[i:] + keys[:i]

    def _get_peek_and_claim(self):
        if self._peek_and_claim_script is None:
            self._peek_and_claim_script = self._redis.register_script(
                _CLAIM_EXACTLY_ONE_SCRIPT
            )
        return self._peek_and_claim_script

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
        # Note: ConnectionError (not ResponseError) propagates intentionally —
        # the outer retry loop in dequeue_from_keys handles reconnection.

    async def _maybe_recover_stale_entries(self, keys: list[str]) -> None:
        now = time.time()
        if now - self._last_recovery_time < self._recovery_interval:
            return
        self._last_recovery_time = now
        await self._recover_stale_entries(keys)

    async def _maybe_cleanup_stale_consumers(self, keys: list[str]) -> None:
        now = time.time()
        if now - self._last_consumer_cleanup_time < self._consumer_cleanup_interval:
            return
        self._last_consumer_cleanup_time = now
        await self._cleanup_stale_consumers(keys)

    async def _recover_stale_entries(self, keys: list[str]) -> None:
        """Claim stale PEL entries via XAUTOCLAIM and feed into local buffer.

        Entries stay in the stream with their delivery count intact — no
        XADD re-enqueue, no counter reset. They cycle between PEL and buffer
        until successfully acked.
        """
        min_idle_ms = self._visibility_timeout * 1000
        now = time.time()
        for key in keys:
            for stream_key in (self._retry_key(key), self._scheduled_key(key)):
                try:
                    await self._ensure_group(stream_key)
                    result = await self._redis.xautoclaim(
                        stream_key,
                        GROUP_NAME,
                        self._consumer,
                        min_idle_time=min_idle_ms,
                        start_id="0-0",
                        count=10,
                    )
                except ResponseError:
                    continue
                _, claimed, _ = result
                for msg_id, fields in claimed:
                    if fields is None:
                        # Orphan PEL entry — stream data was deleted
                        await self._redis.xack(stream_key, GROUP_NAME, msg_id)
                        continue

                    # Feed directly into local buffer
                    delivered = self._parse_stream_result(stream_key, msg_id, fields)
                    sk = delivered.ack_token["stream_key"]
                    if sk not in self._key_buffers:
                        self._key_buffers[sk] = deque()
                    self._key_buffers[sk].append((now, delivered))

    async def _cleanup_stale_consumers(self, keys: list[str]) -> None:
        for key in keys:
            for stream_key in (self._retry_key(key), self._scheduled_key(key)):
                try:
                    consumers = await self._redis.xinfo_consumers(
                        stream_key, GROUP_NAME
                    )
                except ResponseError:
                    continue
                for consumer in consumers:
                    name = consumer.get("name") or consumer.get(b"name")
                    if isinstance(name, bytes):
                        name_str = name.decode()
                    else:
                        name_str = str(name) if name is not None else ""
                    if name_str == self._consumer:
                        continue
                    idle = consumer.get("idle") or consumer.get(b"idle", 0)
                    pel_count = consumer.get("pel-count") or consumer.get(
                        b"pel-count", 0
                    )
                    if idle > self._consumer_idle_threshold_ms and pel_count == 0:
                        await self._redis.xgroup_delconsumer(
                            stream_key, GROUP_NAME, name
                        )

    async def reset(self) -> None:
        self._initialized_groups.clear()
        self._key_buffers.clear()
        self._peek_and_claim_script = None
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
        key = self._scheduled_key(task_run.task_key)
        await self._ensure_group(key)
        await self._redis.xadd(key, {"data": task_run.model_dump_json()})

    async def retry(self, task_run: schemas.core.TaskRun) -> None:
        key = self._retry_key(task_run.task_key)
        await self._ensure_group(key)
        await self._redis.xadd(key, {"data": task_run.model_dump_json()})

    async def ack(self, delivered: DeliveredTaskRun) -> None:
        if delivered.ack_token is None:
            return
        stream_key = delivered.ack_token["stream_key"]
        msg_id = delivered.ack_token["msg_id"]
        pipe = self._redis.pipeline()
        pipe.xack(stream_key, GROUP_NAME, msg_id)
        pipe.xdel(stream_key, msg_id)
        await pipe.execute()

    def _parse_stream_result(
        self,
        stream_key: bytes | str,
        msg_id: bytes | str,
        fields: dict,
    ) -> DeliveredTaskRun:
        sk = stream_key.decode() if isinstance(stream_key, bytes) else stream_key
        mid = msg_id.decode() if isinstance(msg_id, bytes) else msg_id
        data = fields.get(b"data") or fields.get("data")
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
                raise  # normal timeout, propagate to caller
            except RedisError:
                logger.warning(
                    f"Redis connection error, retrying in {backoff}s",
                    exc_info=True,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)
                self._redis = get_async_redis_client(decode_responses=False)
                self._initialized_groups.clear()
                self._key_buffers.clear()
                self._peek_and_claim_script = None

    async def _dequeue_from_keys_inner(
        self,
        keys: list[str],
        timeout: float = 1,
    ) -> DeliveredTaskRun:
        rotated = self._prioritize_keys(keys)

        await self._maybe_recover_stale_entries(rotated)
        await self._maybe_cleanup_stale_consumers(rotated)

        # Step 1: drain local buffer first (drop expired items)
        for k in rotated:
            for suffix in (":retry", ":scheduled"):
                stream_key = (
                    self._retry_key(k) if suffix == ":retry" else self._scheduled_key(k)
                )
                buf = self._key_buffers.get(stream_key)
                if not buf:
                    continue
                while buf:
                    inserted_at, delivered = buf[0]
                    if time.time() - inserted_at > self._buffer_ttl:
                        buf.popleft()
                        logger.debug(
                            f"Buffer entry expired after {self._buffer_ttl}s, "
                            f"will be reclaimed via XAUTOCLAIM"
                        )
                        continue
                    self._offset += 1
                    return buf.popleft()[1]

        # Build stream keys in priority order: retry before scheduled per key
        stream_keys: list[str] = []
        for k in rotated:
            stream_keys.append(self._retry_key(k))
            stream_keys.append(self._scheduled_key(k))

        for sk in stream_keys:
            await self._ensure_group(sk)

        # Step 2: Lua peek-and-claim (1 round-trip, priority order)
        # The Lua script returns raw Redis arrays (not parsed by redis-py),
        # so we need to convert the flat field list into a dict.
        script = self._get_peek_and_claim()
        result = await script(keys=stream_keys, args=[GROUP_NAME, self._consumer])
        if result:
            stream_key, entries = result[0]
            msg_id, raw_fields = entries[0]
            if isinstance(raw_fields, list):
                fields = dict(zip(raw_fields[::2], raw_fields[1::2]))
            else:
                fields = raw_fields
            self._offset += 1
            return self._parse_stream_result(stream_key, msg_id, fields)

        # Step 3: blocking XREADGROUP fallback (idle case)
        all_streams = {k: ">" for k in stream_keys}
        timeout_ms = max(int(timeout * 1000), 1)
        result = await self._redis.xreadgroup(
            GROUP_NAME,
            self._consumer,
            streams=all_streams,
            count=1,
            block=timeout_ms,
        )
        if not result:
            raise asyncio.TimeoutError

        now = time.time()
        first_delivered = None
        for stream_key, stream_entries in result:
            for msg_id, fields in stream_entries:
                delivered = self._parse_stream_result(stream_key, msg_id, fields)
                sk = delivered.ack_token["stream_key"]
                if sk not in self._key_buffers:
                    self._key_buffers[sk] = deque()
                if first_delivered is None:
                    first_delivered = delivered
                else:
                    self._key_buffers[sk].append((now, delivered))

        self._offset += 1
        return first_delivered
