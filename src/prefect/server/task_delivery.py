"""Durable, task-keyed delivery of deferred task runs to TaskWorkers."""

from __future__ import annotations

import asyncio
import hashlib
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, AsyncGenerator, ClassVar
from uuid import uuid4

from docket import CurrentDocket, Docket
from redis.exceptions import ResponseError

import prefect.server.schemas as schemas

_GROUP = "prefect-task-workers"
_KEY_PREFIX = "prefect:task-runs"
_PUBLISH_SCRIPT = """
if redis.call('SET', KEYS[2], '1', 'NX', 'EX', ARGV[1]) then
    return redis.call('XADD', KEYS[1], '*', 'data', ARGV[2])
end
return false
"""
_ACK_SCRIPT = """
redis.call('XACK', KEYS[1], ARGV[1], ARGV[2])
redis.call('XDEL', KEYS[1], ARGV[2])
return 1
"""


class TaskDeliveryUnavailable(RuntimeError):
    """Raised when task delivery has not been configured."""


@dataclass(frozen=True)
class TaskRunDelivery:
    task_run: schemas.core.TaskRun
    stream: str
    message_id: str


class TaskRunSubscription:
    """A keyed TaskWorker subscription backed by Docket's Redis transport."""

    def __init__(
        self,
        docket: Docket,
        task_keys: list[str],
        client_id: str,
        visibility_timeout: timedelta,
    ) -> None:
        self._docket = docket
        self._streams = [_stream_key(docket.name, key) for key in task_keys]
        self._consumer = f"{client_id}-{uuid4()}"
        self._visibility_timeout_ms = max(
            1, int(visibility_timeout.total_seconds() * 1000)
        )
        self._pending: deque[TaskRunDelivery] = deque()

    async def __aenter__(self) -> "TaskRunSubscription":
        async with self._docket.redis() as redis:
            pipeline = redis.pipeline()
            for stream in self._streams:
                pipeline.xgroup_create(stream, _GROUP, id="0", mkstream=True)
            for result in await pipeline.execute(raise_on_error=False):
                if isinstance(result, ResponseError) and "BUSYGROUP" in str(result):
                    continue
                if isinstance(result, BaseException):
                    raise result
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        return None

    async def receive(self, timeout: float = 1) -> TaskRunDelivery:
        """Receive a new or abandoned delivery matching this subscription."""
        if self._pending:
            return self._pending.popleft()

        async with self._docket.redis() as redis:
            pipeline = redis.pipeline()
            for stream in self._streams:
                pipeline.xautoclaim(
                    stream,
                    _GROUP,
                    self._consumer,
                    min_idle_time=self._visibility_timeout_ms,
                    start_id="0-0",
                    count=1,
                )
            for stream, result in zip(self._streams, await pipeline.execute()):
                _, claimed, *_ = result
                self._pending.extend(
                    _parse_delivery(stream, message_id, fields)
                    for message_id, fields in claimed
                )

            if self._pending:
                return self._pending.popleft()

            result = await redis.xreadgroup(
                _GROUP,
                self._consumer,
                streams=dict.fromkeys(self._streams, ">"),
                count=1,
                block=max(1, int(timeout * 1000)),
            )

        if not result:
            raise asyncio.TimeoutError

        self._pending.extend(
            _parse_delivery(stream, message_id, fields)
            for stream, entries in result
            for message_id, fields in entries
        )
        return self._pending.popleft()

    async def acknowledge(self, delivery: TaskRunDelivery) -> None:
        """Permanently acknowledge a delivery accepted by the TaskWorker."""
        async with self._docket.redis() as redis:
            await redis.eval(
                _ACK_SCRIPT,
                1,
                delivery.stream,
                _GROUP,
                delivery.message_id,
            )

    async def renew(self, delivery: TaskRunDelivery) -> None:
        """Keep a delivery claimed while its TaskWorker remains connected."""
        async with self._docket.redis() as redis:
            await redis.xclaim(
                delivery.stream,
                _GROUP,
                self._consumer,
                min_idle_time=0,
                message_ids=[delivery.message_id],
                idle=0,
                justid=True,
            )

    @property
    def renewal_interval(self) -> float:
        return self._visibility_timeout_ms / 3000


class TaskRunDeliveryManager:
    """Publishes task runs and creates keyed TaskWorker subscriptions."""

    _active: ClassVar["TaskRunDeliveryManager | None"] = None

    def __init__(self, docket: Docket, visibility_timeout: timedelta) -> None:
        self._docket = docket
        self._visibility_timeout = visibility_timeout
        self._deduplication_ttl = max(
            3600, int(visibility_timeout.total_seconds() * 10)
        )

    @classmethod
    def active(cls) -> "TaskRunDeliveryManager":
        if cls._active is None:
            raise TaskDeliveryUnavailable("Task delivery is not running")
        return cls._active

    async def schedule(
        self,
        task_run: schemas.core.TaskRun,
        *,
        when: datetime | None = None,
    ) -> None:
        if when is None:
            await self.publish(task_run)
            return

        await self._docket.add(
            publish_task_run,
            key=_delivery_key(task_run),
            when=when,
        )(task_run)

    async def publish(self, task_run: schemas.core.TaskRun) -> None:
        await _publish(
            self._docket,
            task_run,
            deduplication_ttl=self._deduplication_ttl,
        )

    def subscribe(self, task_keys: list[str], client_id: str) -> TaskRunSubscription:
        return TaskRunSubscription(
            self._docket,
            task_keys,
            client_id,
            self._visibility_timeout,
        )


async def schedule_task_run_delivery(
    task_run: schemas.core.TaskRun,
    *,
    when: datetime | None = None,
) -> None:
    """Schedule publication of a deferred task run through Docket."""
    await TaskRunDeliveryManager.active().schedule(task_run, when=when)


async def publish_task_run(
    task_run: schemas.core.TaskRun,
    docket: Docket = CurrentDocket(),
) -> None:
    """Docket task that publishes a run to its task-keyed delivery stream."""
    await _publish(docket, task_run)


@asynccontextmanager
async def task_run_delivery_lifespan(
    docket: Docket,
    *,
    visibility_timeout: timedelta,
) -> AsyncGenerator[TaskRunDeliveryManager, None]:
    """Configure publication and subscription for the API process."""
    manager = TaskRunDeliveryManager(docket, visibility_timeout)
    if TaskRunDeliveryManager._active is not None:
        raise RuntimeError("Task delivery is already running")
    TaskRunDeliveryManager._active = manager
    try:
        yield manager
    finally:
        if TaskRunDeliveryManager._active is manager:
            TaskRunDeliveryManager._active = None


def _stream_key(docket_name: str, task_key: str) -> str:
    namespace = hashlib.blake2b(docket_name.encode(), digest_size=8).hexdigest()
    task = hashlib.blake2b(task_key.encode(), digest_size=16).hexdigest()
    return f"{_KEY_PREFIX}:{namespace}:stream:{task}"


def _delivery_key(task_run: schemas.core.TaskRun) -> str:
    state_id = task_run.state_id
    if state_id is None and task_run.state is not None:
        state_id = task_run.state.id
    return f"task-run:{task_run.id}:{state_id}"


async def _publish(
    docket: Docket,
    task_run: schemas.core.TaskRun,
    *,
    deduplication_ttl: int = 3600,
) -> None:
    stream = _stream_key(docket.name, task_run.task_key)
    marker = f"{stream}:published:{_delivery_key(task_run)}"
    async with docket.redis() as redis:
        await redis.eval(
            _PUBLISH_SCRIPT,
            2,
            stream,
            marker,
            str(deduplication_ttl),
            task_run.model_dump_json(),
        )


def _parse_delivery(
    stream: bytes | str,
    message_id: bytes | str,
    fields: dict[Any, Any],
) -> TaskRunDelivery:
    stream = stream.decode() if isinstance(stream, bytes) else stream
    message_id = message_id.decode() if isinstance(message_id, bytes) else message_id
    data = fields.get(b"data", fields.get("data"))
    if data is None:
        raise ValueError(f"Task delivery {message_id!r} has no data")
    return TaskRunDelivery(
        task_run=schemas.core.TaskRun.model_validate_json(data),
        stream=stream,
        message_id=message_id,
    )
