from __future__ import annotations

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
from prefect.workers._cleanup import CleanupExecutionResult

if TYPE_CHECKING:
    from prefect.client.schemas.objects import FlowRun
    from prefect.workers.base import BaseWorker


class CancellingTimeoutTeardownHandler:
    """
    Cleanup handler for `cancelling_timeout_teardown.v1`.

    Performs idempotent infrastructure teardown for a flow run after the
    server has already committed the state-machine outcome that requires
    cleanup. The handler uses stable target identifiers from the cleanup
    payload (`target.flow_run_id`, `target.infrastructure_pid`) and reuses
    the worker's existing `kill_infrastructure` semantics.

    The handler is opt-in: capable worker types (those that implement
    `kill_infrastructure`) should register it on their cleanup handler
    registry, typically in their constructor:

        class MyWorker(BaseWorker[...]):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._cleanup_handler_registry.register(
                    CancellingTimeoutTeardownHandler(self)
                )

    Boundary contract:
    - Does not propose or force flow-run state transitions; the server has
      already crossed the timeout boundary by the time cleanup is enqueued.
    - Does not require the current flow-run state to be `CANCELLING` and
      does not skip teardown when the flow run has a `start_time`.
    - Treats `InfrastructureNotFound` and an absent infrastructure handle
      (when no actionable handle can be determined) as idempotent success.
    - Treats `InfrastructureNotAvailable`, `NotImplementedError`, and
      missing configuration context as stable release reasons rather than
      generic errors so the cleanup executor can release with intent.
    - Does not depend on an immutable submission-time job configuration
      record; current worker configuration is used only for provider access.
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


__all__ = ["CancellingTimeoutTeardownHandler"]
