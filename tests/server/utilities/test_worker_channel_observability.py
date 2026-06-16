"""Tests for worker channel observability (metrics and logging)."""

from __future__ import annotations

import logging
from uuid import uuid4

import pytest

from prefect.client.schemas.worker_channel import CANCELLING_TIMEOUT_TEARDOWN
from prefect.server.utilities import worker_channel as worker_channel_module
from prefect.server.worker_communication.cleanup_queue import (
    CLEANUP_QUEUE_OPERATIONS,
    record_cleanup_queue_operation,
)
from prefect.server.worker_communication.cleanup_queue.memory import (
    WorkerCleanupQueue,
)


@pytest.fixture
def queue() -> WorkerCleanupQueue:
    q = WorkerCleanupQueue()
    q.clear()
    return q


class TestCleanupQueueOperationMetrics:
    async def test_enqueue_records_accepted(
        self, queue: WorkerCleanupQueue, caplog: pytest.LogCaptureFixture
    ) -> None:
        work_pool_id = uuid4()
        message_id = uuid4()
        with caplog.at_level(logging.DEBUG):
            await queue.enqueue(
                message_id=message_id,
                idempotency_key="test-key",
                work_pool_id=work_pool_id,
                kind=CANCELLING_TIMEOUT_TEARDOWN,
                target={"flow_run_id": str(uuid4())},
            )

        assert any(
            "operation=enqueue" in r.message and "status=accepted" in r.message
            for r in caplog.records
        )

    async def test_enqueue_records_duplicate(
        self, queue: WorkerCleanupQueue, caplog: pytest.LogCaptureFixture
    ) -> None:
        work_pool_id = uuid4()
        message_id = uuid4()
        await queue.enqueue(
            message_id=message_id,
            idempotency_key="test-key",
            work_pool_id=work_pool_id,
            kind=CANCELLING_TIMEOUT_TEARDOWN,
            target={"flow_run_id": str(uuid4())},
        )

        with caplog.at_level(logging.DEBUG):
            await queue.enqueue(
                message_id=message_id,
                idempotency_key="test-key",
                work_pool_id=work_pool_id,
                kind=CANCELLING_TIMEOUT_TEARDOWN,
                target={"flow_run_id": str(uuid4())},
            )

        assert any(
            "operation=enqueue" in r.message and "status=duplicate" in r.message
            for r in caplog.records
        )

    async def test_reserve_records_accepted(
        self, queue: WorkerCleanupQueue, caplog: pytest.LogCaptureFixture
    ) -> None:
        work_pool_id = uuid4()
        await queue.enqueue(
            message_id=uuid4(),
            idempotency_key="test-key",
            work_pool_id=work_pool_id,
            kind=CANCELLING_TIMEOUT_TEARDOWN,
            target={"flow_run_id": str(uuid4())},
        )

        with caplog.at_level(logging.DEBUG):
            reservation = await queue.reserve(
                work_pool_id=work_pool_id,
                cleanup_kinds=[CANCELLING_TIMEOUT_TEARDOWN],
            )

        assert reservation is not None
        assert any(
            "operation=reserve" in r.message and "status=accepted" in r.message
            for r in caplog.records
        )

    async def test_ack_records_accepted(
        self, queue: WorkerCleanupQueue, caplog: pytest.LogCaptureFixture
    ) -> None:
        work_pool_id = uuid4()
        await queue.enqueue(
            message_id=uuid4(),
            idempotency_key="test-key",
            work_pool_id=work_pool_id,
            kind=CANCELLING_TIMEOUT_TEARDOWN,
            target={"flow_run_id": str(uuid4())},
        )
        reservation = await queue.reserve(
            work_pool_id=work_pool_id,
            cleanup_kinds=[CANCELLING_TIMEOUT_TEARDOWN],
        )
        assert reservation is not None

        with caplog.at_level(logging.DEBUG):
            result = await queue.ack(
                work_pool_id=work_pool_id,
                message_id=reservation.message_id,
                reservation_token=reservation.reservation_token,
            )

        assert result.status == "accepted"
        assert any(
            "operation=ack" in r.message and "status=accepted" in r.message
            for r in caplog.records
        )

    async def test_release_records_accepted(
        self, queue: WorkerCleanupQueue, caplog: pytest.LogCaptureFixture
    ) -> None:
        work_pool_id = uuid4()
        await queue.enqueue(
            message_id=uuid4(),
            idempotency_key="test-key",
            work_pool_id=work_pool_id,
            kind=CANCELLING_TIMEOUT_TEARDOWN,
            target={"flow_run_id": str(uuid4())},
        )
        reservation = await queue.reserve(
            work_pool_id=work_pool_id,
            cleanup_kinds=[CANCELLING_TIMEOUT_TEARDOWN],
        )
        assert reservation is not None

        with caplog.at_level(logging.DEBUG):
            result = await queue.release(
                work_pool_id=work_pool_id,
                message_id=reservation.message_id,
                reservation_token=reservation.reservation_token,
                reason="test_release",
            )

        assert result.status == "accepted"
        assert any(
            "operation=release" in r.message and "status=accepted" in r.message
            for r in caplog.records
        )

    async def test_renew_records_accepted(
        self, queue: WorkerCleanupQueue, caplog: pytest.LogCaptureFixture
    ) -> None:
        work_pool_id = uuid4()
        await queue.enqueue(
            message_id=uuid4(),
            idempotency_key="test-key",
            work_pool_id=work_pool_id,
            kind=CANCELLING_TIMEOUT_TEARDOWN,
            target={"flow_run_id": str(uuid4())},
        )
        reservation = await queue.reserve(
            work_pool_id=work_pool_id,
            cleanup_kinds=[CANCELLING_TIMEOUT_TEARDOWN],
        )
        assert reservation is not None

        with caplog.at_level(logging.DEBUG):
            result = await queue.renew(
                work_pool_id=work_pool_id,
                message_id=reservation.message_id,
                reservation_token=reservation.reservation_token,
            )

        assert result.status == "accepted"
        assert any(
            "operation=renew" in r.message and "status=accepted" in r.message
            for r in caplog.records
        )


class TestCleanupQueueOperationMetricCounter:
    def test_record_cleanup_queue_operation_increments_counter(self) -> None:
        if CLEANUP_QUEUE_OPERATIONS is None:
            pytest.skip("prometheus_client not available")

        work_pool_id = uuid4()
        before = CLEANUP_QUEUE_OPERATIONS.labels(
            operation="enqueue", status="accepted"
        )._value.get()
        record_cleanup_queue_operation(
            "enqueue",
            status="accepted",
            work_pool_id=work_pool_id,
            message_id=uuid4(),
            cleanup_kind=CANCELLING_TIMEOUT_TEARDOWN,
        )
        after = CLEANUP_QUEUE_OPERATIONS.labels(
            operation="enqueue", status="accepted"
        )._value.get()
        assert after == before + 1


class TestWorkerChannelConnectionMetrics:
    def test_metric_constants_defined(self) -> None:
        assert worker_channel_module.WORKER_CHANNEL_CONNECTIONS is not None
        assert worker_channel_module.WORKER_CHANNEL_CLOSE_REASONS is not None
        assert worker_channel_module.WORKER_CHANNEL_SNAPSHOTS is not None
        assert worker_channel_module.WORKER_CHANNEL_HEARTBEAT_FAILURES is not None
        assert worker_channel_module.WORKER_CHANNEL_CLEANUP_DELIVERIES is not None


class TestWorkerChannelConfigDiagnostics:
    def test_log_worker_channel_config(self, caplog: pytest.LogCaptureFixture) -> None:
        from prefect.server.api.server import _log_worker_channel_config

        with caplog.at_level(logging.INFO):
            _log_worker_channel_config()

        assert any(
            "Worker channel configuration" in r.message
            and "cleanup_queue_storage" in r.message
            and "cleanup_lease_seconds" in r.message
            for r in caplog.records
        )
