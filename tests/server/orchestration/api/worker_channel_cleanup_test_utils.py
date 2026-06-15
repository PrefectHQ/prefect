import asyncio
import threading
import uuid
from collections.abc import Iterable, Iterator
from datetime import timezone
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
    WORK_POOL_SNAPSHOT_CAPABILITY,
    WORK_POOL_WORKER_CHANNEL_VERSION,
    WORKER_HEARTBEAT_CAPABILITY,
    CleanupKind,
    CleanupMessageFrame,
    WorkerReadyFrame,
)
from prefect.server.events.clients import AssertingEventsClient
from prefect.server.utilities import worker_channel as worker_channel_utils
from prefect.server.utilities import (
    worker_channel_cleanup as worker_channel_cleanup_utils,
)
from prefect.server.worker_communication.cleanup_queue import (
    CleanupQueueMessage,
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


class RaisingAckCleanupQueue(MemoryWorkerCleanupQueue):
    _instance: "RaisingAckCleanupQueue | None" = None
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
        raise RuntimeError("cleanup queue unavailable")


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


class BlockingCleanupMessageWebSocket(RecordingWebSocket):
    def __init__(self) -> None:
        super().__init__()
        self.cleanup_send_started = asyncio.Event()
        self.release_cleanup_send = asyncio.Event()

    async def send_json(self, payload: dict[str, Any]) -> None:
        if payload["type"] == "cleanup.message.v1":
            await super().send_json(payload)
            self.cleanup_send_started.set()
            await self.release_cleanup_send.wait()
            return
        await super().send_json(payload)


def sent_cleanup_operation_results(
    websocket: RecordingWebSocket,
) -> list[dict[str, Any]]:
    return [
        frame
        for frame in websocket.sent_json
        if frame["type"] == "cleanup.operation_result.v1"
    ]


def sent_cleanup_messages(websocket: RecordingWebSocket) -> list[CleanupMessageFrame]:
    return [
        CleanupMessageFrame.model_validate(frame)
        for frame in websocket.sent_json
        if frame["type"] == "cleanup.message.v1"
    ]


def make_cleanup_connection(
    *,
    work_pool,
    cleanup_queue: WorkerCleanupQueue,
    registry: worker_channel_utils.WorkerCleanupConnectionRegistry,
    websocket: RecordingWebSocket | None = None,
    consumer_id: UUID | None = None,
    worker_name: str = "test-worker",
    cleanup_kinds: tuple[CleanupKind, ...] = (CANCELLING_TIMEOUT_TEARDOWN,),
    max_cleanup_concurrency: int = 1,
    ready: bool = True,
) -> worker_channel_utils.WorkerChannelConnection:
    connection = worker_channel_utils.WorkerChannelConnection(
        websocket=websocket or RecordingWebSocket(),
        db=object(),
        work_pool_name=work_pool.name,
        work_pool_id=work_pool.id,
        consumer_id=consumer_id or uuid.uuid4(),
        worker_name=worker_name,
        cleanup_queue=cleanup_queue,
        cleanup_kinds=cleanup_kinds,
        max_cleanup_concurrency=max_cleanup_concurrency,
        cleanup_registry=registry,
    )
    if ready:
        connection._ready_sent.set()
    return connection


def worker_ready_frame_for_connection(
    connection: worker_channel_utils.WorkerChannelConnection,
    work_pool,
) -> WorkerReadyFrame:
    return WorkerReadyFrame.model_validate(
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
