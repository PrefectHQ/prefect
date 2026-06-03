import asyncio
import threading
import time
import uuid
from collections.abc import Iterable, Iterator
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
    CleanupRenewFrame,
    WorkerReadyFrame,
)
from prefect.server.events.clients import AssertingEventsClient
from prefect.server.utilities import worker_channel as worker_channel_utils
from prefect.server.utilities import (
    worker_channel_cleanup as worker_channel_cleanup_utils,
)
from prefect.server.worker_communication.cleanup_queue import (
    CleanupQueueMessage,
    CleanupQueueOperation,
    CleanupQueueOperationResult,
    CleanupQueueReservation,
    CleanupQueueWakeup,
    WorkerCleanupQueue,
)
from prefect.server.worker_communication.cleanup_queue.memory import (
    WorkerCleanupQueue as MemoryWorkerCleanupQueue,
)
from prefect.settings import (
    PREFECT_SERVER_WORKER_CHANNEL_CLEANUP_LEASE_SECONDS,
    temporary_settings,
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


class InstrumentedMemoryCleanupQueue(MemoryWorkerCleanupQueue):
    _instance: "InstrumentedMemoryCleanupQueue | None" = None
    _initialized = False

    def __init__(self) -> None:
        super().__init__()
        self.clear()
        self._wait_for_wakeup_calls = 0
        self._active_wait_for_wakeup_calls = 0
        self._max_active_wait_for_wakeup_calls = 0
        self._instrumentation_lock = threading.Lock()

    def wait_for_wakeup_call_count(self) -> int:
        with self._instrumentation_lock:
            return self._wait_for_wakeup_calls

    def max_active_wait_for_wakeup_calls(self) -> int:
        with self._instrumentation_lock:
            return self._max_active_wait_for_wakeup_calls

    async def wait_for_wakeup(
        self,
        work_pool_id: UUID,
        *,
        after: int = 0,
        timeout: float | None = None,
    ) -> CleanupQueueWakeup | None:
        with self._instrumentation_lock:
            self._wait_for_wakeup_calls += 1
            self._active_wait_for_wakeup_calls += 1
            self._max_active_wait_for_wakeup_calls = max(
                self._max_active_wait_for_wakeup_calls,
                self._active_wait_for_wakeup_calls,
            )
        try:
            return await super().wait_for_wakeup(
                work_pool_id,
                after=after,
                timeout=timeout,
            )
        finally:
            with self._instrumentation_lock:
                self._active_wait_for_wakeup_calls -= 1


async def enqueue_cleanup_message(
    queue: WorkerCleanupQueue,
    *,
    work_pool_id: UUID,
    kind: CleanupKind = CANCELLING_TIMEOUT_TEARDOWN,
    work_queue_id: UUID | None = None,
    message_id: UUID | None = None,
) -> CleanupQueueMessage:
    return await queue.enqueue(
        message_id=message_id or uuid.uuid4(),
        idempotency_key=str(uuid.uuid4()),
        work_pool_id=work_pool_id,
        work_queue_id=work_queue_id,
        kind=kind,
        target={"flow_run_id": uuid.uuid4()},
    )


class ErrorAckCleanupQueue(MemoryWorkerCleanupQueue):
    _instance: "ErrorAckCleanupQueue | None" = None
    _initialized = False

    def __init__(self) -> None:
        super().__init__()
        self.clear()

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


class ToggleFailingReserveCleanupQueue(MemoryWorkerCleanupQueue):
    _instance: "ToggleFailingReserveCleanupQueue | None" = None
    _initialized = False

    def __init__(self) -> None:
        super().__init__()
        self.clear()
        self.reserve_should_fail = False

    async def reserve(
        self,
        *,
        work_pool_id: UUID,
        cleanup_kinds: Iterable[CleanupKind] | None = None,
        preferred_work_queue_ids: Iterable[UUID] | None = None,
        allow_fallback_to_any_queue: bool = True,
    ) -> CleanupQueueReservation | None:
        if self.reserve_should_fail:
            raise RuntimeError("cleanup queue unavailable")
        return await super().reserve(
            work_pool_id=work_pool_id,
            cleanup_kinds=cleanup_kinds,
            preferred_work_queue_ids=preferred_work_queue_ids,
            allow_fallback_to_any_queue=allow_fallback_to_any_queue,
        )


@pytest.fixture
def cleanup_queue(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[InstrumentedMemoryCleanupQueue]:
    with temporary_settings(
        {PREFECT_SERVER_WORKER_CHANNEL_CLEANUP_LEASE_SECONDS: 0.05}
    ):
        queue = InstrumentedMemoryCleanupQueue()
        monkeypatch.setattr(workers_api, "get_worker_cleanup_queue", lambda: queue)
        monkeypatch.setattr(
            worker_channel_cleanup_utils,
            "_WORKER_CHANNEL_CLEANUP_DISPATCH_POLL_SECONDS",
            0.05,
        )
        yield queue
        queue.clear()


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


class DisconnectingOperationResultWebSocket(RecordingWebSocket):
    async def send_json(self, payload: dict[str, Any]) -> None:
        self.sent_json.append(payload)
        if payload["type"] == "cleanup.operation_result.v1":
            raise WebSocketDisconnect


class CancellingWebSocket(RecordingWebSocket):
    async def send_json(self, payload: dict[str, Any]) -> None:
        self.sent_json.append(payload)
        raise asyncio.CancelledError


class BlockingOperationResultWebSocket(RecordingWebSocket):
    def __init__(self) -> None:
        super().__init__()
        self.operation_result_send_started = asyncio.Event()
        self.release_operation_result_send = asyncio.Event()

    async def send_json(self, payload: dict[str, Any]) -> None:
        if payload["type"] == "cleanup.operation_result.v1":
            self.operation_result_send_started.set()
            await self.release_operation_result_send.wait()
        await super().send_json(payload)


class TestWorkerCleanupConnectionRegistry:
    async def test_send_loop_handles_cleanup_dispatch_failure(self, work_pool):
        cleanup_queue = ToggleFailingReserveCleanupQueue()
        cleanup_queue.reserve_should_fail = True
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
        ready = WorkerReadyFrame.model_validate(
            {
                "type": "worker.ready.v1",
                "id": str(uuid7()),
                "sent_at": now("UTC").isoformat(),
                "payload": {
                    "consumer_id": str(connection.consumer_id),
                    "worker_id": None,
                    "selected_channel_version": WORK_POOL_WORKER_CHANNEL_VERSION,
                    "effective_heartbeat_interval_seconds": 30,
                    "accepted_capabilities": [
                        WORKER_HEARTBEAT_CAPABILITY,
                        WORK_POOL_SNAPSHOT_CAPABILITY,
                        CLEANUP_DELIVERY_CAPABILITY,
                    ],
                    "rejected_capabilities": [],
                    "effective_max_cleanup_concurrency": 1,
                    "resolved_work_queues": [],
                    "initial_snapshot": {
                        "snapshot_sequence": 1,
                        "reason": "initial",
                        "work_pool": {
                            "id": str(work_pool.id),
                            "name": work_pool.name,
                            "type": work_pool.type,
                            "base_job_template": work_pool.base_job_template or {},
                            "is_paused": work_pool.is_paused,
                            "storage_configuration": {},
                            "default_queue_id": str(work_pool.default_queue_id),
                        },
                    },
                },
            }
        )

        send_task = asyncio.create_task(connection._send_loop(ready))
        try:
            await asyncio.wait_for(connection._ready_sent.wait(), timeout=0.5)
            await asyncio.sleep(0)

            assert not send_task.done()
            assert websocket.sent_json[0]["type"] == "worker.ready.v1"
        finally:
            send_task.cancel()
            await asyncio.gather(send_task, return_exceptions=True)

    async def test_registered_connection_is_ineligible_until_ready_is_sent(
        self, work_pool
    ):
        cleanup_queue = InstrumentedMemoryCleanupQueue()
        message = await enqueue_cleanup_message(
            cleanup_queue, work_pool_id=work_pool.id
        )
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

            stored = await cleanup_queue.read_message(
                work_pool_id=work_pool.id,
                message_id=message.message_id,
            )
            assert stored is not None
            assert stored.delivery_count == 0
            assert websocket.sent_json == []

            connection._ready_sent.set()
            await registry.dispatch_available(
                work_pool_id=work_pool.id,
                cleanup_queue=cleanup_queue,
            )

        assert websocket.sent_json[0]["type"] == "cleanup.message.v1"
        cleanup = CleanupMessageFrame.model_validate(websocket.sent_json[0])
        assert cleanup.payload.message_id == message.message_id
        stored = await cleanup_queue.read_message(
            work_pool_id=work_pool.id,
            message_id=message.message_id,
        )
        assert stored is not None
        assert stored.delivery_count == 1

    async def test_disconnect_during_cleanup_send_removes_connection_from_dispatch(
        self, work_pool
    ):
        cleanup_queue = InstrumentedMemoryCleanupQueue()
        message = await enqueue_cleanup_message(
            cleanup_queue, work_pool_id=work_pool.id
        )
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
        assert len(websocket.sent_json) == 1

    async def test_cleanup_send_cancellation_releases_reserved_message(self, work_pool):
        cleanup_queue = InstrumentedMemoryCleanupQueue()
        message = await enqueue_cleanup_message(
            cleanup_queue, work_pool_id=work_pool.id
        )
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
        first = await enqueue_cleanup_message(cleanup_queue, work_pool_id=work_pool.id)
        second = await enqueue_cleanup_message(cleanup_queue, work_pool_id=work_pool.id)
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
        cleanup_queue = InstrumentedMemoryCleanupQueue()
        message = await enqueue_cleanup_message(
            cleanup_queue, work_pool_id=work_pool.id
        )
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

    async def test_operation_result_send_precedes_capacity_release(self, work_pool):
        cleanup_queue = InstrumentedMemoryCleanupQueue()
        first = await enqueue_cleanup_message(cleanup_queue, work_pool_id=work_pool.id)
        second = await enqueue_cleanup_message(cleanup_queue, work_pool_id=work_pool.id)
        websocket = BlockingOperationResultWebSocket()
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
            operation_task = asyncio.create_task(
                connection._handle_cleanup_operation(
                    CleanupAckFrame.model_validate(
                        _cleanup_ack_frame(
                            message_id=first_cleanup.payload.message_id,
                            reservation_token=first_cleanup.payload.reservation_token,
                        )
                    )
                )
            )
            await websocket.operation_result_send_started.wait()

            dispatch_task = asyncio.create_task(
                registry.dispatch_available(
                    work_pool_id=work_pool.id,
                    cleanup_queue=cleanup_queue,
                )
            )
            await asyncio.wait_for(dispatch_task, timeout=0.5)
            assert [
                frame["type"]
                for frame in websocket.sent_json
                if frame["type"] == "cleanup.message.v1"
            ] == ["cleanup.message.v1"]
            stored_second = await cleanup_queue.read_message(
                work_pool_id=work_pool.id,
                message_id=second.message_id,
            )
            assert stored_second is not None
            assert stored_second.delivery_count == 0

            websocket.release_operation_result_send.set()
            await operation_task

        sent_frame_types = [frame["type"] for frame in websocket.sent_json]
        cleanup_messages = [
            CleanupMessageFrame.model_validate(frame)
            for frame in websocket.sent_json
            if frame["type"] == "cleanup.message.v1"
        ]
        assert first_cleanup.payload.message_id == first.message_id
        assert [message.payload.message_id for message in cleanup_messages] == [
            first.message_id,
            second.message_id,
        ]
        assert sent_frame_types == [
            "cleanup.message.v1",
            "cleanup.operation_result.v1",
            "cleanup.message.v1",
        ]

    async def test_operation_result_handles_cleanup_dispatch_failure(
        self, work_pool, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(
            worker_channel_cleanup_utils,
            "_WORKER_CHANNEL_CLEANUP_DISPATCH_POLL_SECONDS",
            0.01,
        )
        cleanup_queue = ToggleFailingReserveCleanupQueue()
        await enqueue_cleanup_message(cleanup_queue, work_pool_id=work_pool.id)
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
            cleanup = CleanupMessageFrame.model_validate(websocket.sent_json[0])
            cleanup_queue.reserve_should_fail = True

            await connection._handle_cleanup_operation(
                CleanupAckFrame.model_validate(
                    _cleanup_ack_frame(
                        message_id=cleanup.payload.message_id,
                        reservation_token=cleanup.payload.reservation_token,
                    )
                )
            )

        operation_results = [
            frame
            for frame in websocket.sent_json
            if frame["type"] == "cleanup.operation_result.v1"
        ]
        assert operation_results[0]["payload"]["status"] == "accepted"

    @pytest.mark.parametrize("operation", ("ack", "release"))
    async def test_operation_result_send_failure_frees_cleanup_capacity_on_reconnect(
        self, work_pool, operation: CleanupQueueOperation
    ):
        cleanup_queue = InstrumentedMemoryCleanupQueue()
        first = await enqueue_cleanup_message(cleanup_queue, work_pool_id=work_pool.id)
        second = await enqueue_cleanup_message(cleanup_queue, work_pool_id=work_pool.id)
        consumer_id = uuid.uuid4()
        registry = worker_channel_utils.WorkerCleanupConnectionRegistry()
        websocket = DisconnectingOperationResultWebSocket()
        connection = worker_channel_utils.WorkerChannelConnection(
            websocket=websocket,
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
        connection._ready_sent.set()

        async with registry.register(connection):
            await registry.dispatch_available(
                work_pool_id=work_pool.id,
                cleanup_queue=cleanup_queue,
            )
            cleanup = CleanupMessageFrame.model_validate(websocket.sent_json[0])

            if operation == "ack":
                frame = CleanupAckFrame.model_validate(
                    _cleanup_ack_frame(
                        message_id=cleanup.payload.message_id,
                        reservation_token=cleanup.payload.reservation_token,
                    )
                )
                expected_message_id = second.message_id
            else:
                frame = CleanupReleaseFrame.model_validate(
                    _cleanup_release_frame(
                        message_id=cleanup.payload.message_id,
                        reservation_token=cleanup.payload.reservation_token,
                    )
                )
                expected_message_id = first.message_id

            with pytest.raises(WebSocketDisconnect):
                await connection._handle_cleanup_operation(frame)

        replacement_websocket = RecordingWebSocket()
        replacement_connection = worker_channel_utils.WorkerChannelConnection(
            websocket=replacement_websocket,
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
        replacement_connection._ready_sent.set()

        async with registry.register(replacement_connection):
            await registry.dispatch_available(
                work_pool_id=work_pool.id,
                cleanup_queue=cleanup_queue,
            )

        cleanup_messages = [
            CleanupMessageFrame.model_validate(frame)
            for frame in replacement_websocket.sent_json
            if frame["type"] == "cleanup.message.v1"
        ]
        assert [message.payload.message_id for message in cleanup_messages] == [
            expected_message_id
        ]

    async def test_renew_syncs_lease_before_result_send(self, work_pool):
        cleanup_queue = InstrumentedMemoryCleanupQueue()
        first = await enqueue_cleanup_message(cleanup_queue, work_pool_id=work_pool.id)
        second = await enqueue_cleanup_message(cleanup_queue, work_pool_id=work_pool.id)
        websocket = BlockingOperationResultWebSocket()
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
            await registry.update_cleanup_lease(
                connection,
                reservation_token=first_cleanup.payload.reservation_token,
                lease_expires_at=now("UTC") + timedelta(milliseconds=50),
            )

            operation_task = asyncio.create_task(
                connection._handle_cleanup_operation(
                    CleanupRenewFrame.model_validate(
                        _cleanup_renew_frame(
                            message_id=first_cleanup.payload.message_id,
                            reservation_token=first_cleanup.payload.reservation_token,
                        )
                    )
                )
            )
            await websocket.operation_result_send_started.wait()
            await asyncio.sleep(0.1)

            await asyncio.wait_for(
                registry.dispatch_available(
                    work_pool_id=work_pool.id,
                    cleanup_queue=cleanup_queue,
                ),
                timeout=0.5,
            )
            cleanup_messages = [
                CleanupMessageFrame.model_validate(frame)
                for frame in websocket.sent_json
                if frame["type"] == "cleanup.message.v1"
            ]
            assert [message.payload.message_id for message in cleanup_messages] == [
                first.message_id
            ]
            stored_second = await cleanup_queue.read_message(
                work_pool_id=work_pool.id,
                message_id=second.message_id,
            )
            assert stored_second is not None
            assert stored_second.delivery_count == 0

            websocket.release_operation_result_send.set()
            await operation_task

    async def test_mismatched_cleanup_result_keeps_capacity_in_use(self, work_pool):
        cleanup_queue = InstrumentedMemoryCleanupQueue()
        await enqueue_cleanup_message(cleanup_queue, work_pool_id=work_pool.id)
        await enqueue_cleanup_message(cleanup_queue, work_pool_id=work_pool.id)
        third = await enqueue_cleanup_message(cleanup_queue, work_pool_id=work_pool.id)
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
        stored_third = await cleanup_queue.read_message(
            work_pool_id=work_pool.id,
            message_id=third.message_id,
        )
        assert stored_third is not None
        assert stored_third.delivery_count == 0
        assert operation_results[0]["payload"]["status"] == "invalid_token"

    async def test_reconnect_preserves_in_flight_cleanup_capacity(self, work_pool):
        cleanup_queue = InstrumentedMemoryCleanupQueue()
        first = await enqueue_cleanup_message(cleanup_queue, work_pool_id=work_pool.id)
        second = await enqueue_cleanup_message(cleanup_queue, work_pool_id=work_pool.id)
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
        cleanup_queue = InstrumentedMemoryCleanupQueue()
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

    async def test_register_restarts_exiting_cleanup_dispatcher(self, work_pool):
        cleanup_queue = InstrumentedMemoryCleanupQueue()
        registry = worker_channel_utils.WorkerCleanupConnectionRegistry()
        exiting_task_started = asyncio.Event()
        exiting_task_released = asyncio.Event()

        async def exiting_dispatcher() -> None:
            exiting_task_started.set()
            await exiting_task_released.wait()

        exiting_task = asyncio.create_task(exiting_dispatcher())
        await exiting_task_started.wait()
        registry._dispatch_tasks_by_work_pool_id[work_pool.id] = exiting_task
        registry._exiting_dispatch_tasks_by_work_pool_id[work_pool.id] = exiting_task
        stale_event = asyncio.Event()
        registry._dispatch_events_by_work_pool_id[work_pool.id] = stale_event
        registry._dispatch_loops_by_work_pool_id[work_pool.id] = (
            asyncio.get_running_loop()
        )

        connection = worker_channel_utils.WorkerChannelConnection(
            websocket=RecordingWebSocket(),
            db=object(),
            work_pool_name=work_pool.name,
            work_pool_id=work_pool.id,
            consumer_id=uuid.uuid4(),
            worker_name="replacement-worker",
            cleanup_queue=cleanup_queue,
            cleanup_kinds=(CANCELLING_TIMEOUT_TEARDOWN,),
            max_cleanup_concurrency=1,
            cleanup_registry=registry,
        )

        replacement_task: asyncio.Task[None] | None = None
        try:
            async with registry.register(connection):
                replacement_task = registry._dispatch_tasks_by_work_pool_id[
                    work_pool.id
                ]
                assert replacement_task is not exiting_task
                assert replacement_task is not None
                assert not replacement_task.done()
                assert (
                    registry._dispatch_events_by_work_pool_id[work_pool.id]
                    is not stale_event
                )
                assert registry._exiting_dispatch_tasks_by_work_pool_id == {}
        finally:
            exiting_task_released.set()
            tasks = [exiting_task]
            if replacement_task is not None:
                replacement_task.cancel()
                tasks.append(replacement_task)
            await asyncio.gather(*tasks, return_exceptions=True)


class TestWorkerChannelCleanupDispatcher:
    async def test_cleanup_capability_is_accepted_for_capable_workers(
        self,
        test_client: TestClient,
        work_pool,
        cleanup_queue: InstrumentedMemoryCleanupQueue,
    ):
        with _connect_worker_channel(test_client, work_pool.name) as websocket:
            _authenticate_worker_channel(websocket)
            websocket.send_json(_cleanup_worker_hello_frame(max_cleanup_concurrency=2))

            ready = WorkerReadyFrame.model_validate(websocket.receive_json())

        assert CLEANUP_DELIVERY_CAPABILITY in ready.payload.accepted_capabilities
        assert ready.payload.rejected_capabilities == []
        assert ready.payload.effective_max_cleanup_concurrency == 2

    async def test_cleanup_capability_is_rejected_without_worker_capacity(
        self,
        test_client: TestClient,
        work_pool,
        cleanup_queue: InstrumentedMemoryCleanupQueue,
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
        cleanup_queue: InstrumentedMemoryCleanupQueue,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.setattr(
            worker_channel_cleanup_utils,
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
        self,
        test_client: TestClient,
        work_pool,
        cleanup_queue: InstrumentedMemoryCleanupQueue,
    ):
        message = await enqueue_cleanup_message(
            cleanup_queue, work_pool_id=work_pool.id
        )

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
        assert (
            await cleanup_queue.read_message(
                work_pool_id=work_pool.id,
                message_id=message.message_id,
            )
            is None
        )

    async def test_capacity_limits_delivery_until_operation_completes(
        self,
        test_client: TestClient,
        work_pool,
        cleanup_queue: InstrumentedMemoryCleanupQueue,
    ):
        first = await enqueue_cleanup_message(cleanup_queue, work_pool_id=work_pool.id)
        second = await enqueue_cleanup_message(cleanup_queue, work_pool_id=work_pool.id)

        with _connect_worker_channel(test_client, work_pool.name) as websocket:
            _authenticate_worker_channel(websocket)
            websocket.send_json(_cleanup_worker_hello_frame(max_cleanup_concurrency=1))
            WorkerReadyFrame.model_validate(websocket.receive_json())

            first_cleanup = CleanupMessageFrame.model_validate(websocket.receive_json())
            stored_first = await cleanup_queue.read_message(
                work_pool_id=work_pool.id,
                message_id=first.message_id,
            )
            stored_second = await cleanup_queue.read_message(
                work_pool_id=work_pool.id,
                message_id=second.message_id,
            )
            assert stored_first is not None
            assert stored_first.delivery_count == 1
            assert stored_second is not None
            assert stored_second.delivery_count == 0
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
        self,
        test_client: TestClient,
        work_pool,
        cleanup_queue: InstrumentedMemoryCleanupQueue,
    ):
        first = await enqueue_cleanup_message(cleanup_queue, work_pool_id=work_pool.id)
        second = await enqueue_cleanup_message(cleanup_queue, work_pool_id=work_pool.id)

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
        self,
        test_client: TestClient,
        work_pool,
        cleanup_queue: InstrumentedMemoryCleanupQueue,
    ):
        message = await enqueue_cleanup_message(
            cleanup_queue,
            work_pool_id=work_pool.id,
            kind=PENDING_CLAIM_TEARDOWN,
        )

        with _connect_worker_channel(test_client, work_pool.name) as websocket:
            _authenticate_worker_channel(websocket)
            websocket.send_json(_cleanup_worker_hello_frame())
            WorkerReadyFrame.model_validate(websocket.receive_json())
            await asyncio.sleep(0.1)

        stored = await cleanup_queue.read_message(
            work_pool_id=work_pool.id,
            message_id=message.message_id,
        )
        assert stored is not None
        assert stored.delivery_count == 0

    async def test_invalid_reservation_token_returns_operation_result(
        self,
        test_client: TestClient,
        work_pool,
        cleanup_queue: InstrumentedMemoryCleanupQueue,
    ):
        message = await enqueue_cleanup_message(
            cleanup_queue, work_pool_id=work_pool.id
        )

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
        stored = await cleanup_queue.read_message(
            work_pool_id=work_pool.id,
            message_id=message.message_id,
        )
        assert stored is not None
        assert stored.delivery_count == 1

    async def test_release_result_frees_capacity_and_redelivers_with_new_token(
        self,
        test_client: TestClient,
        work_pool,
        cleanup_queue: InstrumentedMemoryCleanupQueue,
    ):
        await enqueue_cleanup_message(cleanup_queue, work_pool_id=work_pool.id)

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
        self,
        test_client: TestClient,
        work_pool,
        cleanup_queue: InstrumentedMemoryCleanupQueue,
    ):
        message = await enqueue_cleanup_message(
            cleanup_queue, work_pool_id=work_pool.id
        )

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
        stored = await cleanup_queue.read_message(
            work_pool_id=work_pool.id,
            message_id=message.message_id,
        )
        assert stored is not None
        assert stored.delivery_count == 1

    async def test_reconnect_can_ack_current_reservation_token(
        self,
        test_client: TestClient,
        work_pool,
        cleanup_queue: InstrumentedMemoryCleanupQueue,
    ):
        with temporary_settings(
            {PREFECT_SERVER_WORKER_CHANNEL_CLEANUP_LEASE_SECONDS: 30}
        ):
            message = await enqueue_cleanup_message(
                cleanup_queue, work_pool_id=work_pool.id
            )

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
        assert (
            await cleanup_queue.read_message(
                work_pool_id=work_pool.id,
                message_id=message.message_id,
            )
            is None
        )

    async def test_disconnect_redelivers_after_lease_expiry(
        self,
        test_client: TestClient,
        work_pool,
        cleanup_queue: InstrumentedMemoryCleanupQueue,
    ):
        message = await enqueue_cleanup_message(
            cleanup_queue, work_pool_id=work_pool.id
        )

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
