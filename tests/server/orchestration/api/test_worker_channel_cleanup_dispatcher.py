import asyncio
import threading
import time
import uuid
from collections.abc import Iterable, Mapping
from datetime import timedelta, timezone
from typing import Any
from uuid import UUID

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import prefect.server.api.workers as workers_api
from prefect._internal.uuid7 import uuid7
from prefect.client.schemas.worker_channel import (
    CANCELLING_TIMEOUT_TEARDOWN,
    CLEANUP_DELIVERY_CAPABILITY,
    PENDING_CLAIM_TEARDOWN,
    WORK_POOL_SNAPSHOT_CAPABILITY,
    WORK_POOL_WORKER_CHANNEL_VERSION,
    WORKER_HEARTBEAT_CAPABILITY,
    CleanupAckFrame,
    CleanupKind,
    CleanupMessageFrame,
    CleanupOperationResultFrame,
    CleanupReleaseFrame,
    WorkerReadyFrame,
)
from prefect.server.events.clients import AssertingEventsClient
from prefect.server.utilities import worker_channel as worker_channel_utils
from prefect.server.worker_communication.cleanup_queue import (
    CleanupQueueDeadLetter,
    CleanupQueueLeaseExpiryResult,
    CleanupQueueMessage,
    CleanupQueueOperation,
    CleanupQueueOperationResult,
    CleanupQueueReservation,
    CleanupQueueWakeup,
    WorkerCleanupQueue,
)
from prefect.types._datetime import now

pytestmark = pytest.mark.clear_db


@pytest.fixture(autouse=True)
def patch_events_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "prefect.server.models.work_queues.PrefectServerEventsClient",
        AssertingEventsClient,
    )
    monkeypatch.setattr(
        "prefect.server.models.workers.PrefectServerEventsClient",
        AssertingEventsClient,
    )


class FakeWorkerCleanupQueue(WorkerCleanupQueue):
    def __init__(self, lease_seconds: float = 30.0) -> None:
        self._lease_seconds = lease_seconds
        self._messages: dict[UUID, CleanupQueueMessage] = {}
        self._reservations: dict[UUID, CleanupQueueReservation] = {}
        self._wakeup_sequences: dict[UUID, int] = {}
        self._wait_for_wakeup_calls = 0
        self._active_wait_for_wakeup_calls = 0
        self._max_active_wait_for_wakeup_calls = 0
        self._lock = threading.Lock()

    def add_message(
        self,
        *,
        work_pool_id: UUID,
        kind: CleanupKind = CANCELLING_TIMEOUT_TEARDOWN,
        work_queue_id: UUID | None = None,
        message_id: UUID | None = None,
    ) -> CleanupQueueMessage:
        current_time = now("UTC")
        message = CleanupQueueMessage(
            message_id=message_id or uuid.uuid4(),
            idempotency_key=str(uuid.uuid4()),
            work_pool_id=work_pool_id,
            work_queue_id=work_queue_id,
            kind=kind,
            target={"flow_run_id": uuid.uuid4()},
            data={},
            created_at=current_time,
            updated_at=current_time,
        )
        with self._lock:
            self._messages[message.message_id] = message
            self._wake_locked(work_pool_id)
        return message

    def active_reservation_count(self) -> int:
        with self._lock:
            return len(self._reservations)

    def active_message_count(self) -> int:
        with self._lock:
            return len(self._messages)

    def wait_for_wakeup_call_count(self) -> int:
        with self._lock:
            return self._wait_for_wakeup_calls

    def max_active_wait_for_wakeup_calls(self) -> int:
        with self._lock:
            return self._max_active_wait_for_wakeup_calls

    async def enqueue(
        self,
        *,
        message_id: UUID,
        idempotency_key: str,
        work_pool_id: UUID,
        kind: CleanupKind,
        target: Mapping[str, Any],
        data: Mapping[str, Any] | None = None,
        work_queue_id: UUID | None = None,
    ) -> CleanupQueueMessage:
        raise NotImplementedError

    async def reserve(
        self,
        *,
        work_pool_id: UUID,
        cleanup_kinds: Iterable[CleanupKind] | None = None,
        preferred_work_queue_ids: Iterable[UUID] | None = None,
        allow_fallback_to_any_queue: bool = True,
    ) -> CleanupQueueReservation | None:
        cleanup_kind_filter = set(cleanup_kinds) if cleanup_kinds is not None else None
        queue_preference_passes = self._queue_preference_passes(
            preferred_work_queue_ids=preferred_work_queue_ids,
            allow_fallback_to_any_queue=allow_fallback_to_any_queue,
        )

        with self._lock:
            self._expire_due_reservations_locked()
            for queue_filter in queue_preference_passes:
                for message in tuple(self._messages.values()):
                    if message.work_pool_id != work_pool_id:
                        continue
                    if message.message_id in self._reservations:
                        continue
                    if (
                        cleanup_kind_filter is not None
                        and message.kind not in cleanup_kind_filter
                    ):
                        continue
                    if (
                        queue_filter is not None
                        and message.work_queue_id not in queue_filter
                    ):
                        continue

                    current_time = now("UTC")
                    updated_message = message.model_copy(
                        update={
                            "delivery_count": message.delivery_count + 1,
                            "updated_at": current_time,
                        }
                    )
                    reservation = CleanupQueueReservation(
                        **updated_message.model_dump(),
                        reservation_token=(
                            f"token-{message.message_id}-{updated_message.delivery_count}"
                        ),
                        lease_expires_at=current_time
                        + timedelta(seconds=self._lease_seconds),
                    )
                    self._messages[message.message_id] = updated_message
                    self._reservations[message.message_id] = reservation
                    return reservation

        return None

    async def ack(
        self,
        *,
        work_pool_id: UUID,
        message_id: UUID,
        reservation_token: str,
    ) -> CleanupQueueOperationResult:
        with self._lock:
            validation = self._validate_current_reservation_locked(
                operation="ack",
                work_pool_id=work_pool_id,
                message_id=message_id,
                reservation_token=reservation_token,
            )
            if validation is not None:
                return validation

            self._messages.pop(message_id)
            self._reservations.pop(message_id)
            return CleanupQueueOperationResult(
                message_id=message_id,
                operation="ack",
                status="accepted",
            )

    async def release(
        self,
        *,
        work_pool_id: UUID,
        message_id: UUID,
        reservation_token: str,
        reason: str,
    ) -> CleanupQueueOperationResult:
        with self._lock:
            validation = self._validate_current_reservation_locked(
                operation="release",
                work_pool_id=work_pool_id,
                message_id=message_id,
                reservation_token=reservation_token,
            )
            if validation is not None:
                return validation

            self._reservations.pop(message_id)
            self._wake_locked(work_pool_id)
            return CleanupQueueOperationResult(
                message_id=message_id,
                operation="release",
                status="accepted",
            )

    async def renew(
        self,
        *,
        work_pool_id: UUID,
        message_id: UUID,
        reservation_token: str,
    ) -> CleanupQueueOperationResult:
        with self._lock:
            validation = self._validate_current_reservation_locked(
                operation="renew",
                work_pool_id=work_pool_id,
                message_id=message_id,
                reservation_token=reservation_token,
            )
            if validation is not None:
                return validation

            reservation = self._reservations[message_id]
            renewed = reservation.model_copy(
                update={
                    "lease_expires_at": now("UTC")
                    + timedelta(seconds=self._lease_seconds)
                }
            )
            self._reservations[message_id] = renewed
            return CleanupQueueOperationResult(
                message_id=message_id,
                operation="renew",
                status="accepted",
                lease_expires_at=renewed.lease_expires_at,
            )

    async def expire_leases(
        self,
        *,
        limit: int = 100,
        work_pool_id: UUID | None = None,
    ) -> CleanupQueueLeaseExpiryResult:
        with self._lock:
            self._expire_due_reservations_locked(work_pool_id=work_pool_id)
        return CleanupQueueLeaseExpiryResult()

    async def read_message(
        self, *, work_pool_id: UUID, message_id: UUID
    ) -> CleanupQueueMessage | None:
        with self._lock:
            message = self._messages.get(message_id)
            if message is None or message.work_pool_id != work_pool_id:
                return None
            return message.model_copy(deep=True)

    async def read_dead_letter(
        self, *, work_pool_id: UUID, message_id: UUID
    ) -> CleanupQueueDeadLetter | None:
        return None

    async def wake_dispatchers(self, work_pool_id: UUID) -> CleanupQueueWakeup:
        with self._lock:
            return self._wake_locked(work_pool_id)

    async def read_wakeup_sequence(self, work_pool_id: UUID) -> int:
        with self._lock:
            return self._wakeup_sequences.get(work_pool_id, 0)

    async def wait_for_wakeup(
        self,
        work_pool_id: UUID,
        *,
        after: int = 0,
        timeout: float | None = None,
    ) -> CleanupQueueWakeup | None:
        with self._lock:
            self._wait_for_wakeup_calls += 1
            self._active_wait_for_wakeup_calls += 1
            self._max_active_wait_for_wakeup_calls = max(
                self._max_active_wait_for_wakeup_calls,
                self._active_wait_for_wakeup_calls,
            )
        deadline = None if timeout is None else time.monotonic() + timeout
        try:
            while True:
                with self._lock:
                    sequence = self._wakeup_sequences.get(work_pool_id, 0)
                    if sequence > after:
                        return CleanupQueueWakeup(
                            work_pool_id=work_pool_id, sequence=sequence
                        )

                if deadline is not None and time.monotonic() >= deadline:
                    return None
                await asyncio.sleep(0.01)
        finally:
            with self._lock:
                self._active_wait_for_wakeup_calls -= 1

    def _validate_current_reservation_locked(
        self,
        *,
        operation: CleanupQueueOperation,
        work_pool_id: UUID,
        message_id: UUID,
        reservation_token: str,
    ) -> CleanupQueueOperationResult | None:
        message = self._messages.get(message_id)
        if message is None:
            return CleanupQueueOperationResult(
                message_id=message_id,
                operation=operation,
                status="not_found",
                reason="message_not_found",
            )
        if message.work_pool_id != work_pool_id:
            return CleanupQueueOperationResult(
                message_id=message_id,
                operation=operation,
                status="unauthorized",
                reason="work_pool_mismatch",
            )

        reservation = self._reservations.get(message_id)
        if reservation is None:
            return CleanupQueueOperationResult(
                message_id=message_id,
                operation=operation,
                status="not_current",
                reason="no_active_reservation",
            )
        if reservation.reservation_token != reservation_token:
            return CleanupQueueOperationResult(
                message_id=message_id,
                operation=operation,
                status="invalid_token",
                reason="reservation_token_mismatch",
            )
        if reservation.lease_expires_at <= now("UTC"):
            self._reservations.pop(message_id)
            self._wake_locked(work_pool_id)
            return CleanupQueueOperationResult(
                message_id=message_id,
                operation=operation,
                status="expired",
                reason="lease_expired",
            )

        return None

    def _expire_due_reservations_locked(
        self, *, work_pool_id: UUID | None = None
    ) -> None:
        current_time = now("UTC")
        for message_id, reservation in tuple(self._reservations.items()):
            if work_pool_id is not None and reservation.work_pool_id != work_pool_id:
                continue
            if reservation.lease_expires_at <= current_time:
                self._reservations.pop(message_id)
                self._wake_locked(reservation.work_pool_id)

    def _wake_locked(self, work_pool_id: UUID) -> CleanupQueueWakeup:
        sequence = self._wakeup_sequences.get(work_pool_id, 0) + 1
        self._wakeup_sequences[work_pool_id] = sequence
        return CleanupQueueWakeup(work_pool_id=work_pool_id, sequence=sequence)

    @staticmethod
    def _queue_preference_passes(
        *,
        preferred_work_queue_ids: Iterable[UUID] | None,
        allow_fallback_to_any_queue: bool,
    ) -> tuple[set[UUID] | None, ...]:
        if preferred_work_queue_ids is None:
            return (None,)

        preferred_queue_filter = set(preferred_work_queue_ids)
        if allow_fallback_to_any_queue:
            return (preferred_queue_filter, None)
        return (preferred_queue_filter,)


@pytest.fixture
def cleanup_queue(monkeypatch: pytest.MonkeyPatch) -> FakeWorkerCleanupQueue:
    queue = FakeWorkerCleanupQueue(lease_seconds=0.05)
    monkeypatch.setattr(workers_api, "get_worker_cleanup_queue", lambda: queue)
    monkeypatch.setattr(
        worker_channel_utils,
        "_WORKER_CHANNEL_CLEANUP_DISPATCH_POLL_SECONDS",
        0.05,
    )
    return queue


def _worker_channel_frame(frame_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": frame_type,
        "id": str(uuid7()),
        "sent_at": now("UTC").astimezone(timezone.utc).isoformat(),
        "payload": payload,
    }


def _worker_hello_frame(**payload_overrides: Any) -> dict[str, Any]:
    payload = {
        "consumer_id": str(uuid.uuid4()),
        "worker_name": "test-worker",
        "worker_type": "process",
        "heartbeat_interval_seconds": 30,
        "supported_channel_versions": [WORK_POOL_WORKER_CHANNEL_VERSION],
        "requested_capabilities": [
            WORKER_HEARTBEAT_CAPABILITY,
            WORK_POOL_SNAPSHOT_CAPABILITY,
        ],
        "work_queue_names": [],
        "handled_cleanup_kinds": [],
        "max_cleanup_concurrency": 0,
        "create_pool_if_not_found": False,
        "default_base_job_template": {},
        "worker_metadata": None,
    }
    payload.update(payload_overrides)
    return _worker_channel_frame("worker.hello.v1", payload)


def _cleanup_worker_hello_frame(**payload_overrides: Any) -> dict[str, Any]:
    payload = {
        "requested_capabilities": [
            WORKER_HEARTBEAT_CAPABILITY,
            WORK_POOL_SNAPSHOT_CAPABILITY,
            CLEANUP_DELIVERY_CAPABILITY,
        ],
        "handled_cleanup_kinds": [CANCELLING_TIMEOUT_TEARDOWN],
        "max_cleanup_concurrency": 1,
    }
    payload.update(payload_overrides)
    return _worker_hello_frame(**payload)


def _cleanup_ack_frame(*, message_id: UUID, reservation_token: str) -> dict[str, Any]:
    return _worker_channel_frame(
        "cleanup.ack.v1",
        {
            "message_id": str(message_id),
            "reservation_token": reservation_token,
        },
    )


def _cleanup_release_frame(
    *, message_id: UUID, reservation_token: str, reason: str = "cannot_act"
) -> dict[str, Any]:
    return _worker_channel_frame(
        "cleanup.release.v1",
        {
            "message_id": str(message_id),
            "reservation_token": reservation_token,
            "reason": reason,
        },
    )


def _cleanup_renew_frame(*, message_id: UUID, reservation_token: str) -> dict[str, Any]:
    return _worker_channel_frame(
        "cleanup.renew.v1",
        {
            "message_id": str(message_id),
            "reservation_token": reservation_token,
        },
    )


def _authenticate_worker_channel(websocket) -> None:
    websocket.send_json({"type": "auth", "token": None})
    assert websocket.receive_json() == {"type": "auth_success"}


def _connect_worker_channel(test_client: TestClient, work_pool_name: str):
    return test_client.websocket_connect(
        f"/api/work_pools/{work_pool_name}/workers/connect",
        subprotocols=("prefect",),
    )


class RecordingWebSocket:
    def __init__(self) -> None:
        self.sent_json: list[dict[str, Any]] = []

    async def send_json(self, payload: dict[str, Any]) -> None:
        self.sent_json.append(payload)


class DisconnectingWebSocket(RecordingWebSocket):
    async def send_json(self, payload: dict[str, Any]) -> None:
        self.sent_json.append(payload)
        raise WebSocketDisconnect


class CancellingWebSocket(RecordingWebSocket):
    async def send_json(self, payload: dict[str, Any]) -> None:
        self.sent_json.append(payload)
        raise asyncio.CancelledError


class ErrorAckCleanupQueue(FakeWorkerCleanupQueue):
    async def ack(
        self,
        *,
        work_pool_id: UUID,
        message_id: UUID,
        reservation_token: str,
    ) -> CleanupQueueOperationResult:
        return CleanupQueueOperationResult(
            message_id=message_id,
            operation="ack",
            status="error",
            reason="backend_unavailable",
        )


class TestWorkerCleanupConnectionRegistry:
    async def test_registered_connection_is_ineligible_until_ready_is_sent(
        self, work_pool, cleanup_queue: FakeWorkerCleanupQueue
    ):
        cleanup_queue.add_message(work_pool_id=work_pool.id)
        websocket = RecordingWebSocket()
        registry = worker_channel_utils.WorkerCleanupConnectionRegistry()
        connection = worker_channel_utils.WorkerChannelConnection(
            websocket=websocket,
            db=object(),
            work_pool_name=work_pool.name,
            work_pool_id=work_pool.id,
            consumer_id=uuid.uuid4(),
            worker_name="test-worker",
            cleanup_queue=cleanup_queue,
            cleanup_kinds=(CANCELLING_TIMEOUT_TEARDOWN,),
            max_cleanup_concurrency=1,
            cleanup_registry=registry,
        )

        async with registry.register(connection):
            await registry.dispatch_available(
                work_pool_id=work_pool.id,
                cleanup_queue=cleanup_queue,
            )

            assert cleanup_queue.active_reservation_count() == 0
            assert websocket.sent_json == []

            connection._ready_sent.set()
            await registry.dispatch_available(
                work_pool_id=work_pool.id,
                cleanup_queue=cleanup_queue,
            )

        assert cleanup_queue.active_reservation_count() == 1
        assert websocket.sent_json[0]["type"] == "cleanup.message.v1"

    async def test_disconnect_during_cleanup_send_removes_connection_from_dispatch(
        self, work_pool
    ):
        cleanup_queue = FakeWorkerCleanupQueue()
        message = cleanup_queue.add_message(work_pool_id=work_pool.id)
        websocket = DisconnectingWebSocket()
        registry = worker_channel_utils.WorkerCleanupConnectionRegistry()
        connection = worker_channel_utils.WorkerChannelConnection(
            websocket=websocket,
            db=object(),
            work_pool_name=work_pool.name,
            work_pool_id=work_pool.id,
            consumer_id=uuid.uuid4(),
            worker_name="test-worker",
            cleanup_queue=cleanup_queue,
            cleanup_kinds=(CANCELLING_TIMEOUT_TEARDOWN,),
            max_cleanup_concurrency=1,
            cleanup_registry=registry,
        )
        connection._ready_sent.set()

        async with registry.register(connection):
            await registry.dispatch_available(
                work_pool_id=work_pool.id,
                cleanup_queue=cleanup_queue,
            )
            await registry.dispatch_available(
                work_pool_id=work_pool.id,
                cleanup_queue=cleanup_queue,
            )

        stored = await cleanup_queue.read_message(
            work_pool_id=work_pool.id,
            message_id=message.message_id,
        )
        assert stored is not None
        assert stored.delivery_count == 1
        assert cleanup_queue.active_reservation_count() == 0
        assert len(websocket.sent_json) == 1

    async def test_cleanup_send_cancellation_releases_reserved_message(self, work_pool):
        cleanup_queue = FakeWorkerCleanupQueue()
        message = cleanup_queue.add_message(work_pool_id=work_pool.id)
        websocket = CancellingWebSocket()
        registry = worker_channel_utils.WorkerCleanupConnectionRegistry()
        connection = worker_channel_utils.WorkerChannelConnection(
            websocket=websocket,
            db=object(),
            work_pool_name=work_pool.name,
            work_pool_id=work_pool.id,
            consumer_id=uuid.uuid4(),
            worker_name="test-worker",
            cleanup_queue=cleanup_queue,
            cleanup_kinds=(CANCELLING_TIMEOUT_TEARDOWN,),
            max_cleanup_concurrency=1,
            cleanup_registry=registry,
        )
        connection._ready_sent.set()

        async with registry.register(connection):
            with pytest.raises(asyncio.CancelledError):
                await registry.dispatch_available(
                    work_pool_id=work_pool.id,
                    cleanup_queue=cleanup_queue,
                )

            assert cleanup_queue.active_reservation_count() == 0
            assert registry._cleanup_in_flight_by_worker == {}

        stored = await cleanup_queue.read_message(
            work_pool_id=work_pool.id,
            message_id=message.message_id,
        )
        assert stored is not None
        assert stored.delivery_count == 1
        assert len(websocket.sent_json) == 1

    async def test_retryable_operation_error_keeps_cleanup_capacity_in_use(
        self, work_pool
    ):
        cleanup_queue = ErrorAckCleanupQueue()
        first = cleanup_queue.add_message(work_pool_id=work_pool.id)
        second = cleanup_queue.add_message(work_pool_id=work_pool.id)
        websocket = RecordingWebSocket()
        registry = worker_channel_utils.WorkerCleanupConnectionRegistry()
        connection = worker_channel_utils.WorkerChannelConnection(
            websocket=websocket,
            db=object(),
            work_pool_name=work_pool.name,
            work_pool_id=work_pool.id,
            consumer_id=uuid.uuid4(),
            worker_name="test-worker",
            cleanup_queue=cleanup_queue,
            cleanup_kinds=(CANCELLING_TIMEOUT_TEARDOWN,),
            max_cleanup_concurrency=1,
            cleanup_registry=registry,
        )
        connection._ready_sent.set()

        async with registry.register(connection):
            await registry.dispatch_available(
                work_pool_id=work_pool.id,
                cleanup_queue=cleanup_queue,
            )
            first_cleanup = CleanupMessageFrame.model_validate(websocket.sent_json[0])

            await connection._handle_cleanup_operation(
                CleanupAckFrame.model_validate(
                    _cleanup_ack_frame(
                        message_id=first_cleanup.payload.message_id,
                        reservation_token=first_cleanup.payload.reservation_token,
                    )
                )
            )
            await registry.dispatch_available(
                work_pool_id=work_pool.id,
                cleanup_queue=cleanup_queue,
            )

        cleanup_messages = [
            frame
            for frame in websocket.sent_json
            if frame["type"] == "cleanup.message.v1"
        ]
        operation_results = [
            frame
            for frame in websocket.sent_json
            if frame["type"] == "cleanup.operation_result.v1"
        ]
        assert first_cleanup.payload.message_id == first.message_id
        assert second.message_id not in {
            CleanupMessageFrame.model_validate(frame).payload.message_id
            for frame in cleanup_messages
        }
        assert len(cleanup_messages) == 1
        assert operation_results[0]["payload"]["status"] == "error"

    async def test_release_redelivery_prefers_another_eligible_worker(self, work_pool):
        cleanup_queue = FakeWorkerCleanupQueue()
        message = cleanup_queue.add_message(work_pool_id=work_pool.id)
        registry = worker_channel_utils.WorkerCleanupConnectionRegistry()
        first_websocket = RecordingWebSocket()
        second_websocket = RecordingWebSocket()
        first_connection = worker_channel_utils.WorkerChannelConnection(
            websocket=first_websocket,
            db=object(),
            work_pool_name=work_pool.name,
            work_pool_id=work_pool.id,
            consumer_id=uuid.uuid4(),
            worker_name="worker-1",
            cleanup_queue=cleanup_queue,
            cleanup_kinds=(CANCELLING_TIMEOUT_TEARDOWN,),
            max_cleanup_concurrency=1,
            cleanup_registry=registry,
        )
        second_connection = worker_channel_utils.WorkerChannelConnection(
            websocket=second_websocket,
            db=object(),
            work_pool_name=work_pool.name,
            work_pool_id=work_pool.id,
            consumer_id=uuid.uuid4(),
            worker_name="worker-2",
            cleanup_queue=cleanup_queue,
            cleanup_kinds=(CANCELLING_TIMEOUT_TEARDOWN,),
            max_cleanup_concurrency=1,
            cleanup_registry=registry,
        )

        async with registry.register(first_connection):
            async with registry.register(second_connection):
                first_connection._ready_sent.set()
                second_connection._ready_sent.set()

                await registry.dispatch_available(
                    work_pool_id=work_pool.id,
                    cleanup_queue=cleanup_queue,
                )
                first_cleanup = CleanupMessageFrame.model_validate(
                    first_websocket.sent_json[0]
                )

                await first_connection._handle_cleanup_operation(
                    CleanupReleaseFrame.model_validate(
                        _cleanup_release_frame(
                            message_id=first_cleanup.payload.message_id,
                            reservation_token=first_cleanup.payload.reservation_token,
                        )
                    )
                )

        first_cleanup_messages = [
            frame
            for frame in first_websocket.sent_json
            if frame["type"] == "cleanup.message.v1"
        ]
        first_operation_results = [
            frame
            for frame in first_websocket.sent_json
            if frame["type"] == "cleanup.operation_result.v1"
        ]
        second_cleanup_messages = [
            CleanupMessageFrame.model_validate(frame)
            for frame in second_websocket.sent_json
            if frame["type"] == "cleanup.message.v1"
        ]
        assert len(first_cleanup_messages) == 1
        assert first_operation_results[0]["payload"]["status"] == "accepted"
        assert [frame.payload.message_id for frame in second_cleanup_messages] == [
            message.message_id
        ]
        assert second_cleanup_messages[0].payload.reservation_token != (
            first_cleanup.payload.reservation_token
        )

    async def test_mismatched_cleanup_result_keeps_capacity_in_use(self, work_pool):
        cleanup_queue = FakeWorkerCleanupQueue()
        cleanup_queue.add_message(work_pool_id=work_pool.id)
        cleanup_queue.add_message(work_pool_id=work_pool.id)
        third = cleanup_queue.add_message(work_pool_id=work_pool.id)
        websocket = RecordingWebSocket()
        registry = worker_channel_utils.WorkerCleanupConnectionRegistry()
        connection = worker_channel_utils.WorkerChannelConnection(
            websocket=websocket,
            db=object(),
            work_pool_name=work_pool.name,
            work_pool_id=work_pool.id,
            consumer_id=uuid.uuid4(),
            worker_name="test-worker",
            cleanup_queue=cleanup_queue,
            cleanup_kinds=(CANCELLING_TIMEOUT_TEARDOWN,),
            max_cleanup_concurrency=2,
            cleanup_registry=registry,
        )
        connection._ready_sent.set()

        async with registry.register(connection):
            await registry.dispatch_available(
                work_pool_id=work_pool.id,
                cleanup_queue=cleanup_queue,
            )
            first_cleanup = CleanupMessageFrame.model_validate(websocket.sent_json[0])
            second_cleanup = CleanupMessageFrame.model_validate(websocket.sent_json[1])

            await connection._handle_cleanup_operation(
                CleanupAckFrame.model_validate(
                    _cleanup_ack_frame(
                        message_id=second_cleanup.payload.message_id,
                        reservation_token=first_cleanup.payload.reservation_token,
                    )
                )
            )

        cleanup_messages = [
            CleanupMessageFrame.model_validate(frame)
            for frame in websocket.sent_json
            if frame["type"] == "cleanup.message.v1"
        ]
        operation_results = [
            frame
            for frame in websocket.sent_json
            if frame["type"] == "cleanup.operation_result.v1"
        ]
        assert len(cleanup_messages) == 2
        assert third.message_id not in {
            message.payload.message_id for message in cleanup_messages
        }
        assert cleanup_queue.active_reservation_count() == 2
        assert operation_results[0]["payload"]["status"] == "invalid_token"

    async def test_reconnect_preserves_in_flight_cleanup_capacity(self, work_pool):
        cleanup_queue = FakeWorkerCleanupQueue()
        first = cleanup_queue.add_message(work_pool_id=work_pool.id)
        second = cleanup_queue.add_message(work_pool_id=work_pool.id)
        registry = worker_channel_utils.WorkerCleanupConnectionRegistry()
        consumer_id = uuid.uuid4()

        first_websocket = RecordingWebSocket()
        first_connection = worker_channel_utils.WorkerChannelConnection(
            websocket=first_websocket,
            db=object(),
            work_pool_name=work_pool.name,
            work_pool_id=work_pool.id,
            consumer_id=consumer_id,
            worker_name="test-worker",
            cleanup_queue=cleanup_queue,
            cleanup_kinds=(CANCELLING_TIMEOUT_TEARDOWN,),
            max_cleanup_concurrency=1,
            cleanup_registry=registry,
        )
        first_connection._ready_sent.set()

        async with registry.register(first_connection):
            await registry.dispatch_available(
                work_pool_id=work_pool.id,
                cleanup_queue=cleanup_queue,
            )

        first_cleanup = CleanupMessageFrame.model_validate(first_websocket.sent_json[0])

        second_websocket = RecordingWebSocket()
        second_connection = worker_channel_utils.WorkerChannelConnection(
            websocket=second_websocket,
            db=object(),
            work_pool_name=work_pool.name,
            work_pool_id=work_pool.id,
            consumer_id=consumer_id,
            worker_name="test-worker",
            cleanup_queue=cleanup_queue,
            cleanup_kinds=(CANCELLING_TIMEOUT_TEARDOWN,),
            max_cleanup_concurrency=1,
            cleanup_registry=registry,
        )
        second_connection._ready_sent.set()

        async with registry.register(second_connection):
            await registry.dispatch_available(
                work_pool_id=work_pool.id,
                cleanup_queue=cleanup_queue,
            )
            assert second_websocket.sent_json == []

            await second_connection._handle_cleanup_operation(
                CleanupAckFrame.model_validate(
                    _cleanup_ack_frame(
                        message_id=first_cleanup.payload.message_id,
                        reservation_token=first_cleanup.payload.reservation_token,
                    )
                )
            )

        cleanup_messages = [
            CleanupMessageFrame.model_validate(frame)
            for frame in second_websocket.sent_json
            if frame["type"] == "cleanup.message.v1"
        ]
        assert first_cleanup.payload.message_id == first.message_id
        assert [message.payload.message_id for message in cleanup_messages] == [
            second.message_id
        ]

    async def test_register_prunes_expired_in_flight_for_abandoned_worker(
        self, work_pool
    ):
        cleanup_queue = FakeWorkerCleanupQueue()
        registry = worker_channel_utils.WorkerCleanupConnectionRegistry()
        abandoned_connection = worker_channel_utils.WorkerChannelConnection(
            websocket=RecordingWebSocket(),
            db=object(),
            work_pool_name=work_pool.name,
            work_pool_id=work_pool.id,
            consumer_id=uuid.uuid4(),
            worker_name="abandoned-worker",
            cleanup_queue=cleanup_queue,
            cleanup_kinds=(CANCELLING_TIMEOUT_TEARDOWN,),
            max_cleanup_concurrency=1,
            cleanup_registry=registry,
        )
        assert await registry.track_cleanup_reservation(
            abandoned_connection,
            worker_channel_utils.WorkerCleanupInFlight(
                message_id=uuid.uuid4(),
                reservation_token="expired-token",
                lease_expires_at=now("UTC") - timedelta(seconds=1),
            ),
            max_cleanup_concurrency=1,
        )

        new_connection = worker_channel_utils.WorkerChannelConnection(
            websocket=RecordingWebSocket(),
            db=object(),
            work_pool_name=work_pool.name,
            work_pool_id=work_pool.id,
            consumer_id=uuid.uuid4(),
            worker_name="new-worker",
            cleanup_queue=cleanup_queue,
            cleanup_kinds=(CANCELLING_TIMEOUT_TEARDOWN,),
            max_cleanup_concurrency=1,
            cleanup_registry=registry,
        )

        async with registry.register(new_connection):
            assert registry._cleanup_in_flight_by_worker == {}


class TestWorkerChannelCleanupDispatcher:
    async def test_cleanup_capability_is_accepted_for_capable_workers(
        self, test_client: TestClient, work_pool, cleanup_queue: FakeWorkerCleanupQueue
    ):
        with _connect_worker_channel(test_client, work_pool.name) as websocket:
            _authenticate_worker_channel(websocket)
            websocket.send_json(_cleanup_worker_hello_frame(max_cleanup_concurrency=2))

            ready = WorkerReadyFrame.model_validate(websocket.receive_json())

        assert CLEANUP_DELIVERY_CAPABILITY in ready.payload.accepted_capabilities
        assert ready.payload.rejected_capabilities == []
        assert ready.payload.effective_max_cleanup_concurrency == 2

    async def test_cleanup_capability_is_rejected_without_worker_capacity(
        self, test_client: TestClient, work_pool, cleanup_queue: FakeWorkerCleanupQueue
    ):
        with _connect_worker_channel(test_client, work_pool.name) as websocket:
            _authenticate_worker_channel(websocket)
            websocket.send_json(
                _worker_hello_frame(
                    requested_capabilities=[
                        WORKER_HEARTBEAT_CAPABILITY,
                        WORK_POOL_SNAPSHOT_CAPABILITY,
                        CLEANUP_DELIVERY_CAPABILITY,
                    ],
                    handled_cleanup_kinds=[CANCELLING_TIMEOUT_TEARDOWN],
                    max_cleanup_concurrency=0,
                )
            )

            ready = WorkerReadyFrame.model_validate(websocket.receive_json())

        assert CLEANUP_DELIVERY_CAPABILITY not in ready.payload.accepted_capabilities
        assert ready.payload.rejected_capabilities == [CLEANUP_DELIVERY_CAPABILITY]
        assert ready.payload.effective_max_cleanup_concurrency == 0

    def test_idle_cleanup_workers_share_one_dispatcher(
        self,
        test_client: TestClient,
        work_pool,
        cleanup_queue: FakeWorkerCleanupQueue,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.setattr(
            worker_channel_utils,
            "_WORKER_CHANNEL_CLEANUP_DISPATCH_POLL_SECONDS",
            5.0,
        )

        with _connect_worker_channel(test_client, work_pool.name) as first_websocket:
            _authenticate_worker_channel(first_websocket)
            first_websocket.send_json(
                _cleanup_worker_hello_frame(worker_name="worker-1")
            )
            WorkerReadyFrame.model_validate(first_websocket.receive_json())

            with _connect_worker_channel(
                test_client, work_pool.name
            ) as second_websocket:
                _authenticate_worker_channel(second_websocket)
                second_websocket.send_json(
                    _cleanup_worker_hello_frame(worker_name="worker-2")
                )
                WorkerReadyFrame.model_validate(second_websocket.receive_json())

                deadline = time.monotonic() + 1
                while (
                    cleanup_queue.wait_for_wakeup_call_count() == 0
                    and time.monotonic() < deadline
                ):
                    time.sleep(0.01)
                time.sleep(0.1)

                assert cleanup_queue.wait_for_wakeup_call_count() >= 1
                assert cleanup_queue.max_active_wait_for_wakeup_calls() == 1

    async def test_dispatches_cleanup_message_and_sends_ack_result(
        self, test_client: TestClient, work_pool, cleanup_queue: FakeWorkerCleanupQueue
    ):
        message = cleanup_queue.add_message(work_pool_id=work_pool.id)

        with _connect_worker_channel(test_client, work_pool.name) as websocket:
            _authenticate_worker_channel(websocket)
            websocket.send_json(_cleanup_worker_hello_frame())
            WorkerReadyFrame.model_validate(websocket.receive_json())

            cleanup = CleanupMessageFrame.model_validate(websocket.receive_json())
            websocket.send_json(
                _cleanup_ack_frame(
                    message_id=cleanup.payload.message_id,
                    reservation_token=cleanup.payload.reservation_token,
                )
            )
            result = CleanupOperationResultFrame.model_validate(
                websocket.receive_json()
            )

        assert cleanup.payload.message_id == message.message_id
        assert result.payload.message_id == message.message_id
        assert result.payload.operation == "ack"
        assert result.payload.status == "accepted"
        assert cleanup_queue.active_message_count() == 0

    async def test_capacity_limits_delivery_until_operation_completes(
        self, test_client: TestClient, work_pool, cleanup_queue: FakeWorkerCleanupQueue
    ):
        first = cleanup_queue.add_message(work_pool_id=work_pool.id)
        second = cleanup_queue.add_message(work_pool_id=work_pool.id)

        with _connect_worker_channel(test_client, work_pool.name) as websocket:
            _authenticate_worker_channel(websocket)
            websocket.send_json(_cleanup_worker_hello_frame(max_cleanup_concurrency=1))
            WorkerReadyFrame.model_validate(websocket.receive_json())

            first_cleanup = CleanupMessageFrame.model_validate(websocket.receive_json())
            assert cleanup_queue.active_reservation_count() == 1
            websocket.send_json(
                _cleanup_ack_frame(
                    message_id=first_cleanup.payload.message_id,
                    reservation_token=first_cleanup.payload.reservation_token,
                )
            )
            CleanupOperationResultFrame.model_validate(websocket.receive_json())
            second_cleanup = CleanupMessageFrame.model_validate(
                websocket.receive_json()
            )

        assert {
            first_cleanup.payload.message_id,
            second_cleanup.payload.message_id,
        } == {
            first.message_id,
            second.message_id,
        }

    async def test_multiple_workers_receive_distinct_messages(
        self, test_client: TestClient, work_pool, cleanup_queue: FakeWorkerCleanupQueue
    ):
        first = cleanup_queue.add_message(work_pool_id=work_pool.id)
        second = cleanup_queue.add_message(work_pool_id=work_pool.id)

        with _connect_worker_channel(test_client, work_pool.name) as first_websocket:
            _authenticate_worker_channel(first_websocket)
            first_websocket.send_json(
                _cleanup_worker_hello_frame(worker_name="worker-1")
            )
            WorkerReadyFrame.model_validate(first_websocket.receive_json())
            first_cleanup = CleanupMessageFrame.model_validate(
                first_websocket.receive_json()
            )

            with _connect_worker_channel(
                test_client, work_pool.name
            ) as second_websocket:
                _authenticate_worker_channel(second_websocket)
                second_websocket.send_json(
                    _cleanup_worker_hello_frame(worker_name="worker-2")
                )
                WorkerReadyFrame.model_validate(second_websocket.receive_json())
                second_cleanup = CleanupMessageFrame.model_validate(
                    second_websocket.receive_json()
                )

        assert first_cleanup.payload.message_id != second_cleanup.payload.message_id
        assert {
            first_cleanup.payload.message_id,
            second_cleanup.payload.message_id,
        } == {
            first.message_id,
            second.message_id,
        }

    async def test_no_reservation_when_worker_cannot_handle_cleanup_kind(
        self, test_client: TestClient, work_pool, cleanup_queue: FakeWorkerCleanupQueue
    ):
        cleanup_queue.add_message(
            work_pool_id=work_pool.id,
            kind=PENDING_CLAIM_TEARDOWN,
        )

        with _connect_worker_channel(test_client, work_pool.name) as websocket:
            _authenticate_worker_channel(websocket)
            websocket.send_json(_cleanup_worker_hello_frame())
            WorkerReadyFrame.model_validate(websocket.receive_json())
            await asyncio.sleep(0.1)

        assert cleanup_queue.active_reservation_count() == 0
        assert cleanup_queue.active_message_count() == 1

    async def test_invalid_reservation_token_returns_operation_result(
        self, test_client: TestClient, work_pool, cleanup_queue: FakeWorkerCleanupQueue
    ):
        cleanup_queue.add_message(work_pool_id=work_pool.id)

        with _connect_worker_channel(test_client, work_pool.name) as websocket:
            _authenticate_worker_channel(websocket)
            websocket.send_json(_cleanup_worker_hello_frame())
            WorkerReadyFrame.model_validate(websocket.receive_json())
            cleanup = CleanupMessageFrame.model_validate(websocket.receive_json())

            websocket.send_json(
                _cleanup_ack_frame(
                    message_id=cleanup.payload.message_id,
                    reservation_token="wrong-token",
                )
            )
            result = CleanupOperationResultFrame.model_validate(
                websocket.receive_json()
            )

        assert result.payload.status == "invalid_token"
        assert result.payload.reason == "reservation_token_mismatch"
        assert cleanup_queue.active_reservation_count() == 1

    async def test_release_result_frees_capacity_and_redelivers_with_new_token(
        self, test_client: TestClient, work_pool, cleanup_queue: FakeWorkerCleanupQueue
    ):
        cleanup_queue.add_message(work_pool_id=work_pool.id)

        with _connect_worker_channel(test_client, work_pool.name) as websocket:
            _authenticate_worker_channel(websocket)
            websocket.send_json(_cleanup_worker_hello_frame())
            WorkerReadyFrame.model_validate(websocket.receive_json())
            cleanup = CleanupMessageFrame.model_validate(websocket.receive_json())

            websocket.send_json(
                _cleanup_release_frame(
                    message_id=cleanup.payload.message_id,
                    reservation_token=cleanup.payload.reservation_token,
                )
            )
            result = CleanupOperationResultFrame.model_validate(
                websocket.receive_json()
            )
            redelivery = CleanupMessageFrame.model_validate(websocket.receive_json())

            websocket.send_json(
                _cleanup_ack_frame(
                    message_id=cleanup.payload.message_id,
                    reservation_token=cleanup.payload.reservation_token,
                )
            )
            stale_result = CleanupOperationResultFrame.model_validate(
                websocket.receive_json()
            )

        assert result.payload.status == "accepted"
        assert redelivery.payload.message_id == cleanup.payload.message_id
        assert redelivery.payload.reservation_token != cleanup.payload.reservation_token
        assert stale_result.payload.status == "invalid_token"
        assert stale_result.payload.reason == "reservation_token_mismatch"

    async def test_renew_preserves_capacity_and_returns_new_lease(
        self, test_client: TestClient, work_pool, cleanup_queue: FakeWorkerCleanupQueue
    ):
        cleanup_queue.add_message(work_pool_id=work_pool.id)

        with _connect_worker_channel(test_client, work_pool.name) as websocket:
            _authenticate_worker_channel(websocket)
            websocket.send_json(_cleanup_worker_hello_frame())
            WorkerReadyFrame.model_validate(websocket.receive_json())
            cleanup = CleanupMessageFrame.model_validate(websocket.receive_json())

            websocket.send_json(
                _cleanup_renew_frame(
                    message_id=cleanup.payload.message_id,
                    reservation_token=cleanup.payload.reservation_token,
                )
            )
            result = CleanupOperationResultFrame.model_validate(
                websocket.receive_json()
            )

        assert result.payload.operation == "renew"
        assert result.payload.status == "accepted"
        assert result.payload.lease_expires_at is not None
        assert cleanup_queue.active_reservation_count() == 1

    async def test_reconnect_can_ack_current_reservation_token(
        self, test_client: TestClient, work_pool, cleanup_queue: FakeWorkerCleanupQueue
    ):
        cleanup_queue._lease_seconds = 30
        cleanup_queue.add_message(work_pool_id=work_pool.id)

        with _connect_worker_channel(test_client, work_pool.name) as websocket:
            _authenticate_worker_channel(websocket)
            websocket.send_json(_cleanup_worker_hello_frame())
            WorkerReadyFrame.model_validate(websocket.receive_json())
            cleanup = CleanupMessageFrame.model_validate(websocket.receive_json())

        with _connect_worker_channel(test_client, work_pool.name) as websocket:
            _authenticate_worker_channel(websocket)
            websocket.send_json(_cleanup_worker_hello_frame())
            WorkerReadyFrame.model_validate(websocket.receive_json())

            websocket.send_json(
                _cleanup_ack_frame(
                    message_id=cleanup.payload.message_id,
                    reservation_token=cleanup.payload.reservation_token,
                )
            )
            result = CleanupOperationResultFrame.model_validate(
                websocket.receive_json()
            )

        assert result.payload.status == "accepted"
        assert cleanup_queue.active_message_count() == 0

    async def test_disconnect_redelivers_after_lease_expiry(
        self, test_client: TestClient, work_pool, cleanup_queue: FakeWorkerCleanupQueue
    ):
        message = cleanup_queue.add_message(work_pool_id=work_pool.id)

        with _connect_worker_channel(test_client, work_pool.name) as websocket:
            _authenticate_worker_channel(websocket)
            websocket.send_json(_cleanup_worker_hello_frame())
            WorkerReadyFrame.model_validate(websocket.receive_json())
            first_cleanup = CleanupMessageFrame.model_validate(websocket.receive_json())

        await asyncio.sleep(0.08)

        with _connect_worker_channel(test_client, work_pool.name) as websocket:
            _authenticate_worker_channel(websocket)
            websocket.send_json(_cleanup_worker_hello_frame())
            WorkerReadyFrame.model_validate(websocket.receive_json())
            redelivery = CleanupMessageFrame.model_validate(websocket.receive_json())

        assert first_cleanup.payload.message_id == message.message_id
        assert redelivery.payload.message_id == message.message_id
        assert redelivery.payload.delivery_count == 2
        assert (
            redelivery.payload.reservation_token
            != first_cleanup.payload.reservation_token
        )
