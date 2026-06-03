import asyncio
import time

import pytest
from starlette.testclient import TestClient

import prefect.server.api.workers as workers_api
from prefect.client.schemas.worker_channel import (
    CANCELLING_TIMEOUT_TEARDOWN,
    CLEANUP_DELIVERY_CAPABILITY,
    PENDING_CLAIM_TEARDOWN,
    WORK_POOL_SNAPSHOT_CAPABILITY,
    WORKER_HEARTBEAT_CAPABILITY,
    CleanupMessageFrame,
    CleanupOperationResultFrame,
    WorkerReadyFrame,
)
from prefect.server.utilities import (
    worker_channel_cleanup as worker_channel_cleanup_utils,
)
from prefect.settings import (
    PREFECT_SERVER_WORKER_CHANNEL_CLEANUP_LEASE_SECONDS,
    temporary_settings,
)
from tests.server.orchestration.api.worker_channel_cleanup_test_utils import (
    InstrumentedMemoryCleanupQueue,
    _authenticate_worker_channel,
    _cleanup_ack_frame,
    _cleanup_release_frame,
    _cleanup_renew_frame,
    _cleanup_worker_hello_frame,
    _connect_worker_channel,
    _worker_hello_frame,
    enqueue_cleanup_message,
)
from tests.server.orchestration.api.worker_channel_cleanup_test_utils import (
    cleanup_queue as cleanup_queue,
)
from tests.server.orchestration.api.worker_channel_cleanup_test_utils import (
    patch_events_client as patch_events_client,
)

pytestmark = pytest.mark.clear_db


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

    async def test_cleanup_capability_is_rejected_when_queue_is_unavailable(
        self,
        test_client: TestClient,
        work_pool,
        monkeypatch: pytest.MonkeyPatch,
    ):
        def fail_queue_init():
            raise RuntimeError("cleanup queue unavailable")

        monkeypatch.setattr(workers_api, "get_worker_cleanup_queue", fail_queue_init)

        with _connect_worker_channel(test_client, work_pool.name) as websocket:
            _authenticate_worker_channel(websocket)
            websocket.send_json(_cleanup_worker_hello_frame(max_cleanup_concurrency=2))

            ready = WorkerReadyFrame.model_validate(websocket.receive_json())

        assert CLEANUP_DELIVERY_CAPABILITY not in ready.payload.accepted_capabilities
        assert ready.payload.rejected_capabilities == [CLEANUP_DELIVERY_CAPABILITY]
        assert ready.payload.effective_max_cleanup_concurrency == 0

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
