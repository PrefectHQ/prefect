from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.websockets import WebSocket

import prefect.server.models as models
import prefect.server.schemas as schemas
from prefect._internal.schemas.bases import PrefectBaseModel
from prefect._internal.uuid7 import uuid7
from prefect.client.schemas.worker_channel import (
    WORKER_CHANNEL_CLOSE_POLICIES,
    WorkerChannelCloseReason,
    WorkerHeartbeatFrame,
    WorkerReadyFrame,
    WorkPoolSnapshot,
    WorkPoolSnapshotFrame,
    WorkPoolSnapshotPayload,
    validate_worker_channel_frame,
)
from prefect.logging import get_logger
from prefect.server.database import PrefectDBInterface
from prefect.server.models.workers import emit_work_pool_status_event
from prefect.server.utilities import messaging, subscriptions
from prefect.types._datetime import now

if TYPE_CHECKING:
    from prefect.server.database.orm_models import WorkPool as ORMWorkPool

logger: logging.Logger = get_logger("prefect.server.utilities.worker_channel")

WORKER_CHANNEL_SNAPSHOT_TOPIC = "work-pool-worker-channel-snapshots"
_WORKER_CHANNEL_SNAPSHOT_BUFFER_SIZE = 1
_WORKER_CHANNEL_SNAPSHOT_COALESCE_SECONDS = 0.05

WORK_POOL_FIELDS_THAT_TRIGGER_SNAPSHOTS = frozenset(
    {
        "base_job_template",
        "concurrency_limit",
        "is_paused",
        "storage_configuration",
    }
)


class WorkerChannelSnapshotInvalidation(PrefectBaseModel):
    work_pool_id: UUID
    reason: str
    work_pool_deleted: bool = False

    def targets(self, *, work_pool_id: UUID) -> bool:
        return self.work_pool_id == work_pool_id


def work_pool_update_triggers_snapshot(update_values: Mapping[str, Any]) -> bool:
    return bool(WORK_POOL_FIELDS_THAT_TRIGGER_SNAPSHOTS.intersection(update_values))


class WorkerChannelConnection:
    def __init__(
        self,
        *,
        websocket: WebSocket,
        db: PrefectDBInterface,
        work_pool_name: str,
        work_pool_id: UUID,
        consumer_id: UUID,
        worker_name: str,
    ) -> None:
        self.websocket = websocket
        self.db = db
        self.work_pool_name = work_pool_name
        self.work_pool_id = work_pool_id
        self.consumer_id = consumer_id
        self.worker_name = worker_name
        self._next_snapshot_sequence = 2
        self._snapshot_queue: asyncio.Queue[WorkerChannelSnapshotInvalidation] = (
            asyncio.Queue(maxsize=_WORKER_CHANNEL_SNAPSHOT_BUFFER_SIZE)
        )
        self._send_lock = asyncio.Lock()
        self._closed = asyncio.Event()

    async def run(
        self, ready: WorkerReadyFrame, consumer_kwargs: Mapping[str, Any]
    ) -> None:
        send_task = asyncio.create_task(self._send_loop(ready))
        receive_task = asyncio.create_task(self._receive_loop())
        fanout_task = asyncio.create_task(self._fanout_loop(consumer_kwargs))
        tasks = {send_task, receive_task, fanout_task}

        try:
            done, pending = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_COMPLETED
            )
        except asyncio.CancelledError:
            self._closed.set()
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            return
        except BaseException:
            self._closed.set()
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise

        self._closed.set()
        for task in pending:
            task.cancel()
        try:
            await asyncio.gather(*pending, return_exceptions=True)
        except asyncio.CancelledError:
            return

        for task in done:
            if task.cancelled():
                continue
            exception = task.exception()
            if exception is not None:
                raise exception

    async def close(self, close_reason: WorkerChannelCloseReason) -> None:
        if self._closed.is_set():
            return

        self._closed.set()
        async with self._send_lock:
            await close_worker_channel(self.websocket, close_reason)

    def queue_snapshot(
        self,
        invalidation: WorkerChannelSnapshotInvalidation,
    ) -> None:
        if self._closed.is_set() or not invalidation.targets(
            work_pool_id=self.work_pool_id,
        ):
            return

        while True:
            try:
                self._snapshot_queue.put_nowait(invalidation)
                return
            except asyncio.QueueFull:
                try:
                    self._snapshot_queue.get_nowait()
                except asyncio.QueueEmpty:
                    continue

    async def _fanout_loop(self, consumer_kwargs: Mapping[str, Any]) -> None:
        if "subscription" in consumer_kwargs:
            consumer_kwargs = {**consumer_kwargs, "concurrency": 1}
        consumer = messaging.create_consumer(**consumer_kwargs)

        async def handle_message(worker_channel_message: messaging.Message) -> None:
            invalidation = parse_snapshot_invalidation(worker_channel_message)
            self.queue_snapshot(invalidation)

        await consumer.run(handle_message)

    async def _send_loop(self, ready: WorkerReadyFrame) -> None:
        await self._send_frame(ready)

        while not self._closed.is_set():
            invalidation = await self._snapshot_queue.get()
            invalidation = await self._coalesce_snapshot_invalidations(invalidation)

            if invalidation.work_pool_deleted:
                await self.close(WorkerChannelCloseReason.AUTHORIZATION_FAILED)
                return

            frame = await self._build_snapshot_frame(invalidation)
            if frame is None:
                await self.close(WorkerChannelCloseReason.AUTHORIZATION_FAILED)
                return

            await self._send_frame(frame)

    async def _send_frame(
        self, frame: WorkerReadyFrame | WorkPoolSnapshotFrame
    ) -> None:
        async with self._send_lock:
            await self.websocket.send_json(frame.model_dump(mode="json"))

    async def _coalesce_snapshot_invalidations(
        self,
        invalidation: WorkerChannelSnapshotInvalidation,
    ) -> WorkerChannelSnapshotInvalidation:
        await asyncio.sleep(_WORKER_CHANNEL_SNAPSHOT_COALESCE_SECONDS)

        while True:
            try:
                invalidation = self._snapshot_queue.get_nowait()
            except asyncio.QueueEmpty:
                return invalidation

    async def _build_snapshot_frame(
        self,
        invalidation: WorkerChannelSnapshotInvalidation,
    ) -> WorkPoolSnapshotFrame | None:
        async with self.db.session_context() as session:
            work_pool = await models.workers.read_work_pool(
                session=session,
                work_pool_id=invalidation.work_pool_id,
            )
            if work_pool is None:
                return None

            payload = WorkPoolSnapshotPayload(
                snapshot_sequence=self._next_snapshot_sequence,
                reason=invalidation.reason,
                work_pool=await build_worker_channel_work_pool_snapshot(
                    session=session,
                    work_pool=work_pool,
                ),
            )

        self._next_snapshot_sequence += 1
        return WorkPoolSnapshotFrame(
            type="work_pool.snapshot.v1",
            id=uuid7(),
            sent_at=now("UTC"),
            payload=payload,
        )

    async def _receive_loop(self) -> None:
        while not self._closed.is_set():
            try:
                message = await self.websocket.receive_json()
                frame = validate_worker_channel_frame(message)
            except subscriptions.NORMAL_DISCONNECT_EXCEPTIONS:
                return
            except ValidationError:
                await self.close(WorkerChannelCloseReason.PROTOCOL_ERROR)
                return
            except ValueError:
                await self.close(WorkerChannelCloseReason.PROTOCOL_ERROR)
                return

            if not isinstance(frame, WorkerHeartbeatFrame):
                await self.close(WorkerChannelCloseReason.PROTOCOL_ERROR)
                return

            if (
                frame.payload.consumer_id != self.consumer_id
                or frame.payload.worker_name != self.worker_name
            ):
                await self.close(WorkerChannelCloseReason.PROTOCOL_ERROR)
                return

            try:
                async with self.db.session_context(begin_transaction=True) as session:
                    await _persist_worker_channel_heartbeat(
                        session=session,
                        work_pool_name=self.work_pool_name,
                        frame=frame,
                    )
            except Exception:
                logger.exception("Worker channel heartbeat persistence failed")
                await self.close(WorkerChannelCloseReason.HEARTBEAT_PERSISTENCE_FAILED)
                return


async def close_worker_channel(
    websocket: WebSocket, close_reason: WorkerChannelCloseReason
) -> None:
    policy = WORKER_CHANNEL_CLOSE_POLICIES[close_reason]
    await websocket.close(code=policy.websocket_code, reason=close_reason.value)


async def build_worker_channel_work_pool_snapshot(
    session: AsyncSession,
    work_pool: ORMWorkPool,
) -> WorkPoolSnapshot:
    work_pool_response = schemas.responses.WorkPoolResponse.model_validate(
        work_pool, from_attributes=True
    )

    if work_pool_response.concurrency_limit is not None:
        work_pool_response.active_slots = (
            await models.workers.count_work_pool_active_slots(
                session=session,
                work_pool_id=work_pool.id,
            )
        )

    return WorkPoolSnapshot.model_validate(work_pool_response.model_dump(mode="json"))


async def _persist_worker_channel_heartbeat(
    session: AsyncSession,
    work_pool_name: str,
    frame: WorkerHeartbeatFrame,
) -> None:
    work_pool = await models.workers.read_work_pool_by_name(
        session=session,
        work_pool_name=work_pool_name,
    )
    if work_pool is None:
        raise RuntimeError("Worker channel work pool no longer exists")

    await models.workers.record_worker_heartbeat(
        session=session,
        work_pool=work_pool,
        worker_name=frame.payload.worker_name,
        heartbeat_interval_seconds=frame.payload.heartbeat_interval_seconds,
        emit_status_change=emit_work_pool_status_event,
    )


async def publish_snapshot_invalidation(
    invalidation: WorkerChannelSnapshotInvalidation,
) -> None:
    async with messaging.create_publisher(
        topic=WORKER_CHANNEL_SNAPSHOT_TOPIC
    ) as publisher:
        await publisher.publish_data(
            invalidation.model_dump_json().encode(),
            attributes={
                "work_pool_id": str(invalidation.work_pool_id),
                "reason": invalidation.reason,
            },
        )


def parse_snapshot_invalidation(
    message: messaging.Message,
) -> WorkerChannelSnapshotInvalidation:
    data = message.data.encode() if isinstance(message.data, str) else message.data
    return WorkerChannelSnapshotInvalidation.model_validate_json(data)
