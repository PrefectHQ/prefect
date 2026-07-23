"""Durable, task-keyed delivery of deferred task runs to TaskWorkers."""

from __future__ import annotations

import asyncio
import hashlib
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, AsyncGenerator, ClassVar
from uuid import uuid4

from docket import CurrentDocket, Docket
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import ResponseError

import prefect.server.schemas as schemas
from prefect.logging import get_logger

_GROUP = "prefect-task-workers"
_KEY_PREFIX = "task-runs"
_RECONNECTION_DELAY = 0.5
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
_logger = get_logger(__name__)


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
        self._streams = [_stream_key(docket, key) for key in task_keys]
        self._consumer = f"{client_id}-{uuid4()}"
        self._visibility_timeout_ms = max(
            1, int(visibility_timeout.total_seconds() * 1000)
        )
        self._deliveries: asyncio.Queue[TaskRunDelivery] = asyncio.Queue()
        self._outstanding: dict[
            tuple[str, str], tuple[TaskRunDelivery, asyncio.Event]
        ] = {}
        self._readers: list[asyncio.Task[None]] = []
        self._lease_renewer: asyncio.Task[None] | None = None

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
        self._readers = [
            asyncio.create_task(self._read_stream(stream)) for stream in self._streams
        ]
        self._lease_renewer = asyncio.create_task(self._renew_leases())
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        tasks = [*self._readers]
        if self._lease_renewer is not None:
            tasks.append(self._lease_renewer)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        return None

    async def receive(self, timeout: float = 1) -> TaskRunDelivery:
        """Receive a new or abandoned delivery matching this subscription."""
        return await asyncio.wait_for(self._deliveries.get(), timeout=timeout)

    async def _read_stream(self, stream: str) -> None:
        while True:
            try:
                delivery = await self._read_one(stream)
            except RedisConnectionError:
                _logger.warning(
                    "Lost the Redis connection while reading task deliveries; "
                    "retrying in %.1f seconds",
                    _RECONNECTION_DELAY,
                    exc_info=True,
                )
                await asyncio.sleep(_RECONNECTION_DELAY)
                continue
            except ResponseError as exc:
                if "NOGROUP" not in str(exc):
                    raise
                try:
                    await self._ensure_group(stream)
                except RedisConnectionError:
                    _logger.warning(
                        "Lost the Redis connection while recreating a task "
                        "delivery consumer group; retrying in %.1f seconds",
                        _RECONNECTION_DELAY,
                        exc_info=True,
                    )
                    await asyncio.sleep(_RECONNECTION_DELAY)
                continue

            released = asyncio.Event()
            key = (delivery.stream, delivery.message_id)
            self._outstanding[key] = (delivery, released)
            await self._deliveries.put(delivery)
            await released.wait()

    async def _ensure_group(self, stream: str) -> None:
        try:
            async with self._docket.redis() as redis:
                await redis.xgroup_create(stream, _GROUP, id="0", mkstream=True)
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def _read_one(self, stream: str) -> TaskRunDelivery:
        while True:
            async with self._docket.redis() as redis:
                _, claimed, *_ = await redis.xautoclaim(
                    stream,
                    _GROUP,
                    self._consumer,
                    min_idle_time=self._visibility_timeout_ms,
                    start_id="0-0",
                    count=1,
                )
                if claimed:
                    message_id, fields = claimed[0]
                    return _parse_delivery(stream, message_id, fields)

                result = await redis.xreadgroup(
                    _GROUP,
                    self._consumer,
                    streams={stream: ">"},
                    count=1,
                    block=1000,
                )
            if result:
                _, entries = result[0]
                message_id, fields = entries[0]
                return _parse_delivery(stream, message_id, fields)

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
        _, released = self._outstanding.pop((delivery.stream, delivery.message_id))
        released.set()

    async def _renew(self) -> None:
        """Keep outstanding deliveries claimed while the TaskWorker is connected."""
        if not self._outstanding:
            return
        async with self._docket.redis() as redis:
            pipeline = redis.pipeline()
            for delivery, _ in self._outstanding.values():
                pipeline.xclaim(
                    delivery.stream,
                    _GROUP,
                    self._consumer,
                    min_idle_time=0,
                    message_ids=[delivery.message_id],
                    idle=0,
                    justid=True,
                )
            await pipeline.execute()

    async def _renew_leases(self) -> None:
        renewal_interval = self._visibility_timeout_ms / 4000
        while True:
            await asyncio.sleep(renewal_interval)
            try:
                await self._renew()
            except Exception:
                _logger.warning(
                    "Failed to renew task delivery leases",
                    exc_info=True,
                )


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


def _stream_key(docket: Docket, task_key: str) -> str:
    task = hashlib.blake2b(task_key.encode(), digest_size=16).hexdigest()
    return docket.key(f"{_KEY_PREFIX}:stream:{task}")


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
    stream = _stream_key(docket, task_run.task_key)
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
