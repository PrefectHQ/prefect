from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any
from uuid import uuid4

import anyio
import pytest

from prefect._internal.uuid7 import uuid7
from prefect.client.schemas.worker_channel import (
    CANCELLING_TIMEOUT_TEARDOWN,
    CLEANUP_DELIVERY_CAPABILITY,
    PENDING_CLAIM_TEARDOWN,
    WORK_POOL_SNAPSHOT_CAPABILITY,
    WORKER_HEARTBEAT_CAPABILITY,
    CleanupAckFrame,
    CleanupMessageFrame,
    CleanupOperationResultFrame,
    CleanupReleaseFrame,
    CleanupRenewFrame,
)
from prefect.types._datetime import DateTime, now
from prefect.workers._worker_channel._protocol import WorkerChannelProtocolHandler
from prefect.workers._worker_channel._state import WorkerChannelTerminalError
from prefect.workers.base import BaseJobConfiguration, BaseWorker, BaseWorkerResult
from prefect.workers.cleanup import (
    CleanupExecutionResult,
    CleanupOperationFrame,
    CleanupOperationResultAction,
    WorkerCleanupExecutor,
    WorkerCleanupHandlerRegistry,
)


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
