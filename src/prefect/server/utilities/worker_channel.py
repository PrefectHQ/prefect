from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
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
    CleanupAckFrame,
    CleanupKind,
    CleanupMessageFrame,
    CleanupOperationResultFrame,
    CleanupReleaseFrame,
    CleanupRenewFrame,
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
from prefect.server.worker_communication.cleanup_queue import (
    CleanupQueueOperation,
    CleanupQueueOperationResult,
    CleanupQueueReservation,
    WorkerCleanupQueue,
)
from prefect.types import DateTime
from prefect.types._datetime import now

if TYPE_CHECKING:
    from prefect.server.database.orm_models import WorkPool as ORMWorkPool

logger: logging.Logger = get_logger("prefect.server.utilities.worker_channel")

WORKER_CHANNEL_SNAPSHOT_TOPIC = "work-pool-worker-channel-snapshots"
_WORKER_CHANNEL_SNAPSHOT_BUFFER_SIZE = 1
_WORKER_CHANNEL_SNAPSHOT_COALESCE_SECONDS = 0.05
_WORKER_CHANNEL_CLEANUP_DISPATCH_POLL_SECONDS = 1.0

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


@dataclass(frozen=True)
class WorkerCleanupInFlight:
    message_id: UUID
    reservation_token: str
    lease_expires_at: DateTime


class WorkerCleanupConnectionRegistry:
    def __init__(self) -> None:
        self._connections_by_work_pool_id: defaultdict[
            UUID, list[WorkerChannelConnection]
        ] = defaultdict(list)
        self._dispatch_locks: defaultdict[UUID, asyncio.Lock] = defaultdict(
            asyncio.Lock
        )
        self._lock = asyncio.Lock()

    @asynccontextmanager
    async def register(
        self, connection: WorkerChannelConnection
    ) -> AsyncIterator[None]:
        async with self._lock:
            self._connections_by_work_pool_id[connection.work_pool_id].append(
                connection
            )

        try:
            yield
        finally:
            async with self._lock:
                connections = self._connections_by_work_pool_id.get(
                    connection.work_pool_id
                )
                if connections is None:
                    return
                try:
                    connections.remove(connection)
                except ValueError:
                    return
                if not connections:
                    self._connections_by_work_pool_id.pop(connection.work_pool_id, None)
                    self._dispatch_locks.pop(connection.work_pool_id, None)

    async def dispatch_available(
        self,
        *,
        work_pool_id: UUID,
        cleanup_queue: WorkerCleanupQueue,
    ) -> None:
        async with self._dispatch_locks[work_pool_id]:
            while True:
                candidates = await self._eligible_connections(work_pool_id)
                if not candidates:
                    return

                dispatched = False
                for allow_fallback_to_any_queue in (False, True):
                    for connection in candidates:
                        if await connection.dispatch_one_cleanup_message(
                            cleanup_queue=cleanup_queue,
                            allow_fallback_to_any_queue=allow_fallback_to_any_queue,
                        ):
                            dispatched = True
                            break
                    if dispatched:
                        break

                if not dispatched:
                    return

    async def _eligible_connections(
        self, work_pool_id: UUID
    ) -> tuple[WorkerChannelConnection, ...]:
        async with self._lock:
            connections = tuple(self._connections_by_work_pool_id.get(work_pool_id, ()))

        eligible = []
        for connection in connections:
            if await connection.has_cleanup_capacity():
                eligible.append(connection)
        return tuple(eligible)


WORKER_CLEANUP_CONNECTION_REGISTRY = WorkerCleanupConnectionRegistry()


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
        cleanup_queue: WorkerCleanupQueue | None = None,
        cleanup_kinds: tuple[CleanupKind, ...] = (),
        cleanup_work_queue_ids: tuple[UUID, ...] = (),
        max_cleanup_concurrency: int = 0,
        cleanup_registry: WorkerCleanupConnectionRegistry = (
            WORKER_CLEANUP_CONNECTION_REGISTRY
        ),
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
        self._ready_sent = asyncio.Event()
        self._cleanup_queue = cleanup_queue
        self._cleanup_kinds = cleanup_kinds
        self._cleanup_work_queue_ids = cleanup_work_queue_ids
        self._max_cleanup_concurrency = max_cleanup_concurrency
        self._cleanup_registry = cleanup_registry
        self._cleanup_in_flight_by_token: dict[str, WorkerCleanupInFlight] = {}
        self._cleanup_state_lock = asyncio.Lock()

    @property
    def cleanup_enabled(self) -> bool:
        return (
            self._cleanup_queue is not None
            and self._cleanup_kinds
            and self._max_cleanup_concurrency > 0
        )

    async def run(
        self, ready: WorkerReadyFrame, consumer_kwargs: Mapping[str, Any]
    ) -> None:
        if self.cleanup_enabled:
            async with self._cleanup_registry.register(self):
                await self._run(ready, consumer_kwargs)
            return

        await self._run(ready, consumer_kwargs)

    async def _run(
        self, ready: WorkerReadyFrame, consumer_kwargs: Mapping[str, Any]
    ) -> None:
        send_task = asyncio.create_task(self._send_loop(ready))
        receive_task = asyncio.create_task(self._receive_loop())
        fanout_task = asyncio.create_task(self._fanout_loop(consumer_kwargs))
        tasks = {send_task, receive_task, fanout_task}
        if self.cleanup_enabled:
            tasks.add(asyncio.create_task(self._cleanup_dispatch_loop()))

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

    async def has_cleanup_capacity(self) -> bool:
        if (
            not self.cleanup_enabled
            or self._closed.is_set()
            or not self._ready_sent.is_set()
        ):
            return False

        async with self._cleanup_state_lock:
            self._prune_expired_cleanup_reservations_locked()
            return len(self._cleanup_in_flight_by_token) < self._max_cleanup_concurrency

    async def dispatch_one_cleanup_message(
        self,
        *,
        cleanup_queue: WorkerCleanupQueue,
        allow_fallback_to_any_queue: bool,
    ) -> bool:
        if not await self.has_cleanup_capacity():
            return False

        preferred_work_queue_ids: tuple[UUID, ...] | None
        if allow_fallback_to_any_queue:
            preferred_work_queue_ids = None
        else:
            if not self._cleanup_work_queue_ids:
                return False
            preferred_work_queue_ids = self._cleanup_work_queue_ids

        reservation = await cleanup_queue.reserve(
            work_pool_id=self.work_pool_id,
            cleanup_kinds=self._cleanup_kinds,
            preferred_work_queue_ids=preferred_work_queue_ids,
            allow_fallback_to_any_queue=allow_fallback_to_any_queue,
        )
        if reservation is None:
            return False

        async with self._cleanup_state_lock:
            self._prune_expired_cleanup_reservations_locked()
            if (
                self._closed.is_set()
                or not self._ready_sent.is_set()
                or len(self._cleanup_in_flight_by_token)
                >= self._max_cleanup_concurrency
            ):
                should_release = True
            else:
                self._cleanup_in_flight_by_token[reservation.reservation_token] = (
                    WorkerCleanupInFlight(
                        message_id=reservation.message_id,
                        reservation_token=reservation.reservation_token,
                        lease_expires_at=reservation.lease_expires_at,
                    )
                )
                should_release = False

        if should_release:
            await cleanup_queue.release(
                work_pool_id=self.work_pool_id,
                message_id=reservation.message_id,
                reservation_token=reservation.reservation_token,
                reason="connection_unavailable",
            )
            return False

        try:
            await self._send_frame(_build_cleanup_message_frame(reservation))
        except subscriptions.NORMAL_DISCONNECT_EXCEPTIONS:
            await self._release_cleanup_delivery_failure(
                cleanup_queue=cleanup_queue,
                reservation=reservation,
            )
            return False
        except Exception:
            logger.exception("Worker channel cleanup message delivery failed")
            await self._release_cleanup_delivery_failure(
                cleanup_queue=cleanup_queue,
                reservation=reservation,
            )
            await self.close(WorkerChannelCloseReason.TRANSIENT_SERVER_ERROR)
            return False

        return True

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
        self._ready_sent.set()

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
        self,
        frame: (
            WorkerReadyFrame
            | WorkPoolSnapshotFrame
            | CleanupMessageFrame
            | CleanupOperationResultFrame
        ),
    ) -> None:
        async with self._send_lock:
            await self.websocket.send_json(frame.model_dump(mode="json"))

    async def _cleanup_dispatch_loop(self) -> None:
        assert self._cleanup_queue is not None
        cleanup_queue = self._cleanup_queue
        await self._ready_sent.wait()
        wakeup_sequence = await cleanup_queue.read_wakeup_sequence(self.work_pool_id)

        while not self._closed.is_set():
            await self._cleanup_registry.dispatch_available(
                work_pool_id=self.work_pool_id,
                cleanup_queue=cleanup_queue,
            )
            wakeup = await cleanup_queue.wait_for_wakeup(
                self.work_pool_id,
                after=wakeup_sequence,
                timeout=_WORKER_CHANNEL_CLEANUP_DISPATCH_POLL_SECONDS,
            )
            if wakeup is not None:
                wakeup_sequence = wakeup.sequence

    async def _release_cleanup_delivery_failure(
        self,
        *,
        cleanup_queue: WorkerCleanupQueue,
        reservation: CleanupQueueReservation,
    ) -> None:
        await self._forget_cleanup_reservation(reservation.reservation_token)
        await cleanup_queue.release(
            work_pool_id=self.work_pool_id,
            message_id=reservation.message_id,
            reservation_token=reservation.reservation_token,
            reason="delivery_failed",
        )

    async def _handle_cleanup_operation(
        self,
        frame: CleanupAckFrame | CleanupReleaseFrame | CleanupRenewFrame,
    ) -> None:
        if not self.cleanup_enabled or self._cleanup_queue is None:
            await self._send_frame(
                _build_cleanup_operation_result_frame(
                    request_frame_id=frame.id,
                    result=CleanupQueueOperationResult(
                        message_id=frame.payload.message_id,
                        operation=_cleanup_operation_from_frame(frame),
                        status="unauthorized",
                        reason="cleanup_delivery_not_accepted",
                    ),
                )
            )
            return

        cleanup_queue = self._cleanup_queue
        if isinstance(frame, CleanupAckFrame):
            result = await cleanup_queue.ack(
                work_pool_id=self.work_pool_id,
                message_id=frame.payload.message_id,
                reservation_token=frame.payload.reservation_token,
            )
        elif isinstance(frame, CleanupReleaseFrame):
            result = await cleanup_queue.release(
                work_pool_id=self.work_pool_id,
                message_id=frame.payload.message_id,
                reservation_token=frame.payload.reservation_token,
                reason=frame.payload.reason,
            )
        else:
            result = await cleanup_queue.renew(
                work_pool_id=self.work_pool_id,
                message_id=frame.payload.message_id,
                reservation_token=frame.payload.reservation_token,
            )

        freed_capacity = await self._sync_cleanup_operation_result(
            reservation_token=frame.payload.reservation_token,
            result=result,
        )
        await self._send_frame(
            _build_cleanup_operation_result_frame(
                request_frame_id=frame.id,
                result=result,
            )
        )
        if freed_capacity:
            await self._cleanup_registry.dispatch_available(
                work_pool_id=self.work_pool_id,
                cleanup_queue=cleanup_queue,
            )

    async def _sync_cleanup_operation_result(
        self,
        *,
        reservation_token: str,
        result: CleanupQueueOperationResult,
    ) -> bool:
        if result.operation == "renew" and result.status == "accepted":
            async with self._cleanup_state_lock:
                in_flight = self._cleanup_in_flight_by_token.get(reservation_token)
                if in_flight is not None and result.lease_expires_at is not None:
                    self._cleanup_in_flight_by_token[reservation_token] = (
                        WorkerCleanupInFlight(
                            message_id=in_flight.message_id,
                            reservation_token=in_flight.reservation_token,
                            lease_expires_at=result.lease_expires_at,
                        )
                    )
            return False

        return await self._forget_cleanup_reservation(reservation_token)

    async def _forget_cleanup_reservation(self, reservation_token: str) -> bool:
        async with self._cleanup_state_lock:
            return (
                self._cleanup_in_flight_by_token.pop(reservation_token, None)
                is not None
            )

    def _prune_expired_cleanup_reservations_locked(self) -> None:
        current_time = now("UTC")
        expired_tokens = [
            token
            for token, in_flight in self._cleanup_in_flight_by_token.items()
            if in_flight.lease_expires_at <= current_time
        ]
        for token in expired_tokens:
            self._cleanup_in_flight_by_token.pop(token, None)

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

            if isinstance(frame, WorkerHeartbeatFrame):
                if (
                    frame.payload.consumer_id != self.consumer_id
                    or frame.payload.worker_name != self.worker_name
                ):
                    await self.close(WorkerChannelCloseReason.PROTOCOL_ERROR)
                    return

                try:
                    async with self.db.session_context(
                        begin_transaction=True
                    ) as session:
                        await _persist_worker_channel_heartbeat(
                            session=session,
                            work_pool_name=self.work_pool_name,
                            frame=frame,
                        )
                except Exception:
                    logger.exception("Worker channel heartbeat persistence failed")
                    await self.close(
                        WorkerChannelCloseReason.HEARTBEAT_PERSISTENCE_FAILED
                    )
                    return
                continue

            if isinstance(
                frame, (CleanupAckFrame, CleanupReleaseFrame, CleanupRenewFrame)
            ):
                await self._handle_cleanup_operation(frame)
                continue

            await self.close(WorkerChannelCloseReason.PROTOCOL_ERROR)
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


def _build_cleanup_message_frame(
    reservation: CleanupQueueReservation,
) -> CleanupMessageFrame:
    return CleanupMessageFrame(
        type="cleanup.message.v1",
        id=uuid7(),
        sent_at=now("UTC"),
        payload={
            "message_id": reservation.message_id,
            "kind": reservation.kind,
            "reservation_token": reservation.reservation_token,
            "lease_expires_at": reservation.lease_expires_at,
            "delivery_count": reservation.delivery_count,
            "work_queue_id": reservation.work_queue_id,
            "target": reservation.target,
            "data": reservation.data,
        },
    )


def _build_cleanup_operation_result_frame(
    *,
    request_frame_id: UUID,
    result: CleanupQueueOperationResult,
) -> CleanupOperationResultFrame:
    return CleanupOperationResultFrame(
        type="cleanup.operation_result.v1",
        id=uuid7(),
        sent_at=now("UTC"),
        payload={
            "request_frame_id": request_frame_id,
            "message_id": result.message_id,
            "operation": result.operation,
            "status": result.status,
            "lease_expires_at": result.lease_expires_at,
            "reason": result.reason,
            "detail": None,
        },
    )


def _cleanup_operation_from_frame(
    frame: CleanupAckFrame | CleanupReleaseFrame | CleanupRenewFrame,
) -> CleanupQueueOperation:
    if isinstance(frame, CleanupAckFrame):
        return "ack"
    if isinstance(frame, CleanupReleaseFrame):
        return "release"
    return "renew"


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
