from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import pytest

from prefect._internal.uuid7 import uuid7
from prefect.client.schemas.objects import FlowRun
from prefect.client.schemas.worker_channel import (
    CANCELLING_TIMEOUT_TEARDOWN,
    PENDING_CLAIM_TEARDOWN,
    CancellingTimeoutCleanupMessagePayload,
    CleanupMessageFrame,
)
from prefect.exceptions import (
    InfrastructureNotAvailable,
    InfrastructureNotFound,
    ObjectNotFound,
)
from prefect.states import Cancelling, Pending, Running
from prefect.types._datetime import now
from prefect.workers._cleanup import (
    CleanupExecutionResult,
    WorkerCleanupExecutor,
)
from prefect.workers._cleanup_handlers import CancellingTimeoutTeardownHandler
from prefect.workers.base import (
    BaseJobConfiguration,
    BaseWorker,
    BaseWorkerResult,
)


class TeardownTrackingWorker(BaseWorker[BaseJobConfiguration, Any, BaseWorkerResult]):
    """
    Test worker that overrides `kill_infrastructure` so the handler has a
    capable target to dispatch to.
    """

    type = "cleanup-handler-test-capable"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.kill_calls: list[dict[str, Any]] = []
        self.kill_side_effect: BaseException | None = None
        self._cleanup_handler_registry.register(CancellingTimeoutTeardownHandler(self))

    async def run(  # type: ignore[override]
        self,
        flow_run: Any = None,
        configuration: Any = None,
        task_status: Any = None,
    ) -> BaseWorkerResult:
        raise NotImplementedError

    async def kill_infrastructure(  # type: ignore[override]
        self,
        infrastructure_pid: str,
        configuration: BaseJobConfiguration,
        grace_seconds: int = 30,
    ) -> None:
        self.kill_calls.append(
            {
                "infrastructure_pid": infrastructure_pid,
                "configuration": configuration,
                "grace_seconds": grace_seconds,
            }
        )
        if self.kill_side_effect is not None:
            raise self.kill_side_effect


class IncapableWorker(BaseWorker[BaseJobConfiguration, Any, BaseWorkerResult]):
    """Test worker without `kill_infrastructure` to verify the base default."""

    type = "cleanup-handler-test-incapable"

    async def run(  # type: ignore[override]
        self,
        flow_run: Any = None,
        configuration: Any = None,
        task_status: Any = None,
    ) -> BaseWorkerResult:
        raise NotImplementedError


def _cancelling_payload(
    *,
    flow_run_id: UUID | None = None,
    infrastructure_pid: str | None = "infra-pid",
) -> CancellingTimeoutCleanupMessagePayload:
    target: dict[str, str | None] = {
        "flow_run_id": str(flow_run_id or uuid4()),
    }
    if infrastructure_pid is not None:
        target["infrastructure_pid"] = infrastructure_pid

    return CancellingTimeoutCleanupMessagePayload.model_validate(
        {
            "kind": CANCELLING_TIMEOUT_TEARDOWN,
            "message_id": str(uuid4()),
            "reservation_token": "token",
            "lease_expires_at": (now("UTC") + timedelta(minutes=5)).isoformat(),
            "delivery_count": 1,
            "work_queue_id": None,
            "target": target,
            "data": {},
        }
    )


def _build_handler(
    *,
    flow_run: FlowRun | None,
    configuration: BaseJobConfiguration | None = None,
    configuration_error: BaseException | None = None,
    kill_side_effect: BaseException | None = None,
    grace_seconds: int = 30,
) -> tuple[CancellingTimeoutTeardownHandler, Mock]:
    worker = Mock(spec=BaseWorker)
    client = Mock()
    if flow_run is None:
        client.read_flow_run = AsyncMock(
            side_effect=ObjectNotFound(Exception("missing"))
        )
    else:
        client.read_flow_run = AsyncMock(return_value=flow_run)
    worker.client = client

    if configuration_error is not None:
        worker._get_configuration = AsyncMock(side_effect=configuration_error)
    else:
        worker._get_configuration = AsyncMock(
            return_value=configuration or BaseJobConfiguration()
        )

    worker.kill_infrastructure = AsyncMock(side_effect=kill_side_effect)

    handler = CancellingTimeoutTeardownHandler(worker, grace_seconds=grace_seconds)
    return handler, worker


def _flow_run(
    *,
    state=None,
    start_time=None,
    infrastructure_pid: str | None = None,
) -> FlowRun:
    return FlowRun(
        id=uuid4(),
        flow_id=uuid4(),
        name="test-flow-run",
        state=state or Cancelling(),
        start_time=start_time,
        infrastructure_pid=infrastructure_pid,
    )


class TestHandlerRegistration:
    async def test_handler_declares_cancelling_timeout_kind(self):
        worker = Mock(spec=BaseWorker)
        handler = CancellingTimeoutTeardownHandler(worker)

        assert handler.cleanup_kind == CANCELLING_TIMEOUT_TEARDOWN

    async def test_capable_worker_advertises_cancelling_timeout_kind(self):
        worker = TeardownTrackingWorker(work_pool_name="test")

        assert worker.handled_cleanup_kinds == (CANCELLING_TIMEOUT_TEARDOWN,)
        assert worker.max_cleanup_concurrency == 1

    async def test_incapable_worker_does_not_advertise_cancelling_timeout_kind(self):
        worker = IncapableWorker(work_pool_name="test")

        assert worker.handled_cleanup_kinds == ()
        assert worker.max_cleanup_concurrency == 0

    async def test_base_worker_does_not_register_handler_by_default(self):
        """The base worker should not auto-register the cancelling timeout handler."""

        class NoCleanupWorker(BaseWorker[BaseJobConfiguration, Any, BaseWorkerResult]):
            type = "cleanup-handler-test-no-cleanup"

            async def run(  # type: ignore[override]
                self, flow_run=None, configuration=None, task_status=None
            ):
                raise NotImplementedError

        worker = NoCleanupWorker(work_pool_name="test")

        assert worker.handled_cleanup_kinds == ()
        assert worker.cleanup_handler_registry.get(CANCELLING_TIMEOUT_TEARDOWN) is None


class TestHandlerBehavior:
    async def test_releases_unexpected_payload_kind(self):
        handler, worker = _build_handler(flow_run=_flow_run())

        wrong_payload = Mock(spec=[])  # No isinstance check matches
        wrong_payload.kind = PENDING_CLAIM_TEARDOWN

        result = await handler.cleanup(wrong_payload)

        assert result == CleanupExecutionResult.release("unexpected_payload_kind")
        worker.client.read_flow_run.assert_not_called()

    async def test_releases_invalid_payload_when_flow_run_id_missing(self):
        """Defensive check: even though Pydantic validates flow_run_id, the
        handler releases with `invalid_payload` if it cannot find one on the
        target."""
        handler, worker = _build_handler(flow_run=_flow_run())

        payload = _cancelling_payload()
        payload.target.flow_run_id = None  # type: ignore[assignment]

        result = await handler.cleanup(payload)

        assert result == CleanupExecutionResult.release("invalid_payload")
        worker.client.read_flow_run.assert_not_called()

    async def test_deleted_flow_run_is_idempotent_success(self):
        handler, worker = _build_handler(flow_run=None)

        result = await handler.cleanup(_cancelling_payload())

        assert result == CleanupExecutionResult.success()
        worker.kill_infrastructure.assert_not_called()

    async def test_missing_pid_with_no_stored_pid_acks_as_noop(self):
        flow_run = _flow_run(infrastructure_pid=None)
        handler, worker = _build_handler(flow_run=flow_run)

        result = await handler.cleanup(
            _cancelling_payload(
                flow_run_id=flow_run.id,
                infrastructure_pid=None,
            )
        )

        assert result == CleanupExecutionResult.success()
        worker.kill_infrastructure.assert_not_called()

    async def test_missing_pid_with_stored_pid_releases_missing_handle(self):
        flow_run = _flow_run(infrastructure_pid="stored-pid")
        handler, worker = _build_handler(flow_run=flow_run)

        result = await handler.cleanup(
            _cancelling_payload(
                flow_run_id=flow_run.id,
                infrastructure_pid=None,
            )
        )

        assert result == CleanupExecutionResult.release("missing_infrastructure_handle")
        worker.kill_infrastructure.assert_not_called()

    async def test_empty_string_pid_treated_as_missing(self):
        flow_run = _flow_run(infrastructure_pid=None)
        handler, worker = _build_handler(flow_run=flow_run)

        result = await handler.cleanup(
            _cancelling_payload(
                flow_run_id=flow_run.id,
                infrastructure_pid="",
            )
        )

        assert result == CleanupExecutionResult.success()
        worker.kill_infrastructure.assert_not_called()

    async def test_configuration_unavailable_releases_with_stable_reason(self):
        flow_run = _flow_run(infrastructure_pid="stored-pid")
        handler, worker = _build_handler(
            flow_run=flow_run,
            configuration_error=ObjectNotFound(Exception("deployment gone")),
        )

        result = await handler.cleanup(
            _cancelling_payload(flow_run_id=flow_run.id, infrastructure_pid="pid")
        )

        assert result == CleanupExecutionResult.release(
            "configuration_context_unavailable"
        )
        worker.kill_infrastructure.assert_not_called()

    async def test_infrastructure_not_found_acks_as_idempotent_success(self):
        flow_run = _flow_run(infrastructure_pid="pid")
        handler, worker = _build_handler(
            flow_run=flow_run,
            kill_side_effect=InfrastructureNotFound("gone"),
        )

        result = await handler.cleanup(
            _cancelling_payload(flow_run_id=flow_run.id, infrastructure_pid="pid")
        )

        assert result == CleanupExecutionResult.success()
        worker.kill_infrastructure.assert_awaited_once()

    async def test_not_implemented_releases_unsupported_worker_type(self):
        flow_run = _flow_run(infrastructure_pid="pid")
        handler, worker = _build_handler(
            flow_run=flow_run,
            kill_side_effect=NotImplementedError("nope"),
        )

        result = await handler.cleanup(
            _cancelling_payload(flow_run_id=flow_run.id, infrastructure_pid="pid")
        )

        assert result == CleanupExecutionResult.release("unsupported_worker_type")

    async def test_infrastructure_unavailable_releases_with_stable_reason(self):
        flow_run = _flow_run(infrastructure_pid="pid")
        handler, worker = _build_handler(
            flow_run=flow_run,
            kill_side_effect=InfrastructureNotAvailable("offline"),
        )

        result = await handler.cleanup(
            _cancelling_payload(flow_run_id=flow_run.id, infrastructure_pid="pid")
        )

        assert result == CleanupExecutionResult.release("infrastructure_not_available")

    async def test_successful_kill_acks(self):
        flow_run = _flow_run(infrastructure_pid="pid")
        handler, worker = _build_handler(flow_run=flow_run)

        result = await handler.cleanup(
            _cancelling_payload(flow_run_id=flow_run.id, infrastructure_pid="pid")
        )

        assert result == CleanupExecutionResult.success()
        worker.kill_infrastructure.assert_awaited_once()
        call_kwargs = worker.kill_infrastructure.await_args.kwargs
        assert call_kwargs["infrastructure_pid"] == "pid"
        assert call_kwargs["grace_seconds"] == 30

    async def test_grace_seconds_is_configurable(self):
        flow_run = _flow_run(infrastructure_pid="pid")
        handler, worker = _build_handler(flow_run=flow_run, grace_seconds=10)

        await handler.cleanup(
            _cancelling_payload(flow_run_id=flow_run.id, infrastructure_pid="pid")
        )

        assert worker.kill_infrastructure.await_args.kwargs["grace_seconds"] == 10

    async def test_does_not_skip_when_start_time_is_set(self):
        """The cleanup message is emitted after the timeout boundary; the
        handler must NOT skip teardown when a `start_time` is present."""
        flow_run = _flow_run(
            state=Running(),
            start_time=now("UTC"),
            infrastructure_pid="pid",
        )
        handler, worker = _build_handler(flow_run=flow_run)

        result = await handler.cleanup(
            _cancelling_payload(flow_run_id=flow_run.id, infrastructure_pid="pid")
        )

        assert result == CleanupExecutionResult.success()
        worker.kill_infrastructure.assert_awaited_once()

    async def test_does_not_skip_when_state_is_not_cancelling(self):
        """The handler must NOT require the flow run to currently be in the
        CANCELLING state — the server has already moved beyond it."""
        flow_run = _flow_run(state=Pending(), infrastructure_pid="pid")
        handler, worker = _build_handler(flow_run=flow_run)

        result = await handler.cleanup(
            _cancelling_payload(flow_run_id=flow_run.id, infrastructure_pid="pid")
        )

        assert result == CleanupExecutionResult.success()
        worker.kill_infrastructure.assert_awaited_once()

    async def test_does_not_mutate_flow_run_state(self):
        """Verify the handler never proposes or forces a state transition."""
        flow_run = _flow_run(state=Running(), infrastructure_pid="pid")
        handler, worker = _build_handler(flow_run=flow_run)

        await handler.cleanup(
            _cancelling_payload(flow_run_id=flow_run.id, infrastructure_pid="pid")
        )

        worker.client.set_flow_run_state.assert_not_called()
        # Any helper that would propose a transition should not have been used.
        assert not hasattr(worker, "_propose_state_calls")

    async def test_uses_payload_pid_not_flow_run_pid(self):
        """Per the protocol contract, target identifiers come from the payload,
        not from current flow-run state."""
        flow_run = _flow_run(infrastructure_pid="flow-run-pid")
        handler, worker = _build_handler(flow_run=flow_run)

        await handler.cleanup(
            _cancelling_payload(
                flow_run_id=flow_run.id,
                infrastructure_pid="payload-pid",
            )
        )

        worker.kill_infrastructure.assert_awaited_once()
        assert (
            worker.kill_infrastructure.await_args.kwargs["infrastructure_pid"]
            == "payload-pid"
        )


class TestExecutorIntegration:
    """Verify the handler integrates correctly with WorkerCleanupExecutor."""

    async def _build_executor_with_handler(
        self,
        *,
        flow_run: FlowRun | None,
        infrastructure_pid: str | None = "pid",
        kill_side_effect: BaseException | None = None,
    ) -> tuple[WorkerCleanupExecutor, Mock, list[Any]]:
        sent: list[Any] = []

        async def send(frame):
            sent.append(frame)
            from prefect.client.schemas.worker_channel import (
                CleanupOperationResultFrame,
            )

            return CleanupOperationResultFrame.model_validate(
                {
                    "type": "cleanup.operation_result.v1",
                    "id": str(uuid7()),
                    "sent_at": now("UTC").isoformat(),
                    "payload": {
                        "request_frame_id": str(frame.id),
                        "message_id": str(frame.payload.message_id),
                        "operation": frame.payload.message_id
                        and (
                            "ack"
                            if frame.type == "cleanup.ack.v1"
                            else "release"
                            if frame.type == "cleanup.release.v1"
                            else "renew"
                        ),
                        "status": "accepted",
                        "reason": None,
                        "detail": None,
                    },
                }
            )

        handler, worker = _build_handler(
            flow_run=flow_run,
            kill_side_effect=kill_side_effect,
        )
        executor = WorkerCleanupExecutor([handler], send_operation=send)

        message = CleanupMessageFrame.model_validate(
            {
                "type": "cleanup.message.v1",
                "id": str(uuid7()),
                "sent_at": now("UTC").isoformat(),
                "payload": _cancelling_payload(
                    flow_run_id=flow_run.id if flow_run else uuid4(),
                    infrastructure_pid=infrastructure_pid,
                ).model_dump(mode="json"),
            }
        )

        await executor.execute(message)
        return executor, worker, sent

    async def test_successful_teardown_results_in_ack_frame(self):
        flow_run = _flow_run(infrastructure_pid="pid")
        _, worker, sent = await self._build_executor_with_handler(flow_run=flow_run)

        worker.kill_infrastructure.assert_awaited_once()
        assert len(sent) == 1
        assert sent[0].type == "cleanup.ack.v1"

    async def test_missing_handle_results_in_release_frame(self):
        flow_run = _flow_run(infrastructure_pid="stored-pid")
        _, worker, sent = await self._build_executor_with_handler(
            flow_run=flow_run,
            infrastructure_pid=None,
        )

        worker.kill_infrastructure.assert_not_called()
        assert len(sent) == 1
        assert sent[0].type == "cleanup.release.v1"
        assert sent[0].payload.reason == "missing_infrastructure_handle"

    async def test_unsupported_worker_results_in_release_frame(self):
        flow_run = _flow_run(infrastructure_pid="pid")
        _, _worker, sent = await self._build_executor_with_handler(
            flow_run=flow_run,
            kill_side_effect=NotImplementedError("nope"),
        )

        assert len(sent) == 1
        assert sent[0].type == "cleanup.release.v1"
        assert sent[0].payload.reason == "unsupported_worker_type"

    async def test_infrastructure_not_found_results_in_ack_frame(self):
        flow_run = _flow_run(infrastructure_pid="pid")
        _, _worker, sent = await self._build_executor_with_handler(
            flow_run=flow_run,
            kill_side_effect=InfrastructureNotFound("gone"),
        )

        assert len(sent) == 1
        assert sent[0].type == "cleanup.ack.v1"

    async def test_unsupported_cleanup_kind_releases_via_executor(self):
        """When a worker only registers cancelling_timeout_teardown but receives
        a pending_claim_teardown message, the executor handles the release
        without invoking the handler."""
        sent: list[Any] = []

        async def send(frame):
            sent.append(frame)
            from prefect.client.schemas.worker_channel import (
                CleanupOperationResultFrame,
            )

            return CleanupOperationResultFrame.model_validate(
                {
                    "type": "cleanup.operation_result.v1",
                    "id": str(uuid7()),
                    "sent_at": now("UTC").isoformat(),
                    "payload": {
                        "request_frame_id": str(frame.id),
                        "message_id": str(frame.payload.message_id),
                        "operation": "release",
                        "status": "accepted",
                        "reason": None,
                        "detail": None,
                    },
                }
            )

        handler, _worker = _build_handler(flow_run=_flow_run(infrastructure_pid="pid"))
        executor = WorkerCleanupExecutor([handler], send_operation=send)

        pending_payload = {
            "kind": PENDING_CLAIM_TEARDOWN,
            "message_id": str(uuid4()),
            "reservation_token": "token",
            "lease_expires_at": (now("UTC") + timedelta(minutes=5)).isoformat(),
            "delivery_count": 1,
            "work_queue_id": None,
            "target": {
                "flow_run_id": str(uuid4()),
                "claim_id": str(uuid7()),
            },
            "data": {},
        }
        message = CleanupMessageFrame.model_validate(
            {
                "type": "cleanup.message.v1",
                "id": str(uuid7()),
                "sent_at": now("UTC").isoformat(),
                "payload": pending_payload,
            }
        )

        await executor.execute(message)

        assert len(sent) == 1
        assert sent[0].type == "cleanup.release.v1"
        assert sent[0].payload.reason == "unsupported_cleanup_kind"


class TestRealWorkerIntegration:
    """End-to-end smoke tests using a real BaseWorker subclass and fixtures."""

    async def test_handler_against_real_capable_worker(self, work_pool):
        worker = TeardownTrackingWorker(
            work_pool_name=work_pool.name,
            name="cleanup-handler-test",
        )
        flow_run = _flow_run(infrastructure_pid="pid")

        handler = worker.cleanup_handler_registry.get(CANCELLING_TIMEOUT_TEARDOWN)
        assert isinstance(handler, CancellingTimeoutTeardownHandler)

        worker._get_configuration = AsyncMock(  # type: ignore[method-assign]
            return_value=BaseJobConfiguration()
        )
        worker._client = Mock()
        worker._client.read_flow_run = AsyncMock(return_value=flow_run)

        result = await handler.cleanup(
            _cancelling_payload(flow_run_id=flow_run.id, infrastructure_pid="pid")
        )

        assert result == CleanupExecutionResult.success()
        assert worker.kill_calls == [
            {
                "infrastructure_pid": "pid",
                "configuration": worker._get_configuration.return_value,
                "grace_seconds": 30,
            }
        ]

    async def test_handler_treats_not_implemented_from_base_as_unsupported(self):
        """Direct check against an incapable BaseWorker subclass — kill
        raises NotImplementedError, which the handler maps to a stable
        release reason."""
        worker = IncapableWorker(work_pool_name="test")
        flow_run = _flow_run(infrastructure_pid="pid")

        worker._client = Mock()
        worker._client.read_flow_run = AsyncMock(return_value=flow_run)
        worker._get_configuration = AsyncMock(  # type: ignore[method-assign]
            return_value=BaseJobConfiguration()
        )

        handler = CancellingTimeoutTeardownHandler(worker)
        result = await handler.cleanup(
            _cancelling_payload(flow_run_id=flow_run.id, infrastructure_pid="pid")
        )

        assert result == CleanupExecutionResult.release("unsupported_worker_type")


@pytest.mark.parametrize(
    "kill_side_effect,expected_reason",
    [
        (InfrastructureNotAvailable("offline"), "infrastructure_not_available"),
        (NotImplementedError("nope"), "unsupported_worker_type"),
    ],
)
async def test_typed_kill_exceptions_map_to_stable_release_reasons(
    kill_side_effect: BaseException,
    expected_reason: str,
):
    flow_run = _flow_run(infrastructure_pid="pid")
    handler, _worker = _build_handler(
        flow_run=flow_run, kill_side_effect=kill_side_effect
    )

    result = await handler.cleanup(
        _cancelling_payload(flow_run_id=flow_run.id, infrastructure_pid="pid")
    )

    assert result == CleanupExecutionResult.release(expected_reason)
