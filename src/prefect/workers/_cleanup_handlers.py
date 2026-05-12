from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Any
from uuid import UUID

from prefect.client.schemas.worker_channel import (
    CANCELLING_TIMEOUT_TEARDOWN,
    CancellingTimeoutCleanupMessagePayload,
    CleanupMessagePayload,
)
from prefect.exceptions import (
    InfrastructureNotAvailable,
    InfrastructureNotFound,
    ObjectNotFound,
)
from prefect.workers._cleanup import (
    CleanupExecutionResult,
    WorkerCleanupHandlerRegistry,
)

if TYPE_CHECKING:
    from prefect.client.schemas.objects import FlowRun
    from prefect.workers.base import BaseWorker


class CancellingTimeoutTeardownHandler:
    """Idempotent infrastructure teardown for `cancelling_timeout_teardown.v1`.

    The cleanup message is enqueued after the server has already committed
    the CANCELLING-timeout state outcome. Boundary contract:

    - Does not propose or force flow-run state transitions.
    - Does not require the flow run to currently be in `CANCELLING` and
      does not skip teardown when the flow run has a `start_time`.
    - Treats `InfrastructureNotFound` and an absent infrastructure handle
      (when no actionable handle can be determined) as idempotent success.
    - Maps `InfrastructureNotAvailable`, `NotImplementedError`, and missing
      configuration context to stable release reasons rather than generic
      errors so the executor can release with intent.
    - Uses the cleanup payload's stable target identifiers; current worker
      configuration is consulted only for provider access, not as proof of
      submission-time configuration.
    """

    cleanup_kind = CANCELLING_TIMEOUT_TEARDOWN

    def __init__(
        self,
        worker: "BaseWorker[Any, Any, Any]",
        *,
        grace_seconds: int = 30,
    ) -> None:
        self._worker = worker
        self._grace_seconds = grace_seconds

    async def cleanup(
        self, message: CleanupMessagePayload
    ) -> CleanupExecutionResult | None:
        if not isinstance(message, CancellingTimeoutCleanupMessagePayload):
            return CleanupExecutionResult.release("unexpected_payload_kind")

        flow_run_id = getattr(message.target, "flow_run_id", None)
        if flow_run_id is None:
            return CleanupExecutionResult.release("invalid_payload")

        flow_run = await self._read_flow_run(flow_run_id)
        if flow_run is None:
            return CleanupExecutionResult.success()

        infrastructure_pid = message.target.infrastructure_pid
        if not infrastructure_pid:
            stored_pid = getattr(flow_run, "infrastructure_pid", None)
            if not stored_pid:
                return CleanupExecutionResult.success()
            return CleanupExecutionResult.release("missing_infrastructure_handle")

        try:
            configuration = await self._worker._get_configuration(flow_run)
        except ObjectNotFound:
            return CleanupExecutionResult.release("configuration_context_unavailable")

        try:
            await self._worker.kill_infrastructure(
                infrastructure_pid=infrastructure_pid,
                configuration=configuration,
                grace_seconds=self._grace_seconds,
            )
        except InfrastructureNotFound:
            return CleanupExecutionResult.success()
        except NotImplementedError:
            return CleanupExecutionResult.release("unsupported_worker_type")
        except InfrastructureNotAvailable:
            return CleanupExecutionResult.release("infrastructure_not_available")

        return CleanupExecutionResult.success()

    async def _read_flow_run(self, flow_run_id: UUID) -> "FlowRun | None":
        try:
            return await self._worker.client.read_flow_run(flow_run_id)
        except ObjectNotFound:
            return None


@lru_cache(maxsize=None)
def _class_implements_kill_infrastructure(cls: type) -> bool:
    return sum("kill_infrastructure" in vars(c) for c in cls.__mro__) > 1


def build_cleanup_handler_registry(
    worker: "BaseWorker[Any, Any, Any]",
) -> "WorkerCleanupHandlerRegistry":
    """Build the cleanup handler registry for a worker.

    Class-level `cleanup_handlers` for a given cleanup kind take precedence
    over the per-instance default registered here.
    """
    registry = WorkerCleanupHandlerRegistry(worker.__class__.cleanup_handlers)

    if (
        _class_implements_kill_infrastructure(type(worker))
        and registry.get(CANCELLING_TIMEOUT_TEARDOWN) is None
    ):
        registry.register(CancellingTimeoutTeardownHandler(worker))

    return registry


__all__ = [
    "CancellingTimeoutTeardownHandler",
    "build_cleanup_handler_registry",
]
