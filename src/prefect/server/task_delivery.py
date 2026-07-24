"""Durable delivery of deferred task runs to TaskWorkers."""

from __future__ import annotations

import asyncio
import hashlib
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, AsyncGenerator, ClassVar, TypedDict, cast

import orjson
import sqlalchemy as sa
from docket import CurrentDocket, Docket, Perpetual
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy.orm import selectinload

import prefect.server.schemas as schemas
from prefect.logging import get_logger
from prefect.server.database import provide_database_interface
from prefect.server.schemas.states import StateType
from prefect.settings import get_current_settings

_RECONNECTION_DELAY = 0.5
_READY = "ready"
_CLAIMED = "claimed"
_logger = get_logger(__name__)

_RESERVE = """
if redis.call('ZSCORE', KEYS[1], ARGV[1]) then return 1 end
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[2]) then return 0 end
redis.call('ZADD', KEYS[1], 0, ARGV[1])
return 1
"""

_OFFER = """
if redis.call('EXISTS', KEYS[2]) == 1 then
  redis.call('ZREM', KEYS[3], ARGV[1])
  redis.call('DEL', KEYS[1])
  return 0
end
if redis.call('EXISTS', KEYS[1]) == 0 then
  redis.call('LPUSH', KEYS[4], ARGV[2])
  redis.call('SET', KEYS[1], 'ready')
  return 1
end
return 0
"""

_CLAIM = """
for i, queue in ipairs(KEYS) do
  local message = redis.call('RPOP', queue)
  if message then
    local delivery, marker, acked, members =
      string.match(message, '^([^\\n]+)\\n([^\\n]+)\\n([^\\n]+)\\n([^\\n]+)\\n')
    if redis.call('EXISTS', acked) == 0 then
      redis.call('SET', marker, 'claimed', 'PX', ARGV[1])
      redis.call('ZREM', members, delivery)
      return {queue, message}
    end
    redis.call('DEL', marker)
  end
end
return nil
"""

_REQUEUE = """
if redis.call('EXISTS', KEYS[2]) == 1 then
  redis.call('DEL', KEYS[1])
  return 1
end
if not redis.call('ZSCORE', KEYS[3], ARGV[1]) then
  if redis.call('ZCARD', KEYS[3]) >= tonumber(ARGV[3]) then return 0 end
  redis.call('ZADD', KEYS[3], 0, ARGV[1])
end
redis.call('RPUSH', KEYS[4], ARGV[2])
redis.call('SET', KEYS[1], 'ready')
return 1
"""


class TaskDeliveryUnavailable(RuntimeError):
    """Raised when task delivery has not been configured."""


class _DeliveryEnvelope(TypedDict):
    delivery_id: str
    queued_key: str
    acked_key: str
    members_key: str
    kind: str
    task_run: dict[str, Any]


@dataclass(frozen=True)
class TaskRunDelivery:
    task_run: schemas.core.TaskRun
    delivery_id: str
    queue: str
    message: bytes
    members_key: str
    max_size: int


class TaskRunSubscription:
    """A TaskWorker subscription to one or more task-key queues."""

    def __init__(
        self,
        docket: Docket,
        task_keys: list[str],
        visibility_timeout: timedelta,
        max_scheduled_size: int,
        max_retry_size: int,
    ) -> None:
        self._docket = docket
        self._queues = [
            queue
            for task_key in task_keys
            for queue in (
                _queue_key(docket, task_key, "retry"),
                _queue_key(docket, task_key, "scheduled"),
            )
        ]
        self._visibility_timeout = visibility_timeout
        self._max_sizes = {
            "scheduled": max_scheduled_size,
            "retry": max_retry_size,
        }
        self._outstanding: dict[str, TaskRunDelivery] = {}
        self._visibility_renewer: asyncio.Task[None] | None = None

    async def __aenter__(self) -> "TaskRunSubscription":
        self._visibility_renewer = asyncio.create_task(self._renew_visibility())
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        if self._visibility_renewer is not None:
            self._visibility_renewer.cancel()
            await asyncio.gather(self._visibility_renewer, return_exceptions=True)

        deliveries = list(self._outstanding.values())
        self._outstanding.clear()
        for delivery in deliveries:
            try:
                await self._requeue(delivery)
            except RedisConnectionError:
                # The Docket execution offers the run again after the visibility
                # timeout if this API process cannot return it explicitly.
                pass

    async def receive(self, timeout: float = 1) -> TaskRunDelivery:
        """Receive a task run matching this subscription."""
        return await asyncio.wait_for(self._receive_one(), timeout=timeout)

    async def _receive_one(self) -> TaskRunDelivery:
        while True:
            try:
                result = await self._pop_one()
                if result is None:
                    continue

                queue, message = result
                queue = _decode(queue)
                envelope = _decode_envelope(message)
                delivery_id = envelope["delivery_id"]

                delivery = TaskRunDelivery(
                    task_run=schemas.core.TaskRun.model_validate(envelope["task_run"]),
                    delivery_id=delivery_id,
                    queue=queue,
                    message=message,
                    members_key=envelope["members_key"],
                    max_size=self._max_sizes[envelope["kind"]],
                )
                self._outstanding[delivery_id] = delivery
                return delivery
            except RedisConnectionError:
                _logger.warning(
                    "Lost the Redis connection while receiving a task delivery; "
                    "retrying in %.1f seconds",
                    _RECONNECTION_DELAY,
                    exc_info=True,
                )
                await asyncio.sleep(_RECONNECTION_DELAY)

    async def _pop_one(self) -> tuple[bytes, bytes] | None:
        async with self._docket.redis() as redis:
            result = await cast(Any, redis).eval(
                _CLAIM,
                len(self._queues),
                *self._queues,
                str(int(self._visibility_timeout.total_seconds() * 1000)),
            )
        if result is None:
            await asyncio.sleep(0.01)
            return None
        return result[0], result[1]

    async def acknowledge(self, delivery: TaskRunDelivery) -> None:
        """Acknowledge a task run accepted by the connected TaskWorker."""
        async with self._docket.redis() as redis:
            await redis.set(
                _acked_key(self._docket, delivery.delivery_id),
                "1",
                ex=_delivery_ttl(self._visibility_timeout),
            )
            await redis.delete(_queued_key(self._docket, delivery.delivery_id))

        self._outstanding.pop(delivery.delivery_id, None)
        # The acceptance marker is authoritative if cancellation races a
        # reschedule or Redis becomes unavailable after the writes above.
        try:
            await self._docket.cancel(delivery.delivery_id)
        except RedisConnectionError:
            _logger.warning(
                "Accepted task delivery %s, but could not cancel its Docket "
                "execution; it will stop when Docket next observes the acceptance",
                delivery.delivery_id,
                exc_info=True,
            )

    async def _requeue(self, delivery: TaskRunDelivery) -> None:
        while True:
            async with self._docket.redis() as redis:
                requeued = await cast(Any, redis).eval(
                    _REQUEUE,
                    4,
                    _queued_key(self._docket, delivery.delivery_id),
                    _acked_key(self._docket, delivery.delivery_id),
                    delivery.members_key,
                    delivery.queue,
                    delivery.delivery_id,
                    delivery.message,
                    str(delivery.max_size),
                )
            if requeued:
                return
            await asyncio.sleep(0.01)

    async def _renew_visibility(self) -> None:
        interval = max(0.001, self._visibility_timeout.total_seconds() / 4)
        while True:
            await asyncio.sleep(interval)
            try:
                async with self._docket.redis() as redis:
                    for delivery_id in list(self._outstanding):
                        await redis.set(
                            _queued_key(self._docket, delivery_id),
                            _CLAIMED,
                            xx=True,
                            ex=self._visibility_timeout,
                        )
            except RedisConnectionError:
                _logger.warning(
                    "Lost the Redis connection while renewing task delivery visibility",
                    exc_info=True,
                )


class TaskRunDeliveryManager:
    """Schedules Docket executions and creates keyed TaskWorker subscriptions."""

    _active: ClassVar["TaskRunDeliveryManager | None"] = None

    def __init__(
        self,
        docket: Docket,
        visibility_timeout: timedelta,
        max_scheduled_size: int | None = None,
        max_retry_size: int | None = None,
    ) -> None:
        self._docket = docket
        self._visibility_timeout = visibility_timeout
        scheduling = get_current_settings().server.tasks.scheduling
        self._max_scheduled_size = (
            max_scheduled_size
            if max_scheduled_size is not None
            else scheduling.max_scheduled_queue_size
        )
        self._max_retry_size = (
            max_retry_size
            if max_retry_size is not None
            else scheduling.max_retry_queue_size
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
        kind = _delivery_kind(task_run)
        max_size = self._max_retry_size if kind == "retry" else self._max_scheduled_size
        delivery_id = _delivery_key(task_run)
        members_key = _members_key(self._docket, task_run.task_key, kind)
        await self._reserve(members_key, delivery_id, max_size, wait=True)
        await self._docket.add(
            deliver_task_run,
            key=delivery_id,
            when=when,
        )(task_run, self._visibility_timeout.total_seconds(), kind, max_size)

    async def reconcile(self, task_run: schemas.core.TaskRun) -> bool:
        """Restore delivery for a deferred task run if its execution is absent."""
        delivery_id = _delivery_key(task_run)
        if await self._docket.get_execution(delivery_id) is not None:
            return False
        async with self._docket.redis() as redis:
            if await redis.exists(_acked_key(self._docket, delivery_id)):
                return False
        kind = _delivery_kind(task_run)
        max_size = self._max_retry_size if kind == "retry" else self._max_scheduled_size
        members_key = _members_key(self._docket, task_run.task_key, kind)
        if not await self._reserve(members_key, delivery_id, max_size, wait=False):
            return False
        when = (
            task_run.state.state_details.scheduled_time
            if kind == "retry" and task_run.state is not None
            else None
        )
        await self._docket.add(deliver_task_run, key=delivery_id, when=when)(
            task_run, self._visibility_timeout.total_seconds(), kind, max_size
        )
        return True

    async def _reserve(
        self, members_key: str, delivery_id: str, max_size: int, *, wait: bool
    ) -> bool:
        while True:
            async with self._docket.redis() as redis:
                reserved = await cast(Any, redis).eval(
                    _RESERVE, 1, members_key, delivery_id, str(max_size)
                )
            if reserved or not wait:
                return bool(reserved)
            await asyncio.sleep(0.01)

    async def publish(self, task_run: schemas.core.TaskRun) -> None:
        await self.schedule(task_run)

    def subscribe(self, task_keys: list[str]) -> TaskRunSubscription:
        return TaskRunSubscription(
            self._docket,
            task_keys,
            self._visibility_timeout,
            self._max_scheduled_size,
            self._max_retry_size,
        )


async def schedule_task_run_delivery(
    task_run: schemas.core.TaskRun,
    *,
    when: datetime | None = None,
) -> None:
    """Schedule a deferred task run for delivery through Docket."""
    await TaskRunDeliveryManager.active().schedule(task_run, when=when)


async def deliver_task_run(
    task_run: schemas.core.TaskRun,
    visibility_timeout_seconds: float,
    kind: str,
    max_size: int,
    perpetual: Perpetual = Perpetual(),
    docket: Docket = CurrentDocket(),
) -> None:
    """Offer a task run until a TaskWorker acknowledges it."""
    visibility_timeout = timedelta(seconds=visibility_timeout_seconds)
    delivery_id = _delivery_key(task_run)
    queued = _queued_key(docket, delivery_id)
    acked = _acked_key(docket, delivery_id)
    members = _members_key(docket, task_run.task_key, kind)
    queue = _queue_key(docket, task_run.task_key, kind)
    message = _encode_envelope(delivery_id, queued, acked, members, kind, task_run)

    async with docket.redis() as redis:
        if await redis.exists(acked):
            await redis.zrem(members, delivery_id)
            await redis.delete(queued)
            perpetual.cancel()
            return
        await cast(Any, redis).eval(
            _OFFER,
            4,
            queued,
            acked,
            members,
            queue,
            delivery_id,
            message,
        )

    perpetual.after(visibility_timeout)


@asynccontextmanager
async def task_run_delivery_lifespan(
    docket: Docket,
    *,
    visibility_timeout: timedelta,
) -> AsyncGenerator[TaskRunDeliveryManager, None]:
    """Configure deferred task delivery for an API process."""
    manager = TaskRunDeliveryManager(docket, visibility_timeout)
    if TaskRunDeliveryManager._active is not None:
        raise RuntimeError("Task delivery is already running")
    TaskRunDeliveryManager._active = manager
    reconciliation = asyncio.create_task(_reconcile_task_run_deliveries(manager))
    try:
        yield manager
    finally:
        reconciliation.cancel()
        await asyncio.gather(reconciliation, return_exceptions=True)
        if TaskRunDeliveryManager._active is manager:
            TaskRunDeliveryManager._active = None


async def _reconcile_task_run_deliveries(
    manager: TaskRunDeliveryManager,
) -> None:
    """Continuously repair Docket delivery state from the Prefect database."""
    while True:
        try:
            db = provide_database_interface()
            async with db.session_context(begin_transaction=False) as session:
                result = await session.execute(
                    sa.select(db.TaskRun)
                    .join(
                        db.TaskRunState,
                        db.TaskRun.state_id == db.TaskRunState.id,
                    )
                    .where(db.TaskRun.state_type == StateType.SCHEDULED)
                    .where(
                        db.TaskRunState.state_details["deferred"].as_boolean()
                        == sa.true()
                    )
                    .options(selectinload(db.TaskRun.state))
                    .order_by(db.TaskRun.created)
                )
                task_runs = [
                    schemas.core.TaskRun.model_validate(model)
                    for model in result.scalars().all()
                ]
            for task_run in task_runs:
                await manager.reconcile(task_run)
        except asyncio.CancelledError:
            raise
        except Exception:
            _logger.warning(
                "Failed to reconcile deferred task deliveries; retrying",
                exc_info=True,
            )
        await asyncio.sleep(max(1.0, manager._visibility_timeout.total_seconds() / 2))


def _queue_key(docket: Docket, task_key: str, kind: str = "scheduled") -> str:
    route = hashlib.blake2b(task_key.encode(), digest_size=16).hexdigest()
    return docket.key(f"task-runs:ready:{route}:{kind}")


def _members_key(docket: Docket, task_key: str, kind: str) -> str:
    route = hashlib.blake2b(task_key.encode(), digest_size=16).hexdigest()
    return docket.key(f"task-runs:members:{route}:{kind}")


def _delivery_kind(task_run: schemas.core.TaskRun) -> str:
    return (
        "retry"
        if task_run.state is not None and task_run.state.name == "AwaitingRetry"
        else "scheduled"
    )


def _encode_envelope(
    delivery_id: str,
    queued_key: str,
    acked_key: str,
    members_key: str,
    kind: str,
    task_run: schemas.core.TaskRun,
) -> bytes:
    return b"\n".join(
        (
            delivery_id.encode(),
            queued_key.encode(),
            acked_key.encode(),
            members_key.encode(),
            kind.encode(),
            orjson.dumps(task_run.model_dump(mode="json")),
        )
    )


def _decode_envelope(message: bytes) -> _DeliveryEnvelope:
    delivery_id, queued, acked, members, kind, task_run = message.split(b"\n", 5)
    return {
        "delivery_id": delivery_id.decode(),
        "queued_key": queued.decode(),
        "acked_key": acked.decode(),
        "members_key": members.decode(),
        "kind": kind.decode(),
        "task_run": orjson.loads(task_run),
    }


def _delivery_key(task_run: schemas.core.TaskRun) -> str:
    state_id = task_run.state_id
    if state_id is None and task_run.state is not None:
        state_id = task_run.state.id
    return f"task-run:{task_run.id}:{state_id}"


def _delivery_marker_key(docket: Docket, delivery_id: str, marker: str) -> str:
    delivery = hashlib.blake2b(delivery_id.encode(), digest_size=16).hexdigest()
    return docket.key(f"task-runs:{delivery}:{marker}")


def _queued_key(docket: Docket, delivery_id: str) -> str:
    return _delivery_marker_key(docket, delivery_id, "queued")


def _acked_key(docket: Docket, delivery_id: str) -> str:
    return _delivery_marker_key(docket, delivery_id, "acked")


def _delivery_ttl(visibility_timeout: timedelta) -> int:
    return max(3600, int(visibility_timeout.total_seconds() * 10))


def _decode(value: bytes | str) -> str:
    return value.decode() if isinstance(value, bytes) else value
