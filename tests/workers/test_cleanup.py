from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any
from unittest.mock import Mock
from uuid import uuid4

import anyio
import orjson
import pytest

from prefect._internal.uuid7 import uuid7
from prefect.client.base import ServerType
from prefect.client.schemas.worker_channel import (
    CANCELLING_TIMEOUT_TEARDOWN,
    CLEANUP_DELIVERY_CAPABILITY,
    PENDING_CLAIM_TEARDOWN,
    WORK_POOL_SNAPSHOT_CAPABILITY,
    WORK_POOL_WORKER_CHANNEL_VERSION,
    WORKER_HEARTBEAT_CAPABILITY,
    CleanupAckFrame,
    CleanupMessageFrame,
    CleanupOperationResultFrame,
    CleanupReleaseFrame,
    CleanupRenewFrame,
    WorkerReadyFrame,
)
from prefect.types._datetime import DateTime, now
from prefect.workers._cleanup import (
    CleanupExecutionResult,
    CleanupOperationFrame,
    CleanupOperationResultAction,
    WorkerCleanupExecutor,
    WorkerCleanupHandlerRegistry,
)
from prefect.workers._worker_channel._protocol import WorkerChannelProtocolHandler
from prefect.workers._worker_channel._state import (
    ActiveWorkerChannelSession,
    WorkerChannelConnection,
    WorkerChannelTerminalError,
)
from prefect.workers._worker_channel._sync import WorkPoolWorkerChannel
from prefect.workers.base import BaseJobConfiguration, BaseWorker, BaseWorkerResult


class WorkerTestImpl(BaseWorker[BaseJobConfiguration, Any, BaseWorkerResult]):
    type = "cleanup-test"

    async def run(self):
        pass


class RecordingCleanupHandler:
    def __init__(
        self,
        cleanup_kind: str = CANCELLING_TIMEOUT_TEARDOWN,
        result: CleanupExecutionResult | None = None,
        wait_for: anyio.Event | None = None,
        started: anyio.Event | None = None,
    ):
        self.cleanup_kind = cleanup_kind
        self.result = result
        self.wait_for = wait_for
        self.started = started
        self.messages = []

    async def cleanup(self, message):
        self.messages.append(message)
        if self.started is not None:
            self.started.set()
        if self.wait_for is not None:
            await self.wait_for.wait()
        return self.result


class CancellableCleanupHandler:
    cleanup_kind = CANCELLING_TIMEOUT_TEARDOWN

    def __init__(self):
        self.started = anyio.Event()
        self.cancelled = anyio.Event()

    async def cleanup(self, message):
        self.started.set()
        try:
            await anyio.sleep_forever()
        finally:
            self.cancelled.set()


class QueueWorkerChannelWebSocket:
    def __init__(self, messages: list[dict[str, Any] | BaseException] | None = None):
        self._send_stream, self._receive_stream = anyio.create_memory_object_stream[
            dict[str, Any] | BaseException
        ](100)
        self.sent: list[dict[str, Any]] = []
        for message in messages or []:
            self._send_stream.send_nowait(message)

    async def send(self, message: str) -> None:
        self.sent.append(orjson.loads(message))

    async def recv(self) -> str:
        message = await self._receive_stream.receive()
        if isinstance(message, BaseException):
            raise message
        return orjson.dumps(message).decode()

    async def put(self, message: dict[str, Any] | BaseException) -> None:
        await self._send_stream.send(message)


class FakeWorkerChannelConnect:
    def __init__(self, websocket: QueueWorkerChannelWebSocket):
        self.websocket = websocket
        self.exited = False

    async def __aenter__(self) -> QueueWorkerChannelWebSocket:
        return self.websocket

    async def __aexit__(self, *exc_info: Any) -> None:
        self.exited = True


def _worker_ready_frame(
    consumer_id,
    *,
    cleanup_delivery: bool = True,
    effective_max_cleanup_concurrency: int | None = None,
):
    accepted_capabilities = [
        WORKER_HEARTBEAT_CAPABILITY,
        WORK_POOL_SNAPSHOT_CAPABILITY,
    ]
    if cleanup_delivery:
        accepted_capabilities.append(CLEANUP_DELIVERY_CAPABILITY)

    return WorkerReadyFrame.model_validate(
        {
            "type": "worker.ready.v1",
            "id": str(uuid7()),
            "sent_at": now("UTC").isoformat(),
            "payload": {
                "consumer_id": str(consumer_id),
                "worker_id": None,
                "selected_channel_version": WORK_POOL_WORKER_CHANNEL_VERSION,
                "effective_heartbeat_interval_seconds": 30,
                "accepted_capabilities": accepted_capabilities,
                "rejected_capabilities": [],
                "effective_max_cleanup_concurrency": (
                    effective_max_cleanup_concurrency
                    if effective_max_cleanup_concurrency is not None
                    else 1
                    if cleanup_delivery
                    else 0
                ),
                "resolved_work_queues": [],
                "initial_snapshot": {
                    "snapshot_sequence": 1,
                    "reason": "initial",
                    "work_pool": {
                        "id": str(uuid4()),
                        "name": "test-work-pool",
                        "type": "test",
                        "base_job_template": {},
                        "is_paused": False,
                        "storage_configuration": {},
                        "default_queue_id": str(uuid4()),
                    },
                },
            },
        }
    )


def _message_frame(
    *,
    kind: str = CANCELLING_TIMEOUT_TEARDOWN,
    reservation_token: str = "token",
    lease_expires_at: DateTime | None = None,
) -> CleanupMessageFrame:
    target: dict[str, str | None] = {"flow_run_id": str(uuid4())}
    if kind == PENDING_CLAIM_TEARDOWN:
        target["claim_id"] = str(uuid7())

    return CleanupMessageFrame.model_validate(
        {
            "type": "cleanup.message.v1",
            "id": str(uuid7()),
            "sent_at": now("UTC").isoformat(),
            "payload": {
                "message_id": str(uuid4()),
                "kind": kind,
                "reservation_token": reservation_token,
                "lease_expires_at": (
                    lease_expires_at or now("UTC") + timedelta(minutes=5)
                ).isoformat(),
                "delivery_count": 1,
                "work_queue_id": None,
                "target": target,
                "data": {},
            },
        }
    )


def _operation_name(frame: CleanupOperationFrame) -> str:
    if isinstance(frame, CleanupAckFrame):
        return "ack"
    if isinstance(frame, CleanupReleaseFrame):
        return "release"
    if isinstance(frame, CleanupRenewFrame):
        return "renew"
    raise TypeError(f"Unexpected frame: {frame!r}")


def _operation_result(
    frame: CleanupOperationFrame,
    *,
    status: str = "accepted",
    lease_expires_at: DateTime | None = None,
) -> CleanupOperationResultFrame:
    payload = {
        "request_frame_id": str(frame.id),
        "message_id": str(frame.payload.message_id),
        "operation": _operation_name(frame),
        "status": status,
        "reason": None if status == "accepted" else status,
        "detail": None,
    }
    if isinstance(frame, CleanupRenewFrame) and status == "accepted":
        payload["lease_expires_at"] = (
            lease_expires_at or now("UTC") + timedelta(minutes=5)
        ).isoformat()

    return CleanupOperationResultFrame.model_validate(
        {
            "type": "cleanup.operation_result.v1",
            "id": str(uuid7()),
            "sent_at": now("UTC").isoformat(),
            "payload": payload,
        }
    )


async def test_registry_advertises_declared_cleanup_kinds():
    handler = RecordingCleanupHandler()
    registry = WorkerCleanupHandlerRegistry([handler])

    assert registry.handled_cleanup_kinds == (CANCELLING_TIMEOUT_TEARDOWN,)
    assert registry.get(CANCELLING_TIMEOUT_TEARDOWN) is handler


async def test_registry_rejects_duplicate_cleanup_kinds():
    handler = RecordingCleanupHandler()

    with pytest.raises(ValueError, match="already registered"):
        WorkerCleanupHandlerRegistry([handler, handler])


async def test_worker_advertises_cleanup_only_when_handlers_are_available():
    no_cleanup_worker = WorkerTestImpl(work_pool_name="test", limit=10)

    assert no_cleanup_worker.handled_cleanup_kinds == ()
    assert no_cleanup_worker.max_cleanup_concurrency == 0
    assert no_cleanup_worker._cleanup_delivery_available() is False

    cleanup_worker = WorkerTestImpl(
        work_pool_name="test",
        limit=10,
        _cleanup_handlers=[RecordingCleanupHandler()],
    )

    assert cleanup_worker.handled_cleanup_kinds == (CANCELLING_TIMEOUT_TEARDOWN,)
    assert cleanup_worker.max_cleanup_concurrency == 1
    assert cleanup_worker._cleanup_delivery_available() is True


async def test_protocol_advertises_cleanup_capability_from_executor():
    async def worker_metadata():
        return None

    cleanup_worker = WorkerTestImpl(
        work_pool_name="test",
        _cleanup_handlers=[RecordingCleanupHandler()],
        _max_cleanup_concurrency=2,
    )
    protocol = WorkerChannelProtocolHandler(
        consumer_id=uuid7(),
        worker_name="test-worker",
        worker_type="test",
        heartbeat_interval_seconds=30,
        work_queue_names=["default"],
        create_pool_if_not_found=True,
        default_base_job_template={},
        worker_metadata=worker_metadata,
        classify_closed_connection=lambda exc: WorkerChannelTerminalError(
            "connection_lost", str(exc)
        ),
        logger=logging.getLogger("test-worker-channel"),
        cleanup_executor=cleanup_worker._create_cleanup_executor(),
    )

    hello = await protocol.build_hello_frame()

    assert hello.payload.requested_capabilities == [
        WORKER_HEARTBEAT_CAPABILITY,
        WORK_POOL_SNAPSHOT_CAPABILITY,
        CLEANUP_DELIVERY_CAPABILITY,
    ]
    assert hello.payload.handled_cleanup_kinds == [CANCELLING_TIMEOUT_TEARDOWN]
    assert hello.payload.max_cleanup_concurrency == 2


async def test_protocol_applies_effective_cleanup_concurrency_from_ready():
    async def worker_metadata():
        return None

    executor = WorkerCleanupExecutor(
        [RecordingCleanupHandler()],
        max_concurrency=2,
    )
    protocol = WorkerChannelProtocolHandler(
        consumer_id=uuid7(),
        worker_name="test-worker",
        worker_type="test",
        heartbeat_interval_seconds=30,
        work_queue_names=["default"],
        create_pool_if_not_found=True,
        default_base_job_template={},
        worker_metadata=worker_metadata,
        classify_closed_connection=lambda exc: WorkerChannelTerminalError(
            "connection_lost", str(exc)
        ),
        logger=logging.getLogger("test-worker-channel"),
        cleanup_executor=executor,
    )
    websocket = QueueWorkerChannelWebSocket()
    connection = WorkerChannelConnection(
        FakeWorkerChannelConnect(websocket),
        websocket,
        _worker_ready_frame(
            protocol.consumer_id,
            effective_max_cleanup_concurrency=1,
        ),
    )

    async with executor:
        async with anyio.create_task_group() as task_group:
            task_group.start_soon(protocol.run_connected, connection)

            with anyio.fail_after(1):
                while executor.max_concurrency != 1:
                    await anyio.sleep(0)

            task_group.cancel_scope.cancel()

    assert executor.max_concurrency == 1


async def test_active_session_waits_for_required_capability_before_sending():
    session = ActiveWorkerChannelSession()
    frame = CleanupAckFrame.model_validate(
        {
            "type": "cleanup.ack.v1",
            "id": str(uuid7()),
            "sent_at": now("UTC").isoformat(),
            "payload": {
                "message_id": str(uuid4()),
                "reservation_token": "token",
            },
        }
    )
    websocket_without_cleanup = QueueWorkerChannelWebSocket()
    websocket_with_cleanup = QueueWorkerChannelWebSocket()
    connection_without_cleanup = WorkerChannelConnection(
        FakeWorkerChannelConnect(websocket_without_cleanup),
        websocket_without_cleanup,
        _worker_ready_frame(uuid7(), cleanup_delivery=False),
    )
    connection_with_cleanup = WorkerChannelConnection(
        FakeWorkerChannelConnect(websocket_with_cleanup),
        websocket_with_cleanup,
        _worker_ready_frame(uuid7(), cleanup_delivery=True),
    )

    async def send_frame():
        await session.send(
            frame,
            required_capability=CLEANUP_DELIVERY_CAPABILITY,
        )

    async with anyio.create_task_group() as task_group:
        task_group.start_soon(send_frame)
        session.activate(connection_without_cleanup)
        await anyio.sleep(0)

        assert websocket_without_cleanup.sent == []

        session.activate(connection_with_cleanup)

        with anyio.fail_after(1):
            while not websocket_with_cleanup.sent:
                await anyio.sleep(0)

    assert websocket_with_cleanup.sent[0]["type"] == "cleanup.ack.v1"


async def test_worker_uses_cleanup_concurrency_override_separate_from_flow_limit():
    worker = WorkerTestImpl(
        work_pool_name="test",
        limit=20,
        _cleanup_handlers=[RecordingCleanupHandler()],
        _max_cleanup_concurrency=2,
    )

    assert worker.max_cleanup_concurrency == 2
    assert worker._limit == 20


async def test_executor_acks_successful_cleanup():
    sent: list[CleanupOperationFrame] = []

    async def send(frame: CleanupOperationFrame):
        sent.append(frame)
        return _operation_result(frame)

    handler = RecordingCleanupHandler(result=CleanupExecutionResult.success())
    executor = WorkerCleanupExecutor([handler], send_operation=send)
    message = _message_frame()

    await executor.execute(message)

    assert handler.messages == [message.payload]
    assert len(sent) == 1
    assert isinstance(sent[0], CleanupAckFrame)


async def test_executor_releases_when_handler_cannot_act():
    sent: list[CleanupOperationFrame] = []

    async def send(frame: CleanupOperationFrame):
        sent.append(frame)
        return _operation_result(frame)

    handler = RecordingCleanupHandler(
        result=CleanupExecutionResult.release("missing_infrastructure_handle")
    )
    executor = WorkerCleanupExecutor([handler], send_operation=send)

    await executor.execute(_message_frame())

    assert len(sent) == 1
    assert isinstance(sent[0], CleanupReleaseFrame)
    assert sent[0].payload.reason == "missing_infrastructure_handle"


async def test_executor_releases_unsupported_cleanup_kind():
    sent: list[CleanupOperationFrame] = []

    async def send(frame: CleanupOperationFrame):
        sent.append(frame)
        return _operation_result(frame)

    executor = WorkerCleanupExecutor(
        [RecordingCleanupHandler(CANCELLING_TIMEOUT_TEARDOWN)],
        send_operation=send,
    )

    await executor.execute(_message_frame(kind=PENDING_CLAIM_TEARDOWN))

    assert len(sent) == 1
    assert isinstance(sent[0], CleanupReleaseFrame)
    assert sent[0].payload.reason == "unsupported_cleanup_kind"


async def test_executor_enforces_cleanup_concurrency():
    sent: list[CleanupOperationFrame] = []
    started = anyio.Event()
    finish_first = anyio.Event()

    async def send(frame: CleanupOperationFrame):
        sent.append(frame)
        return _operation_result(frame)

    handler = RecordingCleanupHandler(wait_for=finish_first, started=started)
    executor = WorkerCleanupExecutor(
        [handler],
        send_operation=send,
        max_concurrency=1,
    )
    first = _message_frame(reservation_token="first")
    second = _message_frame(reservation_token="second")

    async with anyio.create_task_group() as task_group:
        task_group.start_soon(executor.execute, first)
        await started.wait()

        await executor.execute(second)

        assert executor.in_flight_count == 1
        finish_first.set()

    assert [type(frame) for frame in sent] == [CleanupReleaseFrame, CleanupAckFrame]
    assert sent[0].payload.reason == "concurrency_limit_reached"


async def test_executor_renews_lease_before_acknowledging_success():
    sent: list[CleanupOperationFrame] = []
    finish_cleanup = anyio.Event()

    async def send(frame: CleanupOperationFrame):
        sent.append(frame)
        return _operation_result(
            frame,
            lease_expires_at=now("UTC") + timedelta(minutes=5),
        )

    handler = RecordingCleanupHandler(wait_for=finish_cleanup)
    executor = WorkerCleanupExecutor(
        [handler],
        send_operation=send,
        lease_renewal_buffer_seconds=30,
    )
    message = _message_frame(lease_expires_at=now("UTC") + timedelta(seconds=1))

    async with anyio.create_task_group() as task_group:
        task_group.start_soon(executor.execute, message)
        while not any(isinstance(frame, CleanupRenewFrame) for frame in sent):
            await anyio.sleep(0)
        finish_cleanup.set()

    assert [type(frame) for frame in sent] == [CleanupRenewFrame, CleanupAckFrame]


async def test_executor_keeps_renewing_until_ack_resolves():
    sent: list[CleanupOperationFrame] = []
    ack_frame: CleanupAckFrame | None = None
    ack_sent = anyio.Event()
    renew_sent = anyio.Event()
    executor: WorkerCleanupExecutor

    async def send(frame: CleanupOperationFrame):
        nonlocal ack_frame
        sent.append(frame)
        if isinstance(frame, CleanupAckFrame):
            ack_frame = frame
            ack_sent.set()
            return None
        if isinstance(frame, CleanupRenewFrame):
            renew_sent.set()
            return _operation_result(
                frame,
                lease_expires_at=now("UTC") + timedelta(minutes=5),
            )
        return _operation_result(frame)

    executor = WorkerCleanupExecutor(
        [RecordingCleanupHandler(result=CleanupExecutionResult.success())],
        send_operation=send,
        lease_renewal_buffer_seconds=0.05,
        operation_result_timeout_seconds=1,
    )
    message = _message_frame(lease_expires_at=now("UTC") + timedelta(seconds=0.1))

    async with anyio.create_task_group() as task_group:
        task_group.start_soon(executor.execute, message)

        with anyio.fail_after(1):
            await ack_sent.wait()
            await renew_sent.wait()

        assert ack_frame is not None
        executor.handle_operation_result(_operation_result(ack_frame))

    assert [type(frame) for frame in sent] == [CleanupAckFrame, CleanupRenewFrame]


async def test_executor_cancels_handler_when_renew_loses_reservation():
    sent: list[CleanupOperationFrame] = []

    async def send(frame: CleanupOperationFrame):
        sent.append(frame)
        if isinstance(frame, CleanupRenewFrame):
            return _operation_result(frame, status="not_current")
        return _operation_result(frame)

    handler = CancellableCleanupHandler()
    executor = WorkerCleanupExecutor(
        [handler],
        send_operation=send,
        lease_renewal_buffer_seconds=30,
    )
    message = _message_frame(lease_expires_at=now("UTC") + timedelta(seconds=1))

    with anyio.fail_after(1):
        await executor.execute(message)

    assert handler.started.is_set()
    assert handler.cancelled.is_set()
    assert [type(frame) for frame in sent] == [CleanupRenewFrame]


async def test_executor_cancels_handler_when_renewal_misses_lease_deadline():
    sent: list[CleanupOperationFrame] = []

    async def send(frame: CleanupOperationFrame):
        sent.append(frame)
        return None

    handler = CancellableCleanupHandler()
    executor = WorkerCleanupExecutor(
        [handler],
        send_operation=send,
        lease_renewal_buffer_seconds=30,
        operation_result_timeout_seconds=0.01,
        operation_retry_delay_seconds=0,
        max_operation_attempts=1,
    )
    message = _message_frame(lease_expires_at=now("UTC") + timedelta(seconds=0.01))

    with anyio.fail_after(1):
        await executor.execute(message)

    assert handler.started.is_set()
    assert handler.cancelled.is_set()
    assert [type(frame) for frame in sent] == [CleanupRenewFrame]


async def test_executor_retries_cleanup_operation_after_lost_result():
    sent: list[CleanupOperationFrame] = []

    async def send(frame: CleanupOperationFrame):
        sent.append(frame)
        if len(sent) == 1:
            return None
        return _operation_result(frame)

    executor = WorkerCleanupExecutor(
        [RecordingCleanupHandler(result=CleanupExecutionResult.success())],
        send_operation=send,
        operation_result_timeout_seconds=0.01,
        operation_retry_delay_seconds=0,
        max_operation_attempts=2,
    )

    await executor.execute(_message_frame())

    assert [type(frame) for frame in sent] == [CleanupAckFrame, CleanupAckFrame]


async def test_executor_matches_async_operation_results_from_channel():
    sent: list[CleanupOperationFrame] = []
    executor: WorkerCleanupExecutor

    async def send(frame: CleanupOperationFrame):
        sent.append(frame)
        executor.handle_operation_result(_operation_result(frame))

    executor = WorkerCleanupExecutor(
        [RecordingCleanupHandler(result=CleanupExecutionResult.success())],
        send_operation=send,
    )

    await executor.execute(_message_frame())

    assert len(sent) == 1
    assert isinstance(sent[0], CleanupAckFrame)


async def test_channel_keeps_cleanup_execution_alive_across_reconnects():
    started = anyio.Event()
    finish_cleanup = anyio.Event()
    handler = RecordingCleanupHandler(
        result=CleanupExecutionResult.success(),
        wait_for=finish_cleanup,
        started=started,
    )
    executor = WorkerCleanupExecutor(
        [handler],
        operation_result_timeout_seconds=1,
        operation_retry_delay_seconds=0,
        max_operation_attempts=2,
    )
    second_websockets: list[QueueWorkerChannelWebSocket] = []
    channel: WorkPoolWorkerChannel

    async def worker_metadata():
        return None

    def connect_factory(*args: Any, **kwargs: Any) -> FakeWorkerChannelConnect:
        websocket = QueueWorkerChannelWebSocket(
            [
                {"type": "auth_success"},
                _worker_ready_frame(channel.consumer_id).model_dump(mode="json"),
            ]
        )
        second_websockets.append(websocket)
        return FakeWorkerChannelConnect(websocket)

    channel = WorkPoolWorkerChannel(
        client=Mock(server_type=ServerType.SERVER),
        api_url="http://localhost:4200/api",
        work_pool_is_available=lambda: True,
        work_pool_name="test-work-pool",
        worker_name="test-worker",
        worker_type="test",
        heartbeat_interval_seconds=30,
        work_queue_names=[],
        create_pool_if_not_found=True,
        default_base_job_template={},
        worker_metadata=worker_metadata,
        logger=logging.getLogger("test-worker-channel"),
        cleanup_executor=executor,
        reconnect_base_seconds=0,
        connect_factory=connect_factory,
    )
    message = _message_frame()
    first_websocket = QueueWorkerChannelWebSocket(
        [
            message.model_dump(mode="json"),
            OSError("connection dropped"),
        ]
    )
    first_connect = FakeWorkerChannelConnect(first_websocket)
    initial_connection = WorkerChannelConnection(
        first_connect,
        first_websocket,
        _worker_ready_frame(channel.consumer_id),
    )

    async with anyio.create_task_group() as task_group:
        task_group.start_soon(channel._run, initial_connection)

        with anyio.fail_after(1):
            await started.wait()
            while not first_connect.exited or not second_websockets:
                await anyio.sleep(0)

        assert first_websocket.sent == []

        finish_cleanup.set()

        with anyio.fail_after(1):
            ack_data = None
            while ack_data is None:
                for sent in second_websockets[-1].sent:
                    if sent["type"] == "cleanup.ack.v1":
                        ack_data = sent
                        break
                await anyio.sleep(0)

        ack = CleanupAckFrame.model_validate(ack_data)
        await second_websockets[-1].put(_operation_result(ack).model_dump(mode="json"))

        with anyio.fail_after(1):
            while executor.in_flight_count:
                await anyio.sleep(0)

        task_group.cancel_scope.cancel()

    assert handler.messages == [message.payload]


@pytest.mark.parametrize(
    "status,operation_frame,expected",
    [
        ("accepted", CleanupAckFrame, CleanupOperationResultAction.ACCEPTED),
        ("not_current", CleanupAckFrame, CleanupOperationResultAction.LOST_RESERVATION),
        ("expired", CleanupAckFrame, CleanupOperationResultAction.LOST_RESERVATION),
        (
            "invalid_token",
            CleanupAckFrame,
            CleanupOperationResultAction.LOST_RESERVATION,
        ),
        (
            "unauthorized",
            CleanupAckFrame,
            CleanupOperationResultAction.LOST_RESERVATION,
        ),
        (
            "dead_lettered",
            CleanupReleaseFrame,
            CleanupOperationResultAction.LOST_RESERVATION,
        ),
        ("not_found", CleanupAckFrame, CleanupOperationResultAction.ACK_NOT_FOUND),
        (
            "not_found",
            CleanupReleaseFrame,
            CleanupOperationResultAction.LOST_RESERVATION,
        ),
        ("error", CleanupAckFrame, CleanupOperationResultAction.RETRYABLE_ERROR),
    ],
)
async def test_executor_classifies_operation_results(
    status: str,
    operation_frame: type[CleanupOperationFrame],
    expected: CleanupOperationResultAction,
):
    executor = WorkerCleanupExecutor([], send_operation=lambda frame: None)
    message = _message_frame()
    frame = executor._build_operation_frame(
        operation=_operation_name_for_frame_type(operation_frame),
        message_id=message.payload.message_id,
        reservation_token=message.payload.reservation_token,
        reason="cannot_act" if operation_frame is CleanupReleaseFrame else None,
    )

    result = _operation_result(frame, status=status)

    assert executor.classify_operation_result(result) is expected


def _operation_name_for_frame_type(
    frame_type: type[CleanupOperationFrame],
) -> str:
    if frame_type is CleanupAckFrame:
        return "ack"
    if frame_type is CleanupReleaseFrame:
        return "release"
    if frame_type is CleanupRenewFrame:
        return "renew"
    raise TypeError(f"Unexpected frame type: {frame_type!r}")
