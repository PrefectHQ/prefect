from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest import mock
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.objects import FlowRun, WorkPool
from prefect.client.schemas.worker_channel import (
    CANCELLING_TIMEOUT_TEARDOWN,
    CancellingTimeoutCleanupMessagePayload,
)
from prefect.exceptions import (
    InfrastructureNotAvailable,
    InfrastructureNotFound,
    ObjectNotFound,
)
from prefect.flows import flow
from prefect.server.schemas.responses import DeploymentResponse
from prefect.states import Pending, Running
from prefect.workers._cleanup import CleanupExecutionResult
from prefect.workers._cleanup_handlers import CancellingTimeoutTeardownHandler
from prefect.workers.base import (
    BaseJobConfiguration,
    BaseWorker,
    BaseWorkerResult,
)


class TeardownTrackingWorker(BaseWorker[BaseJobConfiguration, Any, BaseWorkerResult]):
    """Worker that overrides `kill_infrastructure` so auto-registration triggers."""

    type = "cleanup-handler-test-capable"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.kill_calls: list[dict[str, Any]] = []
        self.kill_side_effect: BaseException | None = None

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
    type = "cleanup-handler-test-incapable"

    async def run(  # type: ignore[override]
        self,
        flow_run: Any = None,
        configuration: Any = None,
        task_status: Any = None,
    ) -> BaseWorkerResult:
        raise NotImplementedError


@flow
def _sample_flow():
    pass


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
            "lease_expires_at": (
                datetime.now(timezone.utc) + timedelta(minutes=5)
            ).isoformat(),
            "delivery_count": 1,
            "work_queue_id": None,
            "target": target,
            "data": {},
        }
    )


async def _create_flow_run(
    prefect_client: PrefectClient,
    work_pool: WorkPool,
    *,
    state=None,
    infrastructure_pid: str | None = None,
) -> FlowRun:
    flow_run = await prefect_client.create_flow_run(
        _sample_flow, work_pool_name=work_pool.name, state=state
    )
    if infrastructure_pid is not None:
        await prefect_client.update_flow_run(
            flow_run.id, infrastructure_pid=infrastructure_pid
        )
    return flow_run


def _handler_for(
    worker: TeardownTrackingWorker,
) -> CancellingTimeoutTeardownHandler:
    handler = worker.cleanup_handler_registry.get(CANCELLING_TIMEOUT_TEARDOWN)
    assert isinstance(handler, CancellingTimeoutTeardownHandler)
    return handler


class TestHandlerRegistration:
    async def test_handler_declares_cancelling_timeout_kind(self):
        handler = CancellingTimeoutTeardownHandler(
            TeardownTrackingWorker(work_pool_name="test")
        )

        assert handler.cleanup_kind == CANCELLING_TIMEOUT_TEARDOWN

    async def test_capable_worker_auto_registers_handler(
        self,
        prefect_client: PrefectClient,
        work_pool: WorkPool,
    ):
        flow_run = await _create_flow_run(
            prefect_client, work_pool, infrastructure_pid="pid"
        )

        async with TeardownTrackingWorker(work_pool_name=work_pool.name) as worker:
            assert worker.handled_cleanup_kinds == (CANCELLING_TIMEOUT_TEARDOWN,)
            assert worker.max_cleanup_concurrency == 1

            handler = worker.cleanup_handler_registry.get(CANCELLING_TIMEOUT_TEARDOWN)
            assert isinstance(handler, CancellingTimeoutTeardownHandler)

            result = await handler.cleanup(
                _cancelling_payload(flow_run_id=flow_run.id, infrastructure_pid="pid")
            )

        assert result == CleanupExecutionResult.success()
        assert len(worker.kill_calls) == 1
        assert worker.kill_calls[0]["infrastructure_pid"] == "pid"

    async def test_incapable_worker_does_not_advertise_cancelling_timeout_kind(self):
        worker = IncapableWorker(work_pool_name="test")

        assert worker.handled_cleanup_kinds == ()
        assert worker.max_cleanup_concurrency == 0
        assert worker.cleanup_handler_registry.get(CANCELLING_TIMEOUT_TEARDOWN) is None

    async def test_base_worker_does_not_register_handler_by_default(self):
        class NoCleanupWorker(BaseWorker[BaseJobConfiguration, Any, BaseWorkerResult]):
            type = "cleanup-handler-test-no-cleanup"

            async def run(  # type: ignore[override]
                self, flow_run=None, configuration=None, task_status=None
            ):
                raise NotImplementedError

        worker = NoCleanupWorker(work_pool_name="test")

        assert worker.handled_cleanup_kinds == ()
        assert worker.cleanup_handler_registry.get(CANCELLING_TIMEOUT_TEARDOWN) is None

    async def test_class_level_cleanup_handlers_take_precedence(self):
        class CustomHandler:
            cleanup_kind = CANCELLING_TIMEOUT_TEARDOWN

            async def cleanup(self, message):
                return CleanupExecutionResult.success()

        custom = CustomHandler()

        class CapableCustomWorker(TeardownTrackingWorker):
            type = "cleanup-handler-test-capable-custom"
            cleanup_handlers = (custom,)

        worker = CapableCustomWorker(work_pool_name="test")

        assert (
            worker.cleanup_handler_registry.get(CANCELLING_TIMEOUT_TEARDOWN) is custom
        )


class TestHandlerBehavior:
    async def test_releases_unexpected_payload_kind(self, work_pool: WorkPool):
        class _UnexpectedPayload:
            kind = "pending_claim_teardown.v1"

        async with TeardownTrackingWorker(work_pool_name=work_pool.name) as worker:
            handler = _handler_for(worker)
            result = await handler.cleanup(_UnexpectedPayload())  # type: ignore[arg-type]

        assert result == CleanupExecutionResult.release("unexpected_payload_kind")
        assert worker.kill_calls == []

    async def test_releases_invalid_payload_when_flow_run_id_missing(
        self, work_pool: WorkPool
    ):
        # Pydantic enforces `flow_run_id` at the protocol layer; this exercises
        # the handler's defense-in-depth path by mutating it post-validation.
        payload = _cancelling_payload()
        payload.target.flow_run_id = None  # type: ignore[assignment]

        async with TeardownTrackingWorker(work_pool_name=work_pool.name) as worker:
            handler = _handler_for(worker)
            result = await handler.cleanup(payload)

        assert result == CleanupExecutionResult.release("invalid_payload")
        assert worker.kill_calls == []

    async def test_deleted_flow_run_is_idempotent_success(self, work_pool: WorkPool):
        async with TeardownTrackingWorker(work_pool_name=work_pool.name) as worker:
            handler = _handler_for(worker)
            result = await handler.cleanup(
                _cancelling_payload(flow_run_id=uuid4(), infrastructure_pid="pid")
            )

        assert result == CleanupExecutionResult.success()
        assert worker.kill_calls == []

    async def test_missing_pid_with_no_stored_pid_acks_as_noop(
        self,
        prefect_client: PrefectClient,
        work_pool: WorkPool,
    ):
        flow_run = await _create_flow_run(prefect_client, work_pool)

        async with TeardownTrackingWorker(work_pool_name=work_pool.name) as worker:
            handler = _handler_for(worker)
            result = await handler.cleanup(
                _cancelling_payload(flow_run_id=flow_run.id, infrastructure_pid=None)
            )

        assert result == CleanupExecutionResult.success()
        assert worker.kill_calls == []

    async def test_missing_pid_with_stored_pid_releases_missing_handle(
        self,
        prefect_client: PrefectClient,
        work_pool: WorkPool,
    ):
        flow_run = await _create_flow_run(
            prefect_client, work_pool, infrastructure_pid="stored-pid"
        )

        async with TeardownTrackingWorker(work_pool_name=work_pool.name) as worker:
            handler = _handler_for(worker)
            result = await handler.cleanup(
                _cancelling_payload(flow_run_id=flow_run.id, infrastructure_pid=None)
            )

        assert result == CleanupExecutionResult.release("missing_infrastructure_handle")
        assert worker.kill_calls == []

    async def test_empty_string_pid_treated_as_missing(
        self,
        prefect_client: PrefectClient,
        work_pool: WorkPool,
    ):
        flow_run = await _create_flow_run(prefect_client, work_pool)

        async with TeardownTrackingWorker(work_pool_name=work_pool.name) as worker:
            handler = _handler_for(worker)
            result = await handler.cleanup(
                _cancelling_payload(flow_run_id=flow_run.id, infrastructure_pid="")
            )

        assert result == CleanupExecutionResult.success()
        assert worker.kill_calls == []

    async def test_configuration_unavailable_releases_with_stable_reason(
        self,
        prefect_client: PrefectClient,
        work_pool: WorkPool,
    ):
        flow_run = await _create_flow_run(
            prefect_client, work_pool, infrastructure_pid="pid"
        )

        async with TeardownTrackingWorker(work_pool_name=work_pool.name) as worker:
            handler = _handler_for(worker)
            with mock.patch.object(
                worker.job_configuration,
                "resolve_for_flow_run",
                AsyncMock(side_effect=ObjectNotFound(Exception("deployment gone"))),
            ):
                result = await handler.cleanup(
                    _cancelling_payload(
                        flow_run_id=flow_run.id, infrastructure_pid="pid"
                    )
                )

        assert result == CleanupExecutionResult.release(
            "configuration_context_unavailable"
        )
        assert worker.kill_calls == []

    async def test_infrastructure_not_found_acks_as_idempotent_success(
        self,
        prefect_client: PrefectClient,
        work_pool: WorkPool,
    ):
        flow_run = await _create_flow_run(
            prefect_client, work_pool, infrastructure_pid="pid"
        )

        async with TeardownTrackingWorker(work_pool_name=work_pool.name) as worker:
            worker.kill_side_effect = InfrastructureNotFound("gone")
            handler = _handler_for(worker)
            result = await handler.cleanup(
                _cancelling_payload(flow_run_id=flow_run.id, infrastructure_pid="pid")
            )

        assert result == CleanupExecutionResult.success()
        assert len(worker.kill_calls) == 1

    async def test_not_implemented_releases_unsupported_worker_type(
        self,
        prefect_client: PrefectClient,
        work_pool: WorkPool,
    ):
        flow_run = await _create_flow_run(
            prefect_client, work_pool, infrastructure_pid="pid"
        )

        async with TeardownTrackingWorker(work_pool_name=work_pool.name) as worker:
            worker.kill_side_effect = NotImplementedError("nope")
            handler = _handler_for(worker)
            result = await handler.cleanup(
                _cancelling_payload(flow_run_id=flow_run.id, infrastructure_pid="pid")
            )

        assert result == CleanupExecutionResult.release("unsupported_worker_type")

    async def test_infrastructure_unavailable_releases_with_stable_reason(
        self,
        prefect_client: PrefectClient,
        work_pool: WorkPool,
    ):
        flow_run = await _create_flow_run(
            prefect_client, work_pool, infrastructure_pid="pid"
        )

        async with TeardownTrackingWorker(work_pool_name=work_pool.name) as worker:
            worker.kill_side_effect = InfrastructureNotAvailable("offline")
            handler = _handler_for(worker)
            result = await handler.cleanup(
                _cancelling_payload(flow_run_id=flow_run.id, infrastructure_pid="pid")
            )

        assert result == CleanupExecutionResult.release("infrastructure_not_available")

    async def test_successful_kill_acks(
        self,
        prefect_client: PrefectClient,
        work_pool: WorkPool,
    ):
        flow_run = await _create_flow_run(
            prefect_client, work_pool, infrastructure_pid="pid"
        )

        async with TeardownTrackingWorker(work_pool_name=work_pool.name) as worker:
            handler = _handler_for(worker)
            result = await handler.cleanup(
                _cancelling_payload(flow_run_id=flow_run.id, infrastructure_pid="pid")
            )

        assert result == CleanupExecutionResult.success()
        assert len(worker.kill_calls) == 1
        call = worker.kill_calls[0]
        assert call["infrastructure_pid"] == "pid"
        assert call["grace_seconds"] == 30
        assert isinstance(call["configuration"], BaseJobConfiguration)

    async def test_grace_seconds_is_configurable(
        self,
        prefect_client: PrefectClient,
        work_pool: WorkPool,
    ):
        flow_run = await _create_flow_run(
            prefect_client, work_pool, infrastructure_pid="pid"
        )

        async with TeardownTrackingWorker(work_pool_name=work_pool.name) as worker:
            handler = CancellingTimeoutTeardownHandler(worker, grace_seconds=10)
            await handler.cleanup(
                _cancelling_payload(flow_run_id=flow_run.id, infrastructure_pid="pid")
            )

        assert worker.kill_calls[0]["grace_seconds"] == 10

    async def test_does_not_skip_when_start_time_is_set(
        self,
        prefect_client: PrefectClient,
        work_pool: WorkPool,
    ):
        flow_run = await _create_flow_run(
            prefect_client,
            work_pool,
            state=Running(),
            infrastructure_pid="pid",
        )
        assert flow_run.start_time is not None

        async with TeardownTrackingWorker(work_pool_name=work_pool.name) as worker:
            handler = _handler_for(worker)
            result = await handler.cleanup(
                _cancelling_payload(flow_run_id=flow_run.id, infrastructure_pid="pid")
            )

        assert result == CleanupExecutionResult.success()
        assert len(worker.kill_calls) == 1

    async def test_does_not_skip_when_state_is_not_cancelling(
        self,
        prefect_client: PrefectClient,
        work_pool: WorkPool,
    ):
        flow_run = await _create_flow_run(
            prefect_client,
            work_pool,
            state=Pending(),
            infrastructure_pid="pid",
        )

        async with TeardownTrackingWorker(work_pool_name=work_pool.name) as worker:
            handler = _handler_for(worker)
            result = await handler.cleanup(
                _cancelling_payload(flow_run_id=flow_run.id, infrastructure_pid="pid")
            )

        assert result == CleanupExecutionResult.success()
        assert len(worker.kill_calls) == 1

    async def test_does_not_mutate_flow_run_state(
        self,
        prefect_client: PrefectClient,
        work_pool: WorkPool,
    ):
        flow_run = await _create_flow_run(
            prefect_client,
            work_pool,
            state=Running(),
            infrastructure_pid="pid",
        )
        assert flow_run.state is not None
        original_state_id = flow_run.state.id
        original_state_type = flow_run.state.type

        async with TeardownTrackingWorker(work_pool_name=work_pool.name) as worker:
            handler = _handler_for(worker)
            await handler.cleanup(
                _cancelling_payload(flow_run_id=flow_run.id, infrastructure_pid="pid")
            )

        refreshed = await prefect_client.read_flow_run(flow_run.id)
        assert refreshed.state is not None
        assert refreshed.state.id == original_state_id
        assert refreshed.state.type == original_state_type

    async def test_uses_payload_pid_not_flow_run_pid(
        self,
        prefect_client: PrefectClient,
        work_pool: WorkPool,
    ):
        flow_run = await _create_flow_run(
            prefect_client, work_pool, infrastructure_pid="flow-run-pid"
        )

        async with TeardownTrackingWorker(work_pool_name=work_pool.name) as worker:
            handler = _handler_for(worker)
            await handler.cleanup(
                _cancelling_payload(
                    flow_run_id=flow_run.id, infrastructure_pid="payload-pid"
                )
            )

        assert len(worker.kill_calls) == 1
        assert worker.kill_calls[0]["infrastructure_pid"] == "payload-pid"


@pytest.mark.parametrize(
    "kill_side_effect,expected_reason",
    [
        (InfrastructureNotAvailable("offline"), "infrastructure_not_available"),
        (NotImplementedError("nope"), "unsupported_worker_type"),
    ],
)
async def test_typed_kill_exceptions_map_to_stable_release_reasons(
    prefect_client: PrefectClient,
    work_pool: WorkPool,
    kill_side_effect: BaseException,
    expected_reason: str,
):
    flow_run = await _create_flow_run(
        prefect_client, work_pool, infrastructure_pid="pid"
    )

    async with TeardownTrackingWorker(work_pool_name=work_pool.name) as worker:
        worker.kill_side_effect = kill_side_effect
        handler = _handler_for(worker)
        result = await handler.cleanup(
            _cancelling_payload(flow_run_id=flow_run.id, infrastructure_pid="pid")
        )

    assert result == CleanupExecutionResult.release(expected_reason)


async def test_cleanup_handler_works_with_unrelated_deployment_context(
    prefect_client: PrefectClient,
    work_pool: WorkPool,
    deployment: DeploymentResponse,
):
    flow_run = await prefect_client.create_flow_run_from_deployment(
        deployment_id=deployment.id,
    )
    await prefect_client.update_flow_run(flow_run.id, infrastructure_pid="pid")

    async with TeardownTrackingWorker(work_pool_name=work_pool.name) as worker:
        handler = _handler_for(worker)
        result = await handler.cleanup(
            _cancelling_payload(flow_run_id=flow_run.id, infrastructure_pid="pid")
        )

    assert result == CleanupExecutionResult.success()
    assert len(worker.kill_calls) == 1
    assert worker.kill_calls[0]["infrastructure_pid"] == "pid"
