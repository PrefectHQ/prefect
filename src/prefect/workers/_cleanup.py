from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol, TypeAlias, cast
from uuid import UUID

import anyio

from prefect._internal.uuid7 import uuid7
from prefect.client.schemas.worker_channel import (
    SUPPORTED_CLEANUP_KINDS,
    CleanupAckFrame,
    CleanupKind,
    CleanupMessageFrame,
    CleanupMessagePayload,
    CleanupOperation,
    CleanupOperationPayload,
    CleanupOperationResultFrame,
    CleanupReleaseFrame,
    CleanupReleasePayload,
    CleanupRenewFrame,
)
from prefect.logging import get_logger
from prefect.types._datetime import DateTime, now

CleanupOperationFrame: TypeAlias = (
    CleanupAckFrame | CleanupReleaseFrame | CleanupRenewFrame
)
CleanupOperationSender: TypeAlias = Callable[
    [CleanupOperationFrame],
    Awaitable[CleanupOperationResultFrame | None] | CleanupOperationResultFrame | None,
]


@dataclass(frozen=True)
class CleanupExecutionResult:
    operation: CleanupOperation
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.operation not in {"ack", "release"}:
            raise ValueError("Cleanup execution results must ack or release")
        if self.operation == "release" and not self.reason:
            raise ValueError("Cleanup release results require a reason")

    @classmethod
    def success(cls) -> CleanupExecutionResult:
        return cls("ack")

    @classmethod
    def noop(cls) -> CleanupExecutionResult:
        return cls.success()

    @classmethod
    def release(cls, reason: str) -> CleanupExecutionResult:
        return cls("release", reason=reason)


class WorkerCleanupHandler(Protocol):
    async def cleanup(
        self, message: CleanupMessagePayload
    ) -> CleanupExecutionResult | None:
        """
        Cleanup handlers must be idempotent.

        Returning `None` is treated as idempotent success.
        """


class WorkerCleanupHandlerRegistry:
    def __init__(self, handlers: Iterable[WorkerCleanupHandler] = ()):
        self._handlers: dict[CleanupKind, WorkerCleanupHandler] = {}
        for handler in handlers:
            self.register(handler)

    def __bool__(self) -> bool:
        return bool(self._handlers)

    @property
    def handled_cleanup_kinds(self) -> tuple[CleanupKind, ...]:
        return tuple(sorted(self._handlers))

    def register(self, handler: WorkerCleanupHandler) -> None:
        for kind in self._handler_kinds(handler):
            if kind not in SUPPORTED_CLEANUP_KINDS:
                raise ValueError(f"Unsupported cleanup kind: {kind!r}")
            if kind in self._handlers:
                raise ValueError(f"Cleanup handler already registered for {kind!r}")
            self._handlers[kind] = handler

    def get(self, kind: CleanupKind) -> WorkerCleanupHandler | None:
        return self._handlers.get(kind)

    @staticmethod
    def _handler_kinds(handler: WorkerCleanupHandler) -> tuple[CleanupKind, ...]:
        cleanup_kinds = getattr(handler, "cleanup_kinds", None)
        if cleanup_kinds is None:
            cleanup_kind = getattr(handler, "cleanup_kind", None)
            if cleanup_kind is None:
                raise ValueError(
                    "Cleanup handlers must define `cleanup_kind` or `cleanup_kinds`"
                )
            cleanup_kinds = (cleanup_kind,)

        if isinstance(cleanup_kinds, str):
            cleanup_kinds = (cleanup_kinds,)
        kinds = tuple(cleanup_kinds)
        if not kinds:
            raise ValueError("Cleanup handlers must declare at least one cleanup kind")
        return cast(tuple[CleanupKind, ...], kinds)


class CleanupOperationResultAction(str, Enum):
    ACCEPTED = "accepted"
    LOST_RESERVATION = "lost_reservation"
    ACK_NOT_FOUND = "ack_not_found"
    RETRYABLE_ERROR = "retryable_error"
    IGNORED = "ignored"


_LOST_RESERVATION_STATUSES = {
    "not_current",
    "expired",
    "invalid_token",
    "unauthorized",
    "dead_lettered",
}


@dataclass
class _PendingOperation:
    frame: CleanupOperationFrame
    future: asyncio.Future[CleanupOperationResultFrame]


@dataclass
class _ReservationState:
    message_id: UUID
    reservation_token: str
    lease_expires_at: DateTime
    owns_reservation: bool = True


class WorkerCleanupExecutor:
    def __init__(
        self,
        handlers: WorkerCleanupHandlerRegistry | Iterable[WorkerCleanupHandler],
        send_operation: CleanupOperationSender | None = None,
        max_concurrency: int | None = None,
        *,
        lease_renewal_buffer_seconds: float = 5.0,
        operation_result_timeout_seconds: float = 30.0,
        operation_retry_delay_seconds: float = 1.0,
        max_operation_attempts: int = 3,
        logger: logging.Logger | None = None,
    ):
        if isinstance(handlers, WorkerCleanupHandlerRegistry):
            self._handlers = handlers
        else:
            self._handlers = WorkerCleanupHandlerRegistry(handlers)

        default_concurrency = 1 if self._handlers else 0
        self.max_concurrency = default_concurrency
        if max_concurrency is not None:
            if max_concurrency < 0:
                raise ValueError("Cleanup concurrency cannot be negative")
            self.max_concurrency = max_concurrency
        if max_operation_attempts < 1:
            raise ValueError("Cleanup operation attempts must be positive")

        self._send_operation = send_operation or self._missing_operation_sender
        self._limiter = (
            anyio.CapacityLimiter(self.max_concurrency)
            if self.max_concurrency > 0
            else None
        )
        self._lease_renewal_buffer_seconds = lease_renewal_buffer_seconds
        self._operation_result_timeout_seconds = operation_result_timeout_seconds
        self._operation_retry_delay_seconds = operation_retry_delay_seconds
        self._max_operation_attempts = max_operation_attempts
        self._pending_operations: dict[UUID, _PendingOperation] = {}
        self._task_group: anyio.abc.TaskGroup | None = None
        self._logger = logger or get_logger(__name__)

    @property
    def handled_cleanup_kinds(self) -> tuple[CleanupKind, ...]:
        return self._handlers.handled_cleanup_kinds

    @property
    def in_flight_count(self) -> int:
        if self._limiter is None:
            return 0
        return int(self._limiter.borrowed_tokens)

    def set_operation_sender(self, send_operation: CleanupOperationSender) -> None:
        self._send_operation = send_operation

    def set_max_concurrency(self, max_concurrency: int) -> None:
        if max_concurrency < 0:
            raise ValueError("Cleanup concurrency cannot be negative")
        self.max_concurrency = max_concurrency
        if max_concurrency == 0:
            self._limiter = None
            return

        if self._limiter is None:
            self._limiter = anyio.CapacityLimiter(max_concurrency)
        else:
            self._limiter.total_tokens = max_concurrency

    def cancel(self) -> None:
        if self._task_group is not None:
            self._task_group.cancel_scope.cancel()

    @staticmethod
    def _missing_operation_sender(
        frame: CleanupOperationFrame,
    ) -> CleanupOperationResultFrame | None:
        raise RuntimeError(
            f"Cleanup operation sender has not been configured for {frame.type!r}"
        )

    async def __aenter__(self) -> WorkerCleanupExecutor:
        if self._task_group is not None:
            raise RuntimeError("WorkerCleanupExecutor is already running")
        self._task_group = anyio.create_task_group()
        await self._task_group.__aenter__()
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        if self._task_group is None:
            return
        task_group = self._task_group
        self._task_group = None
        await task_group.__aexit__(*exc_info)

    def submit(self, frame: CleanupMessageFrame) -> None:
        if self._task_group is None:
            raise RuntimeError(
                "WorkerCleanupExecutor must be used as an async context manager "
                "before cleanup messages can be submitted"
            )
        self._task_group.start_soon(self.execute, frame)

    async def execute(self, frame: CleanupMessageFrame) -> None:
        payload = frame.payload
        handler = self._handlers.get(payload.kind)
        if handler is None:
            await self._release(payload, reason="unsupported_cleanup_kind")
            return

        if self._limiter is None:
            await self._release(payload, reason="cleanup_delivery_unavailable")
            return

        try:
            self._limiter.acquire_on_behalf_of_nowait(payload.reservation_token)
        except anyio.WouldBlock:
            await self._release(payload, reason="concurrency_limit_reached")
            return
        except RuntimeError:
            await self._release(payload, reason="duplicate_reservation")
            return

        state = _ReservationState(
            message_id=payload.message_id,
            reservation_token=payload.reservation_token,
            lease_expires_at=payload.lease_expires_at,
        )
        try:
            with anyio.CancelScope() as cleanup_scope:
                async with anyio.create_task_group() as renewal_group:
                    renewal_group.start_soon(
                        self._renew_until_finished,
                        state,
                        cleanup_scope,
                    )
                    try:
                        result = await self._run_handler(handler, payload)
                    except Exception:
                        self._logger.exception(
                            "Cleanup handler failed for message %s",
                            payload.message_id,
                        )
                        result = CleanupExecutionResult.release("handler_failed")

                    if state.owns_reservation:
                        if result is None:
                            result = CleanupExecutionResult.success()

                        if result.operation == "ack":
                            await self._ack(payload)
                        else:
                            await self._release(
                                payload,
                                reason=result.reason or "handler_released",
                            )

                    renewal_group.cancel_scope.cancel()

            if not state.owns_reservation:
                self._logger.debug(
                    "Skipping cleanup result for message %s because the reservation "
                    "is no longer current",
                    payload.message_id,
                )
                return
        finally:
            self._limiter.release_on_behalf_of(payload.reservation_token)

    async def _run_handler(
        self,
        handler: WorkerCleanupHandler,
        payload: CleanupMessagePayload,
    ) -> CleanupExecutionResult | None:
        result = handler.cleanup(payload)
        if inspect.isawaitable(result):
            result = await result
        if result is not None and not isinstance(result, CleanupExecutionResult):
            raise TypeError(
                "Cleanup handlers must return CleanupExecutionResult or None"
            )
        return result

    async def _ack(
        self, payload: CleanupMessagePayload
    ) -> CleanupOperationResultFrame | None:
        return await self._send_operation_until_resolved(
            operation="ack",
            payload=payload,
        )

    async def _release(
        self, payload: CleanupMessagePayload, reason: str
    ) -> CleanupOperationResultFrame | None:
        return await self._send_operation_until_resolved(
            operation="release",
            payload=payload,
            reason=reason,
        )

    async def _renew_until_finished(
        self,
        state: _ReservationState,
        cleanup_scope: anyio.CancelScope,
    ) -> None:
        while state.owns_reservation:
            sleep_seconds = self._seconds_until_renewal(state.lease_expires_at)
            if sleep_seconds > 0:
                await anyio.sleep(sleep_seconds)

            if not state.owns_reservation:
                return

            if self._lease_expired(state):
                self._lose_reservation(state, cleanup_scope)
                return

            result = await self._send_operation_until_resolved(
                operation="renew",
                message_id=state.message_id,
                reservation_token=state.reservation_token,
            )
            if result is None:
                if self._lease_expired(state):
                    self._lose_reservation(state, cleanup_scope)
                    return
                await anyio.sleep(self._operation_retry_delay_seconds)
                continue
            action = self.classify_operation_result(result)
            if action is CleanupOperationResultAction.ACCEPTED:
                if result.payload.lease_expires_at is not None:
                    state.lease_expires_at = result.payload.lease_expires_at
                continue

            if action is CleanupOperationResultAction.RETRYABLE_ERROR:
                if self._lease_expired(state):
                    self._lose_reservation(state, cleanup_scope)
                    return
                await anyio.sleep(self._operation_retry_delay_seconds)
                continue

            self._lose_reservation(state, cleanup_scope)
            return

    def _lease_expired(self, state: _ReservationState) -> bool:
        return now("UTC") >= state.lease_expires_at

    @staticmethod
    def _lose_reservation(
        state: _ReservationState,
        cleanup_scope: anyio.CancelScope,
    ) -> None:
        state.owns_reservation = False
        cleanup_scope.cancel()

    def _seconds_until_renewal(self, lease_expires_at: DateTime) -> float:
        return max(
            0.0,
            (lease_expires_at - now("UTC")).total_seconds()
            - self._lease_renewal_buffer_seconds,
        )

    async def _send_operation_until_resolved(
        self,
        operation: CleanupOperation,
        payload: CleanupMessagePayload | None = None,
        *,
        message_id: UUID | None = None,
        reservation_token: str | None = None,
        reason: str | None = None,
    ) -> CleanupOperationResultFrame | None:
        if payload is not None:
            message_id = payload.message_id
            reservation_token = payload.reservation_token
        if message_id is None or reservation_token is None:
            raise ValueError("Cleanup operations require a message id and token")

        last_result: CleanupOperationResultFrame | None = None
        last_exception: Exception | None = None
        for attempt in range(1, self._max_operation_attempts + 1):
            frame = self._build_operation_frame(
                operation=operation,
                message_id=message_id,
                reservation_token=reservation_token,
                reason=reason,
            )
            try:
                result = await self._send_operation_once(frame)
            except Exception as exc:
                self._logger.debug(
                    "Cleanup %s operation failed for message %s",
                    operation,
                    message_id,
                    exc_info=True,
                )
                last_exception = exc
                if attempt == self._max_operation_attempts:
                    break
                await anyio.sleep(self._operation_retry_delay_seconds)
                continue

            last_result = result
            action = self.classify_operation_result(result)
            if action is CleanupOperationResultAction.RETRYABLE_ERROR:
                if attempt == self._max_operation_attempts:
                    return result
                await anyio.sleep(self._operation_retry_delay_seconds)
                continue
            return result

        if last_result is None and last_exception is not None:
            self._logger.debug(
                "Cleanup %s operation exhausted after %s attempt(s) for message %s: %r",
                operation,
                self._max_operation_attempts,
                message_id,
                last_exception,
            )
        return last_result

    async def _send_operation_once(
        self, frame: CleanupOperationFrame
    ) -> CleanupOperationResultFrame:
        loop = asyncio.get_running_loop()
        future: asyncio.Future[CleanupOperationResultFrame] = loop.create_future()
        self._pending_operations[frame.id] = _PendingOperation(
            frame=frame,
            future=future,
        )
        try:
            result = self._send_operation(frame)
            if inspect.isawaitable(result):
                result = await result
            if result is not None:
                if isinstance(result, dict):
                    result = CleanupOperationResultFrame.model_validate(result)
                if not isinstance(result, CleanupOperationResultFrame):
                    raise TypeError(
                        "Cleanup operation senders must return "
                        "CleanupOperationResultFrame, a frame dict, or None"
                    )
                return result
            return await asyncio.wait_for(
                future,
                timeout=self._operation_result_timeout_seconds,
            )
        finally:
            self._pending_operations.pop(frame.id, None)

    def handle_operation_result(
        self, frame: CleanupOperationResultFrame
    ) -> CleanupOperationResultAction:
        pending = self._pending_operations.get(frame.payload.request_frame_id)
        if pending is None:
            return CleanupOperationResultAction.IGNORED
        if not pending.future.done():
            pending.future.set_result(frame)
        return self.classify_operation_result(frame)

    @staticmethod
    def classify_operation_result(
        frame: CleanupOperationResultFrame,
    ) -> CleanupOperationResultAction:
        status = frame.payload.status
        if status == "accepted":
            return CleanupOperationResultAction.ACCEPTED
        if status == "error":
            return CleanupOperationResultAction.RETRYABLE_ERROR
        if status == "not_found" and frame.payload.operation == "ack":
            return CleanupOperationResultAction.ACK_NOT_FOUND
        if status == "not_found" or status in _LOST_RESERVATION_STATUSES:
            return CleanupOperationResultAction.LOST_RESERVATION
        return CleanupOperationResultAction.RETRYABLE_ERROR

    def _build_operation_frame(
        self,
        operation: CleanupOperation,
        message_id: UUID,
        reservation_token: str,
        reason: str | None = None,
    ) -> CleanupOperationFrame:
        frame_base = {
            "id": uuid7(),
            "sent_at": now("UTC"),
        }
        operation_payload = CleanupOperationPayload(
            message_id=message_id,
            reservation_token=reservation_token,
        )
        if operation == "ack":
            return CleanupAckFrame(
                type="cleanup.ack.v1",
                payload=operation_payload,
                **frame_base,
            )
        if operation == "renew":
            return CleanupRenewFrame(
                type="cleanup.renew.v1",
                payload=operation_payload,
                **frame_base,
            )

        if not reason:
            raise ValueError("Cleanup release operations require a reason")
        return CleanupReleaseFrame(
            type="cleanup.release.v1",
            payload=CleanupReleasePayload(
                message_id=message_id,
                reservation_token=reservation_token,
                reason=reason,
            ),
            **frame_base,
        )


__all__ = [
    "CleanupExecutionResult",
    "CleanupOperationFrame",
    "CleanupOperationResultAction",
    "CleanupOperationSender",
    "WorkerCleanupExecutor",
    "WorkerCleanupHandler",
    "WorkerCleanupHandlerRegistry",
]
