from __future__ import annotations

from collections.abc import Iterable, Mapping
import importlib
from typing import Any, ClassVar, Literal, Protocol, runtime_checkable
from uuid import UUID

from pydantic import ConfigDict, Field

from prefect._internal.schemas.bases import PrefectBaseModel
from prefect.client.schemas.worker_channel import CleanupKind, CleanupOperationStatus
from prefect.settings.context import get_current_settings
from prefect.types import DateTime, NonNegativeInteger, PositiveInteger

CleanupQueueOperation = Literal["ack", "release", "renew"]


@runtime_checkable
class WorkerCleanupQueueModule(Protocol):
    WorkerCleanupQueue: type[WorkerCleanupQueue]


class CleanupQueueMessage(PrefectBaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    message_id: UUID
    idempotency_key: str = Field(min_length=1)
    work_pool_id: UUID
    work_queue_id: UUID | None = None
    kind: CleanupKind
    target: dict[str, Any] = Field(default_factory=dict)
    data: dict[str, Any] = Field(default_factory=dict)
    created_at: DateTime
    updated_at: DateTime
    delivery_count: NonNegativeInteger = 0


class CleanupQueueReservation(CleanupQueueMessage):
    reservation_token: str = Field(min_length=1)
    lease_expires_at: DateTime
    delivery_count: PositiveInteger


class CleanupQueueDeadLetter(PrefectBaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    message: CleanupQueueMessage
    reason: str = Field(min_length=1)
    final_delivery_count: NonNegativeInteger
    moved_at: DateTime
    reservation_token: str | None = None
    lease_expires_at: DateTime | None = None
    release_reason: str | None = None


class CleanupQueueOperationResult(PrefectBaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    message_id: UUID
    operation: CleanupQueueOperation
    status: CleanupOperationStatus
    lease_expires_at: DateTime | None = None
    reason: str | None = None
    dead_letter: CleanupQueueDeadLetter | None = None


class CleanupQueueLeaseExpiryResult(PrefectBaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    redelivered: list[CleanupQueueMessage] = Field(default_factory=list)
    dead_lettered: list[CleanupQueueDeadLetter] = Field(default_factory=list)


class CleanupQueueWakeup(PrefectBaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    work_pool_id: UUID
    sequence: PositiveInteger


class WorkerCleanupQueue:
    """
    Interface for cleanup delivery queue storage.

    Implementations own cleanup message reservation correctness. WebSocket
    dispatchers may keep process-local routing state, but ack, release, renew,
    lease expiry, retry accounting, and DLQ transitions must go through this
    queue. Implementations own the server retry and lease policy and completed
    idempotency retention semantics.
    """

    async def enqueue(
        self,
        *,
        message_id: UUID,
        idempotency_key: str,
        work_pool_id: UUID,
        kind: CleanupKind,
        target: Mapping[str, Any],
        data: Mapping[str, Any] | None = None,
        work_queue_id: UUID | None = None,
    ) -> CleanupQueueMessage: ...

    async def reserve(
        self,
        *,
        work_pool_id: UUID,
        cleanup_kinds: Iterable[CleanupKind] | None = None,
        preferred_work_queue_ids: Iterable[UUID] | None = None,
        allow_fallback_to_any_queue: bool = True,
    ) -> CleanupQueueReservation | None: ...

    async def ack(
        self,
        *,
        work_pool_id: UUID,
        message_id: UUID,
        reservation_token: str,
    ) -> CleanupQueueOperationResult: ...

    async def release(
        self,
        *,
        work_pool_id: UUID,
        message_id: UUID,
        reservation_token: str,
        reason: str,
    ) -> CleanupQueueOperationResult: ...

    async def renew(
        self,
        *,
        work_pool_id: UUID,
        message_id: UUID,
        reservation_token: str,
    ) -> CleanupQueueOperationResult: ...

    async def expire_leases(
        self,
        *,
        limit: int = 100,
        work_pool_id: UUID | None = None,
    ) -> CleanupQueueLeaseExpiryResult: ...

    async def read_message(
        self,
        *,
        work_pool_id: UUID,
        message_id: UUID,
    ) -> CleanupQueueMessage | None: ...

    async def read_dead_letter(
        self,
        *,
        work_pool_id: UUID,
        message_id: UUID,
    ) -> CleanupQueueDeadLetter | None: ...

    async def wake_dispatchers(self, work_pool_id: UUID) -> CleanupQueueWakeup: ...

    async def read_wakeup_sequence(self, work_pool_id: UUID) -> int: ...

    async def wait_for_wakeup(
        self,
        work_pool_id: UUID,
        *,
        after: int = 0,
        timeout: float | None = None,
    ) -> CleanupQueueWakeup | None: ...


def get_worker_cleanup_queue() -> WorkerCleanupQueue:
    """
    Return a cleanup queue instance from the configured storage module.
    """
    worker_channel_settings = get_current_settings().server.worker_channel
    storage_module = worker_channel_settings.cleanup_queue_storage
    cleanup_queue_module = importlib.import_module(storage_module)
    if not isinstance(cleanup_queue_module, WorkerCleanupQueueModule):
        raise ValueError(
            f"The module {storage_module} does not contain a WorkerCleanupQueue class"
        )
    return cleanup_queue_module.WorkerCleanupQueue()


__all__ = [
    "CleanupQueueDeadLetter",
    "CleanupQueueLeaseExpiryResult",
    "CleanupQueueMessage",
    "CleanupQueueOperation",
    "CleanupQueueOperationResult",
    "CleanupQueueReservation",
    "CleanupQueueWakeup",
    "WorkerCleanupQueue",
    "get_worker_cleanup_queue",
]
