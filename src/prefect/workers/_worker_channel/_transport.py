from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from logging import Logger
from urllib.parse import quote

import anyio
import websockets
import websockets.asyncio.client
import websockets.exceptions
from pydantic import ValidationError

from prefect._internal.websockets import websocket_connect
from prefect.client.schemas.worker_channel import (
    WORK_POOL_WORKER_CHANNEL_ROUTE,
    WORKER_CHANNEL_CLOSE_POLICIES,
    WORKER_CHANNEL_SUBPROTOCOL,
    WorkerChannelCloseReason,
    WorkerChannelProtocolError,
    WorkerReadyFrame,
)
from prefect.workers._worker_channel._state import (
    WorkerChannelError,
    WorkerChannelRetryableError,
    WorkerChannelSession,
    WorkerChannelTerminalError,
)

ConnectFactory = Callable[..., websockets.asyncio.client.connect]
WORKER_CHANNEL_SETUP_TIMEOUT_SECONDS = 10.0


def build_worker_channel_url(api_url: str, work_pool_name: str) -> str:
    base_url = api_url.replace("http", "ws", 1).rstrip("/")
    route = WORK_POOL_WORKER_CHANNEL_ROUTE.format(
        work_pool_name=quote(work_pool_name, safe="")
    )
    return f"{base_url}{route}"


class WorkerChannelTransport:
    def __init__(
        self,
        *,
        api_url: str | None,
        work_pool_name: str,
        logger: Logger,
        connect_factory: ConnectFactory = websocket_connect,
        reconnect_base_seconds: float = 1.0,
        reconnect_max_seconds: float = 30.0,
        setup_timeout_seconds: float | None = None,
    ):
        self.url = (
            build_worker_channel_url(api_url, work_pool_name) if api_url else None
        )
        self._logger = logger
        self._connect_factory = connect_factory
        self._reconnect_base_seconds = reconnect_base_seconds
        self._reconnect_max_seconds = reconnect_max_seconds
        self._setup_timeout_seconds = (
            setup_timeout_seconds
            if setup_timeout_seconds is not None
            else WORKER_CHANNEL_SETUP_TIMEOUT_SECONDS
        )
        self._has_been_healthy = False

    def mark_healthy_once(self) -> None:
        self._has_been_healthy = True

    async def connect_with_timeout(
        self,
        handshake: Callable[
            [websockets.asyncio.client.ClientConnection],
            Awaitable[WorkerReadyFrame],
        ],
    ) -> WorkerChannelSession:
        if self._setup_timeout_seconds <= 0:
            return await self.connect_once(handshake)

        try:
            with anyio.fail_after(self._setup_timeout_seconds):
                return await self.connect_once(handshake)
        except TimeoutError as exc:
            raise WorkerChannelRetryableError(
                "setup_timeout",
                "Worker channel setup timed out",
            ) from exc

    async def connect_once(
        self,
        handshake: Callable[
            [websockets.asyncio.client.ClientConnection],
            Awaitable[WorkerReadyFrame],
        ],
    ) -> WorkerChannelSession:
        if self.url is None:
            raise WorkerChannelTerminalError(
                "endpoint_unavailable",
                "Worker channel endpoint is unavailable",
            )

        connect_context: websockets.asyncio.client.connect | None = None
        entered = False
        session_returned = False
        try:
            connect_context = self._connect_factory(
                self.url,
                subprotocols=[websockets.Subprotocol(WORKER_CHANNEL_SUBPROTOCOL)],
            )
            websocket = await connect_context.__aenter__()
            entered = True

            ready = await handshake(websocket)
            session_returned = True
            return WorkerChannelSession(connect_context, websocket, ready)
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
            raise self.classify_setup_exception(exc) from exc
        finally:
            if entered and connect_context is not None and not session_returned:
                try:
                    await connect_context.__aexit__(None, None, None)
                except Exception:
                    self._logger.debug(
                        "Failed to close worker channel setup connection",
                        exc_info=True,
                    )

    def classify_setup_exception(self, exc: Exception) -> WorkerChannelError:
        if isinstance(exc, websockets.exceptions.ConnectionClosed):
            return self.classify_closed_connection(exc)

        status_code = self._status_code_from_exception(exc)
        if status_code is not None:
            if status_code == 401:
                return WorkerChannelTerminalError(
                    WorkerChannelCloseReason.AUTHENTICATION_FAILED.value,
                    "Worker channel setup was rejected by the server",
                )
            if status_code == 403:
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

    def classify_closed_connection(
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

    _MAX_RECONNECT_EXPONENT = 32

    def reconnect_delay(self, attempt: int) -> float:
        if self._reconnect_base_seconds <= 0:
            return 0
        exponent = max(attempt - 1, 0)
        if exponent >= self._MAX_RECONNECT_EXPONENT:
            return self._reconnect_max_seconds
        return min(
            self._reconnect_base_seconds * 2**exponent,
            self._reconnect_max_seconds,
        )

    async def close_session(self, session: WorkerChannelSession) -> None:
        try:
            await session.connect_context.__aexit__(None, None, None)
        except Exception:
            self._logger.debug("Failed to close worker channel", exc_info=True)
