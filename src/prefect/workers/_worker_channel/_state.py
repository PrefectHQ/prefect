from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

import anyio.abc
import websockets.asyncio.client
import websockets.exceptions

from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.worker_channel import (
    WorkerChannelCapability,
    WorkerChannelFrame,
    WorkerReadyFrame,
)


class WorkerChannelStatus(str, Enum):
    CONNECTING = "connecting"
    HEALTHY = "healthy"
    FALLBACK_RETRYING = "fallback_retrying"
    DISABLED = "disabled"


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
class WorkerChannelState:
    status: WorkerChannelStatus = WorkerChannelStatus.FALLBACK_RETRYING
    reason: str | None = None

    @property
    def rest_fallback_enabled(self) -> bool:
        return self.status != WorkerChannelStatus.HEALTHY

    @property
    def healthy(self) -> bool:
        return self.status == WorkerChannelStatus.HEALTHY

    @property
    def terminal(self) -> bool:
        return self.status == WorkerChannelStatus.DISABLED

    def mark_connecting(self) -> None:
        self.status = WorkerChannelStatus.CONNECTING
        self.reason = None

    def mark_healthy(self) -> None:
        self.status = WorkerChannelStatus.HEALTHY
        self.reason = None

    def mark_unhealthy(self, reason: str | None = None) -> None:
        self.status = WorkerChannelStatus.FALLBACK_RETRYING
        self.reason = reason

    def mark_terminal(self, reason: str | None = None) -> None:
        self.status = WorkerChannelStatus.DISABLED
        self.reason = reason


WorkerChannelFallbackState = WorkerChannelState


@dataclass
class WorkerChannelSession:
    """One successfully negotiated worker-channel WebSocket session."""

    connect_context: websockets.asyncio.client.connect
    websocket: websockets.asyncio.client.ClientConnection
    ready: WorkerReadyFrame


class CurrentWorkerChannelSession:
    """Routes sends through the currently active session across reconnects."""

    def __init__(self) -> None:
        self._session: WorkerChannelSession | None = None
        self._changed: asyncio.Event | None = None

    def activate(self, session: WorkerChannelSession) -> None:
        self._session = session
        self._notify_changed()

    def deactivate(self, session: WorkerChannelSession) -> None:
        if self._session is session:
            self._session = None
            self._notify_changed()

    async def send(
        self,
        frame: WorkerChannelFrame,
        *,
        required_capability: WorkerChannelCapability | None = None,
    ) -> None:
        while True:
            changed = self._changed_event()
            session = self._session
            if session is not None and self._supports(session, required_capability):
                try:
                    await session.websocket.send(frame.model_dump_json())
                    return
                except websockets.exceptions.ConnectionClosed:
                    self.deactivate(session)

            await changed.wait()

    def _changed_event(self) -> asyncio.Event:
        if self._changed is None:
            self._changed = asyncio.Event()
        return self._changed

    def _notify_changed(self) -> None:
        changed = self._changed
        self._changed = asyncio.Event()
        if changed is not None:
            changed.set()

    @staticmethod
    def _supports(
        session: WorkerChannelSession,
        required_capability: WorkerChannelCapability | None,
    ) -> bool:
        return (
            required_capability is None
            or required_capability in session.ready.payload.accepted_capabilities
        )


class WorkerChannel(Protocol):
    @property
    def rest_fallback_enabled(self) -> bool: ...

    def set_client(self, client: PrefectClient) -> None: ...

    async def sync(self, task_group: anyio.abc.TaskGroup | None) -> None: ...

    def stop(self) -> None: ...
