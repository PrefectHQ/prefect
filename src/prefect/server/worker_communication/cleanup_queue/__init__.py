from __future__ import annotations

from collections.abc import Iterable, Mapping
import importlib
from typing import Any, ClassVar, Literal
from uuid import UUID

from pydantic import ConfigDict, Field

from prefect._internal.schemas.bases import PrefectBaseModel
from prefect.client.schemas.worker_channel import CleanupKind, CleanupOperationStatus
from prefect.settings.context import get_current_settings
from prefect.types import DateTime, NonNegativeInteger, PositiveInteger

CleanupQueueOperation = Literal["ack", "release", "renew"]


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
    ) -> CleanupQueueMessage:
        """
        Store a cleanup message if it has not already been produced.

        Implementations should treat `message_id` and `idempotency_key` as stable
        producer identifiers within a work pool, returning the existing message
        for repeated enqueue attempts instead of creating duplicates. The
        optional `work_queue_id` is advisory targeting metadata.
        """
        ...

    async def reserve(
        self,
        *,
        work_pool_id: UUID,
        cleanup_kinds: Iterable[CleanupKind] | None = None,
        preferred_work_queue_ids: Iterable[UUID] | None = None,
        allow_fallback_to_any_queue: bool = True,
    ) -> CleanupQueueReservation | None:
        """
        Atomically reserve one eligible cleanup message for delivery.

        A successful reservation must increment the committed delivery count,
        create exactly one active reservation, and return an unguessable token
        required for follow-up operations. `preferred_work_queue_ids` should be
        treated as an advisory preference, with pool-wide fallback controlled by
        `allow_fallback_to_any_queue`.
        """
        ...

    async def ack(
        self,
        *,
        work_pool_id: UUID,
        message_id: UUID,
        reservation_token: str,
    ) -> CleanupQueueOperationResult:
        """
        Complete a reserved cleanup message.

        The operation must validate the work-pool scope and current reservation
        token atomically before removing the message from active delivery.
        Implementations should retain completed idempotency state according to
        their configured retention policy.
        """
        ...

    async def release(
        self,
        *,
        work_pool_id: UUID,
        message_id: UUID,
        reservation_token: str,
        reason: str,
    ) -> CleanupQueueOperationResult:
        """
        Give up the current reservation without completing the cleanup message.

        The operation must validate the work-pool scope and current reservation
        token atomically, then either make the message eligible for redelivery or
        move it to the dead-letter queue when retry policy is exhausted.
        """
        ...

    async def renew(
        self,
        *,
        work_pool_id: UUID,
        message_id: UUID,
        reservation_token: str,
    ) -> CleanupQueueOperationResult:
        """
        Extend the lease for the current reservation.

        The operation must validate the work-pool scope and current reservation
        token atomically. Renewing a reservation should not increment delivery
        count because no new delivery has been committed.
        """
        ...

    async def expire_leases(
        self,
        *,
        limit: int = 100,
        work_pool_id: UUID | None = None,
    ) -> CleanupQueueLeaseExpiryResult:
        """
        Expire overdue reservations in bounded batches.

        Expired messages should become eligible for redelivery or move to the
        dead-letter queue according to retry policy. Implementations may scope
        the sweep to a work pool when `work_pool_id` is provided.
        """
        ...

    async def read_message(
        self,
        *,
        work_pool_id: UUID,
        message_id: UUID,
    ) -> CleanupQueueMessage | None:
        """
        Read an active cleanup message by work-pool scope and message ID.

        This is an inspection helper for messages that have not been acked or
        dead-lettered. It must not return a message from a different work pool.
        """
        ...

    async def read_dead_letter(
        self,
        *,
        work_pool_id: UUID,
        message_id: UUID,
    ) -> CleanupQueueDeadLetter | None:
        """
        Read a dead-letter entry by work-pool scope and message ID.

        This is an inspection helper for terminal cleanup failures. It must not
        return a dead-letter entry from a different work pool.
        """
        ...

    async def wake_dispatchers(self, work_pool_id: UUID) -> CleanupQueueWakeup:
        """
        Notify dispatchers that cleanup work may be available for a work pool.

        Implementations should advance and return a monotonic wakeup sequence so
        local dispatchers can avoid missing notifications.
        """
        ...

    async def read_wakeup_sequence(self, work_pool_id: UUID) -> int:
        """
        Return the latest wakeup sequence observed for a work pool.

        Callers use this value as the `after` cursor when waiting for future
        wakeups.
        """
        ...

    async def wait_for_wakeup(
        self,
        work_pool_id: UUID,
        *,
        after: int = 0,
        timeout: float | None = None,
    ) -> CleanupQueueWakeup | None:
        """
        Wait for a work-pool wakeup sequence newer than `after`.

        Returns the next wakeup when one is observed, or `None` when `timeout`
        elapses before a newer wakeup is available.
        """
        ...


def get_worker_cleanup_queue() -> WorkerCleanupQueue:
    """
    Return a cleanup queue instance from the configured storage module.
    """
    worker_channel_settings = get_current_settings().server.worker_channel
    storage_module = worker_channel_settings.cleanup_queue_storage
    cleanup_queue_module = importlib.import_module(storage_module)
    cleanup_queue_class = getattr(cleanup_queue_module, "WorkerCleanupQueue", None)
    if (
        not isinstance(cleanup_queue_class, type)
        or cleanup_queue_class is WorkerCleanupQueue
        or not issubclass(cleanup_queue_class, WorkerCleanupQueue)
    ):
        raise ValueError(
            f"The module {storage_module} does not contain a concrete "
            "WorkerCleanupQueue implementation"
        )
    return cleanup_queue_class()


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
