from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from logging import Logger
from typing import Any
from uuid import UUID

import anyio
import orjson
import websockets.asyncio.client
import websockets.exceptions
from pydantic import ValidationError

from prefect._internal.uuid7 import uuid7
from prefect.client.schemas.objects import WorkerMetadata, WorkPool
from prefect.client.schemas.worker_channel import (
    CLEANUP_DELIVERY_CAPABILITY,
    WORK_POOL_SNAPSHOT_CAPABILITY,
    WORK_POOL_WORKER_CHANNEL_VERSION,
    WORKER_HEARTBEAT_CAPABILITY,
    CleanupMessageFrame,
    CleanupOperationResultFrame,
    WorkerChannelAuthSuccess,
    WorkerChannelCloseReason,
    WorkerHeartbeatFrame,
    WorkerHelloFrame,
    WorkerReadyFrame,
    WorkPoolSnapshotFrame,
    validate_worker_channel_frame,
)
from prefect.settings import get_current_settings
from prefect.types._datetime import now
from prefect.workers._cleanup import CleanupOperationFrame, WorkerCleanupExecutor
from prefect.workers._worker_channel._state import (
    CurrentWorkerChannelSession,
    WorkerChannelError,
    WorkerChannelRetryableError,
    WorkerChannelSession,
    WorkerChannelTerminalError,
)


class WorkerChannelProtocolHandler:
    def __init__(
        self,
        *,
        consumer_id: UUID,
        worker_name: str,
        worker_type: str,
        heartbeat_interval_seconds: int,
        work_queue_names: list[str],
        create_pool_if_not_found: bool,
        default_base_job_template: dict[str, Any],
        worker_metadata: Callable[[], Awaitable[WorkerMetadata | None]],
        classify_closed_connection: Callable[
            [websockets.exceptions.ConnectionClosed], WorkerChannelError
        ],
        logger: Logger,
        on_worker_id: Callable[[UUID], None] | None = None,
        on_work_pool_snapshot: Callable[[WorkPool], None] | None = None,
        cleanup_executor: WorkerCleanupExecutor | None = None,
    ):
        self.consumer_id = consumer_id
        self.worker_name = worker_name
        self.worker_type = worker_type
        self.heartbeat_interval_seconds = heartbeat_interval_seconds
        self.work_queue_names = work_queue_names
        self.create_pool_if_not_found = create_pool_if_not_found
        self.default_base_job_template = default_base_job_template
        self._worker_metadata = worker_metadata
        self._classify_closed_connection = classify_closed_connection
        self._logger = logger
        self._on_worker_id = on_worker_id
        self._on_work_pool_snapshot = on_work_pool_snapshot
        self._cleanup_executor = cleanup_executor
        self._current_session = CurrentWorkerChannelSession()
        self._worker_id: UUID | None = None
        self._worker_metadata_sent = False

    @property
    def worker_id(self) -> UUID | None:
        return self._worker_id

    @property
    def worker_metadata_sent(self) -> bool:
        return self._worker_metadata_sent

    async def handshake(
        self, websocket: websockets.asyncio.client.ClientConnection
    ) -> WorkerReadyFrame:
        await websocket.send(
            orjson.dumps({"type": "auth", "token": self._auth_token()}).decode()
        )
        auth = await self._recv_json(websocket)
        try:
            WorkerChannelAuthSuccess.model_validate(auth)
        except ValidationError as exc:
            raise self._terminal_error_from_setup_message(
                auth, "Worker channel authentication failed"
            ) from exc

        hello = await self.build_hello_frame()
        await websocket.send(hello.model_dump_json())

        ready_payload = await self._recv_json(websocket)
        ready_frame = validate_worker_channel_frame(ready_payload)
        if not isinstance(ready_frame, WorkerReadyFrame):
            raise WorkerChannelTerminalError(
                WorkerChannelCloseReason.PROTOCOL_ERROR.value,
                "Expected worker.ready.v1 during worker channel setup",
            )

        self._validate_ready(ready_frame)
        self._handle_ready(ready_frame)
        if hello.payload.worker_metadata:
            self.record_worker_metadata_sent()
        return ready_frame

    async def build_hello_frame(self) -> WorkerHelloFrame:
        metadata_payload = None
        if not self._worker_metadata_sent:
            worker_metadata = await self._worker_metadata()
            metadata_payload = (
                worker_metadata.model_dump(mode="json") if worker_metadata else None
            )

        requested_capabilities = [
            WORKER_HEARTBEAT_CAPABILITY,
            WORK_POOL_SNAPSHOT_CAPABILITY,
        ]
        handled_cleanup_kinds = []
        max_cleanup_concurrency = 0
        if self._cleanup_delivery_requested():
            requested_capabilities.append(CLEANUP_DELIVERY_CAPABILITY)
            assert self._cleanup_executor is not None
            handled_cleanup_kinds = list(self._cleanup_executor.handled_cleanup_kinds)
            max_cleanup_concurrency = self._cleanup_executor.max_concurrency

        return WorkerHelloFrame(
            type="worker.hello.v1",
            id=uuid7(),
            sent_at=now("UTC"),
            payload={
                "consumer_id": self.consumer_id,
                "worker_name": self.worker_name,
                "worker_type": self.worker_type,
                "heartbeat_interval_seconds": self.heartbeat_interval_seconds,
                "supported_channel_versions": [WORK_POOL_WORKER_CHANNEL_VERSION],
                "requested_capabilities": requested_capabilities,
                "work_queue_names": self.work_queue_names,
                "handled_cleanup_kinds": handled_cleanup_kinds,
                "max_cleanup_concurrency": max_cleanup_concurrency,
                "create_pool_if_not_found": self.create_pool_if_not_found,
                "default_base_job_template": self.default_base_job_template,
                "worker_metadata": metadata_payload,
            },
        )

    def _validate_ready(self, ready: WorkerReadyFrame) -> None:
        if ready.payload.consumer_id != self.consumer_id:
            raise WorkerChannelTerminalError(
                WorkerChannelCloseReason.PROTOCOL_ERROR.value,
                "Worker channel ready frame consumer_id did not match hello",
            )

        if (
            CLEANUP_DELIVERY_CAPABILITY in ready.payload.accepted_capabilities
            and not self._cleanup_delivery_requested()
        ):
            raise WorkerChannelTerminalError(
                WorkerChannelCloseReason.PROTOCOL_ERROR.value,
                "Worker channel accepted cleanup_delivery.v1 even though the worker "
                "did not request it",
            )

    def _handle_ready(self, ready: WorkerReadyFrame) -> None:
        self.handle_work_pool_snapshot(ready.payload.initial_snapshot.work_pool)
        worker_id = ready.payload.worker_id
        if worker_id is not None:
            self.record_worker_id(worker_id)

    def handle_work_pool_snapshot(self, work_pool: WorkPool) -> None:
        if self._on_work_pool_snapshot is not None:
            self._on_work_pool_snapshot(work_pool)

    def record_worker_id(self, worker_id: UUID) -> None:
        self._worker_id = worker_id
        if self._on_worker_id is not None:
            self._on_worker_id(worker_id)

    def record_worker_metadata_sent(self) -> None:
        self._worker_metadata_sent = True

    async def run_session(self, session: WorkerChannelSession) -> None:
        cleanup_delivery_enabled = (
            CLEANUP_DELIVERY_CAPABILITY in session.ready.payload.accepted_capabilities
        )
        self._current_session.activate(session)
        if cleanup_delivery_enabled and self._cleanup_executor is not None:
            self._cleanup_executor.set_max_concurrency(
                session.ready.payload.effective_max_cleanup_concurrency
            )
            self._cleanup_executor.set_operation_sender(self._send_cleanup_operation)

        try:
            heartbeat_task = asyncio.create_task(
                self._heartbeat_loop(
                    session.websocket,
                    session.ready.payload.effective_heartbeat_interval_seconds,
                )
            )
            receive_task = asyncio.create_task(
                self._receive_loop(
                    session.websocket,
                    cleanup_delivery_enabled=cleanup_delivery_enabled,
                )
            )
            tasks = {heartbeat_task, receive_task}

            try:
                done, pending = await asyncio.wait(
                    tasks, return_when=asyncio.FIRST_EXCEPTION
                )
            except BaseException:
                for task in tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                raise

            for task in pending:
                task.cancel()

            await asyncio.gather(*pending, return_exceptions=True)

            for task in done:
                exception = task.exception()
                if exception:
                    if isinstance(exception, WorkerChannelError):
                        raise exception
                    if isinstance(exception, websockets.exceptions.ConnectionClosed):
                        raise self._classify_closed_connection(exception) from exception
                    raise WorkerChannelRetryableError(
                        "connection_lost",
                        "Worker channel connection was lost",
                    ) from exception

            raise WorkerChannelRetryableError(
                "connection_closed",
                "Worker channel connection closed",
            )
        finally:
            self._current_session.deactivate(session)

    async def _heartbeat_loop(
        self,
        websocket: websockets.asyncio.client.ClientConnection,
        heartbeat_interval_seconds: int,
    ) -> None:
        while True:
            await anyio.sleep(heartbeat_interval_seconds)
            frame = WorkerHeartbeatFrame(
                type="worker.heartbeat.v1",
                id=uuid7(),
                sent_at=now("UTC"),
                payload={
                    "consumer_id": self.consumer_id,
                    "worker_name": self.worker_name,
                    "heartbeat_interval_seconds": heartbeat_interval_seconds,
                },
            )
            await websocket.send(frame.model_dump_json())

    async def _receive_loop(
        self,
        websocket: websockets.asyncio.client.ClientConnection,
        *,
        cleanup_delivery_enabled: bool,
    ) -> None:
        while True:
            try:
                frame = validate_worker_channel_frame(await self._recv_json(websocket))
            except orjson.JSONDecodeError as exc:
                raise WorkerChannelTerminalError(
                    WorkerChannelCloseReason.PROTOCOL_ERROR.value,
                    "Worker channel received invalid JSON",
                ) from exc
            except ValidationError as exc:
                raise WorkerChannelTerminalError(
                    WorkerChannelCloseReason.PROTOCOL_ERROR.value,
                    "Worker channel received a malformed protocol frame",
                ) from exc

            if isinstance(frame, WorkPoolSnapshotFrame):
                self.handle_work_pool_snapshot(frame.payload.work_pool)
                continue

            if isinstance(frame, CleanupMessageFrame):
                if not cleanup_delivery_enabled or self._cleanup_executor is None:
                    raise WorkerChannelTerminalError(
                        WorkerChannelCloseReason.PROTOCOL_ERROR.value,
                        "Worker channel received cleanup work without accepted "
                        "cleanup delivery",
                    )
                self._cleanup_executor.submit(frame)
                continue

            if isinstance(frame, CleanupOperationResultFrame):
                if not cleanup_delivery_enabled or self._cleanup_executor is None:
                    raise WorkerChannelTerminalError(
                        WorkerChannelCloseReason.PROTOCOL_ERROR.value,
                        "Worker channel received cleanup operation result without "
                        "accepted cleanup delivery",
                    )
                self._cleanup_executor.handle_operation_result(frame)
                continue

            raise WorkerChannelTerminalError(
                WorkerChannelCloseReason.PROTOCOL_ERROR.value,
                f"Worker channel received unsupported frame type {frame.type!r}",
            )

    async def _send_cleanup_operation(
        self,
        frame: CleanupOperationFrame,
    ) -> None:
        await self._current_session.send(
            frame,
            required_capability=CLEANUP_DELIVERY_CAPABILITY,
        )

    def _cleanup_delivery_requested(self) -> bool:
        return (
            self._cleanup_executor is not None
            and bool(self._cleanup_executor.handled_cleanup_kinds)
            and self._cleanup_executor.max_concurrency > 0
        )

    async def _recv_json(
        self, websocket: websockets.asyncio.client.ClientConnection
    ) -> Any:
        try:
            return orjson.loads(await websocket.recv())
        except orjson.JSONDecodeError as exc:
            raise WorkerChannelTerminalError(
                WorkerChannelCloseReason.PROTOCOL_ERROR.value,
                "Worker channel received invalid JSON",
            ) from exc
        except websockets.exceptions.ConnectionClosed as exc:
            raise self._classify_closed_connection(exc) from exc

    def _terminal_error_from_setup_message(
        self, message: Any, default_message: str
    ) -> WorkerChannelTerminalError:
        reason = message.get("reason") if isinstance(message, dict) else None
        try:
            close_reason = WorkerChannelCloseReason(reason)
        except ValueError:
            close_reason = WorkerChannelCloseReason.PROTOCOL_ERROR

        return WorkerChannelTerminalError(close_reason.value, default_message)

    def _auth_token(self) -> str | None:
        settings = get_current_settings()
        auth_token = (
            settings.api.auth_string.get_secret_value()
            if settings.api.auth_string
            else None
        )
        api_key = settings.api.key.get_secret_value() if settings.api.key else None
        return auth_token or api_key
