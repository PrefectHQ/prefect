"""Redis-backed delivery for Prefect background tasks."""

from __future__ import annotations

import asyncio
from collections import deque
from types import TracebackType
from typing import Self
from uuid import uuid4

from pydantic import Field
from redis.asyncio import Redis
from redis.exceptions import ResponseError

from prefect.server.schemas.core import TaskRun
from prefect.server.task_queue import TaskQueueDelivery, TaskQueuePriority
from prefect.settings.base import PrefectBaseSettings, build_settings_config
from prefect_redis.client import get_async_redis_client, redis_key

_GROUP = "prefect-task-workers"
_PREFIX = "prefect:background-task-runs"
_ACK_SCRIPT = """
redis.call('XACK', KEYS[1], ARGV[1], ARGV[2])
redis.call('XDEL', KEYS[1], ARGV[2])
return 1
"""
_RELEASE_SCRIPT = """
redis.call('XADD', KEYS[2], '*', 'data', ARGV[3])
redis.call('XACK', KEYS[1], ARGV[1], ARGV[2])
redis.call('XDEL', KEYS[1], ARGV[2])
return 1
"""


class RedisTaskQueueSettings(PrefectBaseSettings):
    """Settings for Redis-backed background task delivery."""

    model_config = build_settings_config(("redis", "task_queue"))

    visibility_timeout: int = Field(
        default=30,
        gt=0,
        description="Seconds before delivery abandoned by a failed server is reclaimed.",
    )
    block_timeout: float = Field(
        default=0.5,
        ge=0.001,
        lt=1,
        description="Seconds a consumer blocks while waiting for a task run.",
    )


def _stream(task_key: str, priority: TaskQueuePriority) -> str:
    kind = "retry" if priority is TaskQueuePriority.RETRY else "scheduled"
    return redis_key(_PREFIX, f"{kind}:{task_key}")


class Publisher:
    """Publish task runs durably before returning from orchestration."""

    def __init__(self) -> None:
        self._redis: Redis = get_async_redis_client(decode_responses=False)

    async def publish(
        self,
        task_run: TaskRun,
        priority: TaskQueuePriority = TaskQueuePriority.SCHEDULED,
    ) -> None:
        await self._redis.xadd(
            _stream(task_run.task_key, priority),
            {"data": task_run.model_dump_json()},
        )


class Consumer:
    """Reserve task runs matching a TaskWorker's registered task keys."""

    def __init__(self, task_keys: list[str], consumer_id: str) -> None:
        settings = RedisTaskQueueSettings()
        self._redis: Redis = get_async_redis_client(decode_responses=False)
        self._consumer_id = f"{consumer_id}-{uuid4()}"
        self._visibility_timeout_ms = settings.visibility_timeout * 1000
        self._block_timeout_ms = int(settings.block_timeout * 1000)
        self._streams = {
            priority: [_stream(key, priority) for key in task_keys]
            for priority in TaskQueuePriority
        }
        self._buffer: deque[TaskQueueDelivery] = deque()
        self._outstanding: dict[tuple[str, str], TaskQueueDelivery] = {}
        self._ack = self._redis.register_script(_ACK_SCRIPT)
        self._release = self._redis.register_script(_RELEASE_SCRIPT)
        self._next_recovery_check = 0.0

    async def __aenter__(self) -> Self:
        for stream in self._all_streams:
            try:
                await self._redis.xgroup_create(stream, _GROUP, id="0", mkstream=True)
            except ResponseError as exc:
                if "BUSYGROUP" not in str(exc):
                    raise
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        deliveries = [*self._buffer, *self._outstanding.values()]
        self._buffer.clear()
        self._outstanding.clear()
        if deliveries:
            await asyncio.gather(*(self._release_delivery(item) for item in deliveries))
        for stream in self._all_streams:
            try:
                await self._redis.xgroup_delconsumer(stream, _GROUP, self._consumer_id)
            except ResponseError:
                pass

    @property
    def _all_streams(self) -> list[str]:
        return [
            *self._streams[TaskQueuePriority.RETRY],
            *self._streams[TaskQueuePriority.SCHEDULED],
        ]

    async def get(self) -> TaskQueueDelivery:
        if not self._buffer:
            await self._fill_buffer()
        delivery = self._buffer.popleft()
        stream, message_id = delivery.token
        self._outstanding[(stream, message_id)] = delivery
        return delivery

    async def acknowledge(self, delivery: TaskQueueDelivery) -> None:
        stream, message_id = delivery.token
        await self._ack(keys=[stream], args=[_GROUP, message_id])
        self._outstanding.pop((stream, message_id), None)

    async def release(self, delivery: TaskQueueDelivery) -> None:
        await self._release_delivery(delivery)
        stream, message_id = delivery.token
        self._outstanding.pop((stream, message_id), None)

    async def _release_delivery(self, delivery: TaskQueueDelivery) -> None:
        stream, message_id = delivery.token
        retry_stream = _stream(delivery.task_run.task_key, TaskQueuePriority.RETRY)
        await self._release(
            keys=[stream, retry_stream],
            args=[_GROUP, message_id, delivery.task_run.model_dump_json()],
        )

    async def _fill_buffer(self) -> None:
        # Recover work reserved by a server process that disappeared before its
        # TaskWorker acknowledged receipt.
        loop = asyncio.get_running_loop()
        if loop.time() >= self._next_recovery_check:
            self._next_recovery_check = loop.time() + min(
                self._visibility_timeout_ms / 2000, 5
            )
            for priority in TaskQueuePriority:
                for stream in self._streams[priority]:
                    claimed = await self._redis.xautoclaim(
                        stream,
                        _GROUP,
                        self._consumer_id,
                        min_idle_time=self._visibility_timeout_ms,
                        start_id="0-0",
                        count=1,
                    )
                    if claimed[1]:
                        self._append(stream, claimed[1][0])
            if self._buffer:
                return

        # Redis reads all subscribed streams in one round-trip. Retry streams
        # come first and the returned deliveries are sorted again below.
        result = await self._redis.xreadgroup(
            _GROUP,
            self._consumer_id,
            streams={stream: ">" for stream in self._all_streams},
            count=1,
            block=self._block_timeout_ms,
        )
        if not result:
            raise asyncio.TimeoutError

        retry_streams = set(self._streams[TaskQueuePriority.RETRY])
        result.sort(key=lambda item: 0 if self._decode(item[0]) in retry_streams else 1)
        for stream, entries in result:
            for entry in entries:
                self._append(stream, entry)

    def _append(self, stream: bytes | str, entry: tuple[bytes, dict]) -> None:
        message_id, fields = entry
        stream = self._decode(stream)
        message_id = self._decode(message_id)
        data = fields.get(b"data", fields.get("data"))
        if data is None:
            raise ValueError(f"Task queue entry {message_id} has no data")
        self._buffer.append(
            TaskQueueDelivery(
                task_run=TaskRun.model_validate_json(data),
                token=(stream, message_id),
            )
        )

    @staticmethod
    def _decode(value: bytes | str) -> str:
        return value.decode() if isinstance(value, bytes) else value
