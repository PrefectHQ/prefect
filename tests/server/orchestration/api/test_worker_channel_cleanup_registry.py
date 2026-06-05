import asyncio
import uuid
from collections.abc import Iterable
from datetime import timedelta
from uuid import UUID

import pytest
from starlette.websockets import WebSocketDisconnect

from prefect.client.schemas.worker_channel import (
    CleanupAckFrame,
    CleanupKind,
    CleanupMessageFrame,
    CleanupReleaseFrame,
    CleanupRenewFrame,
)
from prefect.server.utilities import worker_channel as worker_channel_utils
from prefect.server.utilities import (
    worker_channel_cleanup as worker_channel_cleanup_utils,
)
from prefect.server.worker_communication.cleanup_queue import (
    CleanupQueueOperation,
    CleanupQueueReservation,
)
from prefect.types._datetime import now
from tests.server.orchestration.api.worker_channel_cleanup_test_utils import (
    BlockingCleanupMessageWebSocket,
    BlockingOperationResultWebSocket,
    CancellingWebSocket,
    DisconnectingOperationResultWebSocket,
    DisconnectingWebSocket,
    ErrorAckCleanupQueue,
    InstrumentedMemoryCleanupQueue,
    RaisingAckCleanupQueue,
    RecordingWebSocket,
    ToggleFailingReserveCleanupQueue,
    _cleanup_ack_frame,
    _cleanup_release_frame,
    _cleanup_renew_frame,
    enqueue_cleanup_message,
    make_cleanup_connection,
    sent_cleanup_messages,
    sent_cleanup_operation_results,
    worker_ready_frame_for_connection,
)
from tests.server.orchestration.api.worker_channel_cleanup_test_utils import (
    patch_events_client as patch_events_client,
)

pytestmark = pytest.mark.clear_db


class TestWorkerCleanupConnectionRegistry:
    async def test_send_loop_handles_cleanup_dispatch_failure(self, work_pool):
        cleanup_queue = ToggleFailingReserveCleanupQueue()
        cleanup_queue.reserve_should_fail = True
        websocket = RecordingWebSocket()
        registry = worker_channel_utils.WorkerCleanupConnectionRegistry()
        connection = make_cleanup_connection(
            work_pool=work_pool,
            cleanup_queue=cleanup_queue,
            registry=registry,
            websocket=websocket,
            ready=False,
        )
        ready = worker_ready_frame_for_connection(connection, work_pool)

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
        connection = make_cleanup_connection(
            work_pool=work_pool,
            cleanup_queue=cleanup_queue,
            registry=registry,
            websocket=websocket,
            ready=False,
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
        connection = make_cleanup_connection(
            work_pool=work_pool,
            cleanup_queue=cleanup_queue,
            registry=registry,
            websocket=websocket,
        )

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

    async def test_slow_cleanup_send_does_not_block_other_dispatchers(self, work_pool):
        cleanup_queue = InstrumentedMemoryCleanupQueue()
        first = await enqueue_cleanup_message(cleanup_queue, work_pool_id=work_pool.id)
        second = await enqueue_cleanup_message(cleanup_queue, work_pool_id=work_pool.id)
        registry = worker_channel_utils.WorkerCleanupConnectionRegistry()
        slow_websocket = BlockingCleanupMessageWebSocket()
        healthy_websocket = RecordingWebSocket()
        slow_connection = make_cleanup_connection(
            work_pool=work_pool,
            cleanup_queue=cleanup_queue,
            registry=registry,
            websocket=slow_websocket,
            worker_name="slow-worker",
        )
        healthy_connection = make_cleanup_connection(
            work_pool=work_pool,
            cleanup_queue=cleanup_queue,
            registry=registry,
            websocket=healthy_websocket,
            worker_name="healthy-worker",
        )

        async with registry.register(slow_connection):
            async with registry.register(healthy_connection):
                slow_dispatch = asyncio.create_task(
                    registry.dispatch_available(
                        work_pool_id=work_pool.id,
                        cleanup_queue=cleanup_queue,
                    )
                )
                await slow_websocket.cleanup_send_started.wait()

                await asyncio.wait_for(
                    registry.dispatch_available(
                        work_pool_id=work_pool.id,
                        cleanup_queue=cleanup_queue,
                    ),
                    timeout=0.5,
                )

                slow_websocket.release_cleanup_send.set()
                await slow_dispatch

        slow_messages = sent_cleanup_messages(slow_websocket)
        healthy_messages = sent_cleanup_messages(healthy_websocket)
        assert [message.payload.message_id for message in slow_messages] == [
            first.message_id
        ]
        assert [message.payload.message_id for message in healthy_messages] == [
            second.message_id
        ]

    async def test_concurrent_dispatches_do_not_over_reserve_one_worker(
        self, work_pool
    ):
        class BlockingReserveCleanupQueue(InstrumentedMemoryCleanupQueue):
            _instance: "BlockingReserveCleanupQueue | None" = None
            _initialized = False

            def __init__(self) -> None:
                super().__init__()
                self.reserve_started = asyncio.Event()
                self.allow_reserve_return = asyncio.Event()
                self.reserve_calls = 0

            async def reserve(
                self,
                *,
                work_pool_id: UUID,
                cleanup_kinds: Iterable[CleanupKind] | None = None,
                preferred_work_queue_ids: Iterable[UUID] | None = None,
                allow_fallback_to_any_queue: bool = True,
            ) -> CleanupQueueReservation | None:
                reservation = await super().reserve(
                    work_pool_id=work_pool_id,
                    cleanup_kinds=cleanup_kinds,
                    preferred_work_queue_ids=preferred_work_queue_ids,
                    allow_fallback_to_any_queue=allow_fallback_to_any_queue,
                )
                if reservation is not None:
                    self.reserve_calls += 1
                    self.reserve_started.set()
                    await self.allow_reserve_return.wait()
                return reservation

        cleanup_queue = BlockingReserveCleanupQueue()
        first = await enqueue_cleanup_message(cleanup_queue, work_pool_id=work_pool.id)
        second = await enqueue_cleanup_message(cleanup_queue, work_pool_id=work_pool.id)
        websocket = RecordingWebSocket()
        registry = worker_channel_utils.WorkerCleanupConnectionRegistry()
        connection = make_cleanup_connection(
            work_pool=work_pool,
            cleanup_queue=cleanup_queue,
            registry=registry,
            websocket=websocket,
            max_cleanup_concurrency=1,
            ready=False,
        )

        async with registry.register(connection):
            background_dispatch = registry._dispatch_tasks_by_work_pool_id[work_pool.id]
            background_dispatch.cancel()
            await asyncio.gather(background_dispatch, return_exceptions=True)
            connection._ready_sent.set()
            first_dispatch = asyncio.create_task(
                registry.dispatch_available(
                    work_pool_id=work_pool.id,
                    cleanup_queue=cleanup_queue,
                )
            )
            second_dispatch: asyncio.Task[None] | None = None
            try:
                await asyncio.wait_for(
                    cleanup_queue.reserve_started.wait(), timeout=0.5
                )
                second_dispatch = asyncio.create_task(
                    registry.dispatch_available(
                        work_pool_id=work_pool.id,
                        cleanup_queue=cleanup_queue,
                    )
                )
                await asyncio.wait_for(second_dispatch, timeout=0.5)
                assert cleanup_queue.reserve_calls == 1
            finally:
                cleanup_queue.allow_reserve_return.set()
                pending_dispatches = [first_dispatch]
                if second_dispatch is not None:
                    pending_dispatches.append(second_dispatch)
                dispatch_results = await asyncio.gather(
                    *pending_dispatches,
                    return_exceptions=True,
                )
                for result in dispatch_results:
                    if isinstance(result, BaseException):
                        raise result

        cleanup_messages = sent_cleanup_messages(websocket)
        assert [message.payload.message_id for message in cleanup_messages] == [
            first.message_id
        ]
        stored_second = await cleanup_queue.read_message(
            work_pool_id=work_pool.id,
            message_id=second.message_id,
        )
        assert stored_second is not None
        assert stored_second.delivery_count == 0
        assert (
            await cleanup_queue.read_dead_letter(
                work_pool_id=work_pool.id,
                message_id=second.message_id,
            )
            is None
        )

    async def test_cleanup_send_cancellation_releases_reserved_message(self, work_pool):
        cleanup_queue = InstrumentedMemoryCleanupQueue()
        message = await enqueue_cleanup_message(
            cleanup_queue, work_pool_id=work_pool.id
        )
        websocket = CancellingWebSocket()
        registry = worker_channel_utils.WorkerCleanupConnectionRegistry()
        connection = make_cleanup_connection(
            work_pool=work_pool,
            cleanup_queue=cleanup_queue,
            registry=registry,
            websocket=websocket,
        )

        async with registry.register(connection):
            with pytest.raises(asyncio.CancelledError):
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
        first_cleanup = CleanupMessageFrame.model_validate(websocket.sent_json[0])

        replacement_websocket = RecordingWebSocket()
        replacement_connection = make_cleanup_connection(
            work_pool=work_pool,
            cleanup_queue=cleanup_queue,
            registry=registry,
            websocket=replacement_websocket,
        )

        async with registry.register(replacement_connection):
            await registry.dispatch_available(
                work_pool_id=work_pool.id,
                cleanup_queue=cleanup_queue,
            )

        redelivered = sent_cleanup_messages(replacement_websocket)
        assert [cleanup.payload.message_id for cleanup in redelivered] == [
            message.message_id
        ]
        assert (
            redelivered[0].payload.reservation_token
            != first_cleanup.payload.reservation_token
        )

    async def test_retryable_operation_error_keeps_cleanup_capacity_in_use(
        self, work_pool
    ):
        cleanup_queue = ErrorAckCleanupQueue()
        first = await enqueue_cleanup_message(cleanup_queue, work_pool_id=work_pool.id)
        second = await enqueue_cleanup_message(cleanup_queue, work_pool_id=work_pool.id)
        websocket = RecordingWebSocket()
        registry = worker_channel_utils.WorkerCleanupConnectionRegistry()
        connection = make_cleanup_connection(
            work_pool=work_pool,
            cleanup_queue=cleanup_queue,
            registry=registry,
            websocket=websocket,
        )

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

        cleanup_messages = sent_cleanup_messages(websocket)
        operation_results = sent_cleanup_operation_results(websocket)
        assert first_cleanup.payload.message_id == first.message_id
        assert second.message_id not in {
            frame.payload.message_id for frame in cleanup_messages
        }
        assert len(cleanup_messages) == 1
        assert operation_results[0]["payload"]["status"] == "error"

    async def test_queue_operation_failure_returns_retryable_result(self, work_pool):
        cleanup_queue = RaisingAckCleanupQueue()
        first = await enqueue_cleanup_message(cleanup_queue, work_pool_id=work_pool.id)
        second = await enqueue_cleanup_message(cleanup_queue, work_pool_id=work_pool.id)
        websocket = RecordingWebSocket()
        registry = worker_channel_utils.WorkerCleanupConnectionRegistry()
        connection = make_cleanup_connection(
            work_pool=work_pool,
            cleanup_queue=cleanup_queue,
            registry=registry,
            websocket=websocket,
        )

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

        cleanup_messages = sent_cleanup_messages(websocket)
        operation_results = sent_cleanup_operation_results(websocket)
        assert [message.payload.message_id for message in cleanup_messages] == [
            first.message_id
        ]
        assert second.message_id not in {
            message.payload.message_id for message in cleanup_messages
        }
        assert operation_results[0]["payload"]["status"] == "error"
        assert operation_results[0]["payload"]["reason"] == (
            "cleanup_queue_operation_failed"
        )

    async def test_release_redelivery_prefers_another_eligible_worker(self, work_pool):
        cleanup_queue = InstrumentedMemoryCleanupQueue()
        message = await enqueue_cleanup_message(
            cleanup_queue, work_pool_id=work_pool.id
        )
        registry = worker_channel_utils.WorkerCleanupConnectionRegistry()
        first_websocket = RecordingWebSocket()
        second_websocket = RecordingWebSocket()
        first_connection = make_cleanup_connection(
            work_pool=work_pool,
            cleanup_queue=cleanup_queue,
            registry=registry,
            websocket=first_websocket,
            worker_name="worker-1",
            ready=False,
        )
        second_connection = make_cleanup_connection(
            work_pool=work_pool,
            cleanup_queue=cleanup_queue,
            registry=registry,
            websocket=second_websocket,
            worker_name="worker-2",
            ready=False,
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

        first_cleanup_messages = sent_cleanup_messages(first_websocket)
        first_operation_results = sent_cleanup_operation_results(first_websocket)
        second_cleanup_messages = sent_cleanup_messages(second_websocket)
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
        connection = make_cleanup_connection(
            work_pool=work_pool,
            cleanup_queue=cleanup_queue,
            registry=registry,
            websocket=websocket,
        )

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
        cleanup_messages = sent_cleanup_messages(websocket)
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
        connection = make_cleanup_connection(
            work_pool=work_pool,
            cleanup_queue=cleanup_queue,
            registry=registry,
            websocket=websocket,
        )

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

        operation_results = sent_cleanup_operation_results(websocket)
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
        connection = make_cleanup_connection(
            work_pool=work_pool,
            cleanup_queue=cleanup_queue,
            registry=registry,
            websocket=websocket,
            consumer_id=consumer_id,
        )

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
        replacement_connection = make_cleanup_connection(
            work_pool=work_pool,
            cleanup_queue=cleanup_queue,
            registry=registry,
            websocket=replacement_websocket,
            consumer_id=consumer_id,
        )

        async with registry.register(replacement_connection):
            await registry.dispatch_available(
                work_pool_id=work_pool.id,
                cleanup_queue=cleanup_queue,
            )

        cleanup_messages = sent_cleanup_messages(replacement_websocket)
        assert [message.payload.message_id for message in cleanup_messages] == [
            expected_message_id
        ]

    async def test_renew_syncs_lease_before_result_send(self, work_pool):
        cleanup_queue = InstrumentedMemoryCleanupQueue()
        first = await enqueue_cleanup_message(cleanup_queue, work_pool_id=work_pool.id)
        second = await enqueue_cleanup_message(cleanup_queue, work_pool_id=work_pool.id)
        websocket = BlockingOperationResultWebSocket()
        registry = worker_channel_utils.WorkerCleanupConnectionRegistry()
        connection = make_cleanup_connection(
            work_pool=work_pool,
            cleanup_queue=cleanup_queue,
            registry=registry,
            websocket=websocket,
        )

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
        connection = make_cleanup_connection(
            work_pool=work_pool,
            cleanup_queue=cleanup_queue,
            registry=registry,
            websocket=websocket,
            max_cleanup_concurrency=2,
        )

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

        cleanup_messages = sent_cleanup_messages(websocket)
        operation_results = sent_cleanup_operation_results(websocket)
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
        first_connection = make_cleanup_connection(
            work_pool=work_pool,
            cleanup_queue=cleanup_queue,
            registry=registry,
            websocket=first_websocket,
            consumer_id=consumer_id,
        )

        async with registry.register(first_connection):
            await registry.dispatch_available(
                work_pool_id=work_pool.id,
                cleanup_queue=cleanup_queue,
            )

        first_cleanup = CleanupMessageFrame.model_validate(first_websocket.sent_json[0])

        second_websocket = RecordingWebSocket()
        second_connection = make_cleanup_connection(
            work_pool=work_pool,
            cleanup_queue=cleanup_queue,
            registry=registry,
            websocket=second_websocket,
            consumer_id=consumer_id,
        )

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

        cleanup_messages = sent_cleanup_messages(second_websocket)
        assert first_cleanup.payload.message_id == first.message_id
        assert [message.payload.message_id for message in cleanup_messages] == [
            second.message_id
        ]
