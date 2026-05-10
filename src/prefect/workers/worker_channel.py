from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from logging import Logger
from typing import Any
from urllib.parse import quote
from uuid import UUID

import anyio
import orjson
import websockets
import websockets.asyncio.client
import websockets.exceptions
from pydantic import ValidationError

from prefect._internal.uuid7 import uuid7
from prefect._internal.websockets import websocket_connect
from prefect.client.schemas.objects import WorkerMetadata
from prefect.client.schemas.worker_channel import (
    CLEANUP_DELIVERY_CAPABILITY,
    WORK_POOL_SNAPSHOT_CAPABILITY,
    WORK_POOL_WORKER_CHANNEL_ROUTE,
    WORK_POOL_WORKER_CHANNEL_VERSION,
    WORKER_CHANNEL_CLOSE_POLICIES,
    WORKER_CHANNEL_SUBPROTOCOL,
    WORKER_HEARTBEAT_CAPABILITY,
    WorkerChannelAuthSuccess,
    WorkerChannelCloseReason,
    WorkerChannelProtocolError,
    WorkerHeartbeatFrame,
    WorkerHelloFrame,
    WorkerReadyFrame,
    WorkPoolSnapshotFrame,
    validate_worker_channel_frame,
)
from prefect.settings import get_current_settings
from prefect.types._datetime import now

ConnectFactory = Callable[..., websockets.asyncio.client.connect]


def build_worker_channel_url(api_url: str, work_pool_name: str) -> str:
    base_url = api_url.replace("http", "ws", 1).rstrip("/")
    route = WORK_POOL_WORKER_CHANNEL_ROUTE.format(
        work_pool_name=quote(work_pool_name, safe="")
    )
    return f"{base_url}{route}"


class WorkerChannelError(Exception):
    pass


class WorkerChannelTerminalError(WorkerChannelError):
    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


class WorkerChannelRetryableError(WorkerChannelError):
    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


@dataclass
class WorkerChannelFallbackState:
    rest_fallback_enabled: bool = True
    healthy: bool = False
    terminal: bool = False
    reason: str | None = None

    def mark_connecting(self) -> None:
        self.rest_fallback_enabled = True
        self.healthy = False
        self.reason = None

    def mark_healthy(self) -> None:
        self.rest_fallback_enabled = False
        self.healthy = True
        self.terminal = False
        self.reason = None

    def mark_unhealthy(self, reason: str | None = None) -> None:
        self.rest_fallback_enabled = True
        self.healthy = False
        self.reason = reason

    def mark_terminal(self, reason: str | None = None) -> None:
        self.rest_fallback_enabled = True
        self.healthy = False
        self.terminal = True
        self.reason = reason


@dataclass
class WorkerChannelConnection:
    connect_context: websockets.asyncio.client.connect
    websocket: websockets.asyncio.client.ClientConnection
    ready: WorkerReadyFrame


class WorkPoolWorkerChannel:
    def __init__(
        self,
        *,
        api_url: str,
        work_pool_name: str,
        worker_name: str,
        worker_type: str,
        heartbeat_interval_seconds: int,
        work_queue_names: list[str],
        create_pool_if_not_found: bool,
        default_base_job_template: dict[str, Any],
        worker_metadata: Callable[[], Awaitable[WorkerMetadata | None]],
        logger: Logger,
        on_worker_id: Callable[[UUID], None] | None = None,
        on_worker_metadata_sent: Callable[[], None] | None = None,
        connect_factory: ConnectFactory = websocket_connect,
        reconnect_base_seconds: float = 1.0,
        reconnect_max_seconds: float = 30.0,
    ):
        self.api_url = api_url
        self.work_pool_name = work_pool_name
        self.worker_name = worker_name
        self.worker_type = worker_type
        self.heartbeat_interval_seconds = heartbeat_interval_seconds
        self.work_queue_names = work_queue_names
        self.create_pool_if_not_found = create_pool_if_not_found
        self.default_base_job_template = default_base_job_template
        self._worker_metadata = worker_metadata
        self._logger = logger
        self._on_worker_id = on_worker_id
        self._on_worker_metadata_sent = on_worker_metadata_sent
        self._connect_factory = connect_factory
        self._reconnect_base_seconds = reconnect_base_seconds
        self._reconnect_max_seconds = reconnect_max_seconds

        self.consumer_id = uuid7()
        self.url = build_worker_channel_url(api_url, work_pool_name)
        self.state = WorkerChannelFallbackState()
        self._has_been_healthy = False

    @property
    def rest_fallback_enabled(self) -> bool:
        return self.state.rest_fallback_enabled

    async def run(self) -> None:
        reconnect_attempt = 0

        while not self.state.terminal:
            connection: WorkerChannelConnection | None = None
            try:
                self.state.mark_connecting()
                connection = await self._connect_once()
                reconnect_attempt = 0
                self._has_been_healthy = True
                self.state.mark_healthy()
                await self._run_connected(connection)
            except WorkerChannelTerminalError as exc:
                self.state.mark_terminal(exc.reason)
                self._logger.debug("Worker channel disabled: %s", exc)
                return
            except WorkerChannelRetryableError as exc:
                self.state.mark_unhealthy(exc.reason)
                self._logger.debug(
                    "Worker channel unhealthy, REST fallback is active: %s", exc
                )
            except BaseException:
                raise
            finally:
                if connection is not None:
                    await self._close_connection(connection)

            reconnect_attempt += 1
            await anyio.sleep(self._reconnect_delay(reconnect_attempt))

    async def _connect_once(self) -> WorkerChannelConnection:
        connect_context: websockets.asyncio.client.connect | None = None
        entered = False
        connection_returned = False
        try:
            connect_context = self._connect_factory(
                self.url,
                subprotocols=[websockets.Subprotocol(WORKER_CHANNEL_SUBPROTOCOL)],
            )
            websocket = await connect_context.__aenter__()
            entered = True

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

            hello = await self._hello_frame()
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
            if hello.payload.worker_metadata and self._on_worker_metadata_sent:
                self._on_worker_metadata_sent()
            connection_returned = True
            return WorkerChannelConnection(connect_context, websocket, ready_frame)
        except asyncio.CancelledError:
            raise
        except (WorkerChannelTerminalError, WorkerChannelRetryableError):
            raise
        except WorkerChannelProtocolError as exc:
            raise WorkerChannelTerminalError(exc.close_reason.value, str(exc)) from exc
        except ValidationError as exc:
            raise WorkerChannelTerminalError(
                WorkerChannelCloseReason.PROTOCOL_ERROR.value,
                "Worker channel setup received a malformed protocol frame",
            ) from exc
        except Exception as exc:
            raise self._classify_setup_exception(exc) from exc
        finally:
            if entered and connect_context is not None and not connection_returned:
                try:
                    await connect_context.__aexit__(None, None, None)
                except Exception:
                    self._logger.debug(
                        "Failed to close worker channel setup connection",
                        exc_info=True,
                    )

    async def _hello_frame(self) -> WorkerHelloFrame:
        worker_metadata = await self._worker_metadata()
        metadata_payload = (
            worker_metadata.model_dump(mode="json") if worker_metadata else None
        )

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
                "requested_capabilities": [
                    WORKER_HEARTBEAT_CAPABILITY,
                    WORK_POOL_SNAPSHOT_CAPABILITY,
                ],
                "work_queue_names": self.work_queue_names,
                "handled_cleanup_kinds": [],
                "max_cleanup_concurrency": 0,
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

        if CLEANUP_DELIVERY_CAPABILITY in ready.payload.accepted_capabilities:
            raise WorkerChannelTerminalError(
                WorkerChannelCloseReason.PROTOCOL_ERROR.value,
                "Worker channel accepted cleanup_delivery.v1 even though the worker "
                "did not request it",
            )

    def _handle_ready(self, ready: WorkerReadyFrame) -> None:
        worker_id = ready.payload.worker_id
        if worker_id is not None and self._on_worker_id is not None:
            self._on_worker_id(worker_id)

    async def _run_connected(self, connection: WorkerChannelConnection) -> None:
        heartbeat_task = asyncio.create_task(
            self._heartbeat_loop(
                connection.websocket,
                connection.ready.payload.effective_heartbeat_interval_seconds,
            )
        )
        receive_task = asyncio.create_task(self._receive_loop(connection.websocket))
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
                raise WorkerChannelRetryableError(
                    "connection_lost",
                    "Worker channel connection was lost",
                ) from exception

        raise WorkerChannelRetryableError(
            "connection_closed",
            "Worker channel connection closed",
        )

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
        self, websocket: websockets.asyncio.client.ClientConnection
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
                continue

            raise WorkerChannelTerminalError(
                WorkerChannelCloseReason.PROTOCOL_ERROR.value,
                f"Worker channel received unsupported frame type {frame.type!r}",
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

    def _classify_setup_exception(self, exc: Exception) -> WorkerChannelError:
        if isinstance(exc, websockets.exceptions.ConnectionClosed):
            return self._classify_closed_connection(exc)

        status_code = self._status_code_from_exception(exc)
        if status_code is not None:
            if status_code in {401, 403}:
                return WorkerChannelTerminalError(
                    WorkerChannelCloseReason.AUTHORIZATION_FAILED.value,
                    "Worker channel setup was rejected by the server",
                )
            if status_code in {404, 405}:
                return WorkerChannelTerminalError(
                    "endpoint_unavailable",
                    "Worker channel endpoint is unavailable",
                )
            if status_code >= 500:
                return WorkerChannelRetryableError(
                    WorkerChannelCloseReason.TRANSIENT_SERVER_ERROR.value,
                    "Worker channel setup failed due to a transient server error",
                )
            return WorkerChannelTerminalError(
                "endpoint_unavailable",
                "Worker channel setup failed during HTTP upgrade",
            )

        if isinstance(
            exc,
            (
                ConnectionError,
                OSError,
                websockets.exceptions.InvalidHandshake,
                websockets.exceptions.InvalidURI,
            ),
        ):
            if self._has_been_healthy:
                return WorkerChannelRetryableError(
                    "connection_lost",
                    "Worker channel reconnect failed",
                )
            return WorkerChannelTerminalError(
                "endpoint_unavailable",
                "Worker channel endpoint is unavailable",
            )

        return WorkerChannelRetryableError(
            WorkerChannelCloseReason.TRANSIENT_SERVER_ERROR.value,
            "Worker channel setup failed due to a transient error",
        )

    def _classify_closed_connection(
        self, exc: websockets.exceptions.ConnectionClosed
    ) -> WorkerChannelError:
        reason = getattr(getattr(exc, "rcvd", None), "reason", None) or ""
        code = getattr(getattr(exc, "rcvd", None), "code", None)

        try:
            close_reason = WorkerChannelCloseReason(reason)
        except ValueError:
            close_reason = None

        if close_reason is not None:
            policy = WORKER_CHANNEL_CLOSE_POLICIES[close_reason]
            if policy.retryable:
                return WorkerChannelRetryableError(close_reason.value, str(exc))
            return WorkerChannelTerminalError(close_reason.value, str(exc))

        if code == 1008:
            return WorkerChannelTerminalError(
                WorkerChannelCloseReason.AUTHORIZATION_FAILED.value,
                str(exc),
            )
        if code == 1002:
            return WorkerChannelTerminalError(
                WorkerChannelCloseReason.PROTOCOL_ERROR.value,
                str(exc),
            )
        if code == 1011:
            return WorkerChannelRetryableError(
                WorkerChannelCloseReason.TRANSIENT_SERVER_ERROR.value,
                str(exc),
            )

        return WorkerChannelRetryableError("connection_lost", str(exc))

    @staticmethod
    def _status_code_from_exception(exc: Exception) -> int | None:
        status_code = getattr(exc, "status_code", None)
        if status_code is not None:
            return int(status_code)

        response = getattr(exc, "response", None)
        status_code = getattr(response, "status_code", None)
        if status_code is not None:
            return int(status_code)

        return None

    def _reconnect_delay(self, attempt: int) -> float:
        if self._reconnect_base_seconds <= 0:
            return 0
        return min(
            self._reconnect_base_seconds * 2 ** max(attempt - 1, 0),
            self._reconnect_max_seconds,
        )

    async def _close_connection(self, connection: WorkerChannelConnection) -> None:
        try:
            await connection.connect_context.__aexit__(None, None, None)
        except Exception:
            self._logger.debug("Failed to close worker channel", exc_info=True)
