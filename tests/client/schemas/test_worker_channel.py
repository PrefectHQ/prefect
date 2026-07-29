from uuid import uuid4

import pytest
from pydantic import ValidationError

from prefect._internal.uuid7 import uuid7
from prefect.client.schemas.worker_channel import (
    CLEANUP_DELIVERY_CAPABILITY,
    REQUIRED_WORKER_CHANNEL_CAPABILITIES,
    SUPPORTED_CLEANUP_KINDS,
    WORK_POOL_SNAPSHOT_CAPABILITY,
    WORK_POOL_WORKER_CHANNEL_CONTRACT,
    WORK_POOL_WORKER_CHANNEL_ROUTE,
    WORK_POOL_WORKER_CHANNEL_VERSION,
    WORKER_CHANNEL_CLOSE_POLICIES,
    WORKER_HEARTBEAT_CAPABILITY,
    CleanupAckFrame,
    CleanupMessageFrame,
    CleanupOperationResultFrame,
    CleanupReleaseFrame,
    CleanupRenewFrame,
    WorkerChannelAuthRequest,
    WorkerChannelAuthSuccess,
    WorkerChannelCloseReason,
    WorkerChannelProtocolError,
    WorkerHelloFrame,
    WorkerReadyFrame,
    select_worker_channel_version,
    validate_worker_channel_frame,
)
from prefect.types._datetime import now


def _frame_base(frame_type: str) -> dict[str, object]:
    return {
        "type": frame_type,
        "id": str(uuid7()),
        "sent_at": now("UTC").isoformat(),
    }


def _work_pool_payload() -> dict[str, object]:
    return {
        "id": str(uuid4()),
        "name": "default",
        "type": "process",
        "base_job_template": {},
        "is_paused": False,
        "storage_configuration": {},
        "default_queue_id": str(uuid4()),
    }


def _hello_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "consumer_id": str(uuid7()),
        "worker_name": "process-worker-1",
        "worker_type": "process",
        "heartbeat_interval_seconds": 30,
        "supported_channel_versions": [WORK_POOL_WORKER_CHANNEL_VERSION],
        "requested_capabilities": [
            WORKER_HEARTBEAT_CAPABILITY,
            WORK_POOL_SNAPSHOT_CAPABILITY,
            CLEANUP_DELIVERY_CAPABILITY,
        ],
        "work_queue_names": ["default"],
        "handled_cleanup_kinds": list(SUPPORTED_CLEANUP_KINDS),
        "max_cleanup_concurrency": 1,
        "create_pool_if_not_found": True,
        "default_base_job_template": {},
        "worker_metadata": None,
    }
    payload.update(overrides)
    return payload


def _hello_frame(**payload_overrides: object) -> dict[str, object]:
    return {
        **_frame_base("worker.hello.v1"),
        "payload": _hello_payload(**payload_overrides),
    }


def _ready_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "consumer_id": str(uuid7()),
        "worker_id": str(uuid4()),
        "selected_channel_version": WORK_POOL_WORKER_CHANNEL_VERSION,
        "effective_heartbeat_interval_seconds": 30,
        "accepted_capabilities": [
            WORKER_HEARTBEAT_CAPABILITY,
            WORK_POOL_SNAPSHOT_CAPABILITY,
            CLEANUP_DELIVERY_CAPABILITY,
        ],
        "rejected_capabilities": [],
        "effective_max_cleanup_concurrency": 1,
        "resolved_work_queues": [{"id": str(uuid4()), "name": "default"}],
        "initial_snapshot": {
            "snapshot_sequence": 1,
            "reason": "initial",
            "work_pool": _work_pool_payload(),
        },
    }
    payload.update(overrides)
    return payload


def _ready_frame(**payload_overrides: object) -> dict[str, object]:
    return {
        **_frame_base("worker.ready.v1"),
        "payload": _ready_payload(**payload_overrides),
    }


def _pending_claim_cleanup_frame(
    target: dict[str, object],
    **payload_overrides: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "message_id": str(uuid4()),
        "kind": "pending_claim_teardown.v1",
        "reservation_token": "reservation-token",
        "lease_expires_at": now("UTC").isoformat(),
        "delivery_count": 1,
        "work_queue_id": None,
        "target": target,
        "data": {},
    }
    payload.update(payload_overrides)
    return {
        **_frame_base("cleanup.message.v1"),
        "payload": payload,
    }


def test_auth_setup_messages_are_outside_application_frame_envelope():
    assert WorkerChannelAuthRequest(type="auth", token=None).token is None
    assert WorkerChannelAuthRequest.model_validate({"type": "auth"}).token is None
    assert WorkerChannelAuthSuccess(type="auth_success").type == "auth_success"

    with pytest.raises(ValidationError):
        validate_worker_channel_frame({"type": "auth", "token": None})

    assert (
        WORK_POOL_WORKER_CHANNEL_CONTRACT.first_application_frame_type
        == "worker.hello.v1"
    )


def test_worker_hello_frame_validates_required_fields_and_capabilities():
    frame = validate_worker_channel_frame(_hello_frame())

    assert isinstance(frame, WorkerHelloFrame)
    assert (
        select_worker_channel_version(frame.payload.supported_channel_versions)
        == WORK_POOL_WORKER_CHANNEL_VERSION
    )
    assert REQUIRED_WORKER_CHANNEL_CAPABILITIES.issubset(
        set(frame.payload.requested_capabilities)
    )

    malformed = _hello_frame()
    del malformed["payload"]["worker_name"]  # type: ignore[index]

    with pytest.raises(ValidationError):
        validate_worker_channel_frame(malformed)


def test_worker_hello_rejects_missing_required_capability():
    with pytest.raises(ValidationError, match="Missing required channel capabilities"):
        WorkerHelloFrame.model_validate(
            _hello_frame(
                requested_capabilities=[
                    WORKER_HEARTBEAT_CAPABILITY,
                    CLEANUP_DELIVERY_CAPABILITY,
                ]
            )
        )


def test_worker_hello_defaults_cleanup_concurrency_when_cleanup_is_available():
    hello = _hello_frame()
    del hello["payload"]["max_cleanup_concurrency"]  # type: ignore[index]

    frame = WorkerHelloFrame.model_validate(hello)

    assert frame.payload.max_cleanup_concurrency == 1


def test_worker_hello_defaults_cleanup_concurrency_for_tuple_inputs():
    hello = _hello_frame(
        requested_capabilities=(
            WORKER_HEARTBEAT_CAPABILITY,
            WORK_POOL_SNAPSHOT_CAPABILITY,
            CLEANUP_DELIVERY_CAPABILITY,
        ),
        handled_cleanup_kinds=SUPPORTED_CLEANUP_KINDS,
    )
    del hello["payload"]["max_cleanup_concurrency"]  # type: ignore[index]

    frame = WorkerHelloFrame.model_validate(hello)

    assert frame.payload.max_cleanup_concurrency == 1


def test_worker_hello_defaults_cleanup_concurrency_to_zero_without_cleanup_kinds():
    hello = _hello_frame(handled_cleanup_kinds=[])
    del hello["payload"]["max_cleanup_concurrency"]  # type: ignore[index]

    frame = WorkerHelloFrame.model_validate(hello)

    assert frame.payload.max_cleanup_concurrency == 0


@pytest.mark.parametrize("requested_capabilities", [None, 1])
def test_worker_hello_rejects_malformed_capabilities_without_raw_type_error(
    requested_capabilities: object,
):
    hello = _hello_frame(requested_capabilities=requested_capabilities)
    del hello["payload"]["max_cleanup_concurrency"]  # type: ignore[index]

    with pytest.raises(ValidationError):
        validate_worker_channel_frame(hello)


def test_worker_hello_rejects_malformed_cleanup_kinds_without_raw_type_error():
    hello = _hello_frame(handled_cleanup_kinds=1)
    del hello["payload"]["max_cleanup_concurrency"]  # type: ignore[index]

    with pytest.raises(ValidationError):
        validate_worker_channel_frame(hello)


def test_worker_hello_allows_unknown_optional_capability_requests():
    future_capability = "future_optional_capability.v1"

    frame = WorkerHelloFrame.model_validate(
        _hello_frame(
            requested_capabilities=[
                WORKER_HEARTBEAT_CAPABILITY,
                WORK_POOL_SNAPSHOT_CAPABILITY,
                future_capability,
            ],
            handled_cleanup_kinds=[],
            max_cleanup_concurrency=0,
        )
    )

    assert future_capability in frame.payload.requested_capabilities


def test_unsupported_channel_version_maps_to_close_reason():
    frame = WorkerHelloFrame.model_validate(
        _hello_frame(supported_channel_versions=["work_pool_worker_channel.v2"])
    )

    with pytest.raises(WorkerChannelProtocolError) as exc_info:
        select_worker_channel_version(frame.payload.supported_channel_versions)

    assert exc_info.value.close_reason == WorkerChannelCloseReason.UNSUPPORTED_VERSION


def test_worker_ready_allows_optional_cleanup_delivery_rejection():
    frame = WorkerReadyFrame.model_validate(
        _ready_frame(
            accepted_capabilities=[
                WORKER_HEARTBEAT_CAPABILITY,
                WORK_POOL_SNAPSHOT_CAPABILITY,
            ],
            rejected_capabilities=[CLEANUP_DELIVERY_CAPABILITY],
            effective_max_cleanup_concurrency=0,
        )
    )

    assert CLEANUP_DELIVERY_CAPABILITY in frame.payload.rejected_capabilities
    assert frame.payload.effective_max_cleanup_concurrency == 0


def test_worker_ready_allows_unknown_optional_capability_rejection():
    future_capability = "future_optional_capability.v1"

    frame = WorkerReadyFrame.model_validate(
        _ready_frame(
            accepted_capabilities=[
                WORKER_HEARTBEAT_CAPABILITY,
                WORK_POOL_SNAPSHOT_CAPABILITY,
            ],
            rejected_capabilities=[future_capability],
            effective_max_cleanup_concurrency=0,
        )
    )

    assert future_capability in frame.payload.rejected_capabilities


def test_worker_ready_rejects_unknown_accepted_capability():
    with pytest.raises(ValidationError):
        WorkerReadyFrame.model_validate(
            _ready_frame(
                accepted_capabilities=[
                    WORKER_HEARTBEAT_CAPABILITY,
                    WORK_POOL_SNAPSHOT_CAPABILITY,
                    "future_optional_capability.v1",
                ],
                effective_max_cleanup_concurrency=0,
            )
        )


def test_worker_ready_rejects_required_capability_rejection():
    with pytest.raises(ValidationError, match="Missing accepted required capabilities"):
        WorkerReadyFrame.model_validate(
            _ready_frame(
                accepted_capabilities=[WORKER_HEARTBEAT_CAPABILITY],
                rejected_capabilities=[WORK_POOL_SNAPSHOT_CAPABILITY],
                effective_max_cleanup_concurrency=0,
            )
        )


def test_worker_ready_rejects_cleanup_concurrency_when_cleanup_unavailable():
    with pytest.raises(ValidationError, match="must be 0"):
        WorkerReadyFrame.model_validate(
            _ready_frame(
                accepted_capabilities=[
                    WORKER_HEARTBEAT_CAPABILITY,
                    WORK_POOL_SNAPSHOT_CAPABILITY,
                ],
                rejected_capabilities=[CLEANUP_DELIVERY_CAPABILITY],
                effective_max_cleanup_concurrency=1,
            )
        )


def test_worker_ready_rejects_zero_cleanup_concurrency_when_cleanup_accepted():
    with pytest.raises(ValidationError, match="must be positive"):
        WorkerReadyFrame.model_validate(
            _ready_frame(effective_max_cleanup_concurrency=0)
        )


def test_worker_ready_rejects_initial_snapshot_sequence_other_than_one():
    with pytest.raises(ValidationError, match="initial snapshot sequence must be 1"):
        WorkerReadyFrame.model_validate(
            _ready_frame(
                initial_snapshot={
                    "snapshot_sequence": 2,
                    "reason": "initial",
                    "work_pool": _work_pool_payload(),
                }
            )
        )


def test_frame_validator_rejects_unknown_type_and_malformed_frames():
    with pytest.raises(ValidationError):
        validate_worker_channel_frame(
            {
                **_frame_base("worker.goodbye.v1"),
                "payload": {},
            }
        )

    malformed = _hello_frame()
    malformed["unexpected"] = True

    with pytest.raises(ValidationError):
        validate_worker_channel_frame(malformed)


def test_snapshot_frame_validates_full_work_pool_replacement_payload():
    frame = validate_worker_channel_frame(
        {
            **_frame_base("work_pool.snapshot.v1"),
            "payload": {
                "snapshot_sequence": 2,
                "reason": "work_pool_updated",
                "work_pool": _work_pool_payload(),
            },
        }
    )

    assert frame.type == "work_pool.snapshot.v1"

    with pytest.raises(ValidationError):
        validate_worker_channel_frame(
            {
                **_frame_base("work_pool.snapshot.v1"),
                "payload": {
                    "snapshot_sequence": 0,
                    "reason": "work_pool_updated",
                    "work_pool": _work_pool_payload(),
                },
            }
        )


@pytest.mark.parametrize(
    "field",
    [
        "id",
        "base_job_template",
        "is_paused",
        "storage_configuration",
        "default_queue_id",
    ],
)
def test_snapshot_frame_requires_full_work_pool_replacement_state(field: str):
    work_pool = _work_pool_payload()
    del work_pool[field]

    with pytest.raises(ValidationError):
        validate_worker_channel_frame(
            {
                **_frame_base("work_pool.snapshot.v1"),
                "payload": {
                    "snapshot_sequence": 2,
                    "reason": "work_pool_updated",
                    "work_pool": work_pool,
                },
            }
        )


@pytest.mark.parametrize("field", ["default_queue_id", "storage_configuration"])
def test_snapshot_frame_rejects_null_required_work_pool_state(field: str):
    work_pool = _work_pool_payload()
    work_pool[field] = None

    with pytest.raises(ValidationError):
        validate_worker_channel_frame(
            {
                **_frame_base("work_pool.snapshot.v1"),
                "payload": {
                    "snapshot_sequence": 2,
                    "reason": "work_pool_updated",
                    "work_pool": work_pool,
                },
            }
        )


@pytest.mark.parametrize(
    "field",
    [
        "id",
        "base_job_template",
        "is_paused",
        "storage_configuration",
        "default_queue_id",
    ],
)
def test_worker_ready_initial_snapshot_requires_full_work_pool_replacement_state(
    field: str,
):
    work_pool = _work_pool_payload()
    del work_pool[field]

    with pytest.raises(ValidationError):
        validate_worker_channel_frame(
            _ready_frame(
                initial_snapshot={
                    "snapshot_sequence": 1,
                    "reason": "initial",
                    "work_pool": work_pool,
                }
            )
        )


def test_cleanup_message_validates_supported_kinds_and_kind_specific_targets():
    cancelling = CleanupMessageFrame.model_validate(
        {
            **_frame_base("cleanup.message.v1"),
            "payload": {
                "message_id": str(uuid4()),
                "kind": "cancelling_timeout_teardown.v1",
                "reservation_token": "reservation-token",
                "lease_expires_at": now("UTC").isoformat(),
                "delivery_count": 1,
                "work_queue_id": None,
                "target": {
                    "flow_run_id": str(uuid4()),
                    "infrastructure_pid": "pid-123",
                },
                "data": {},
            },
        }
    )

    assert cancelling.payload.kind == "cancelling_timeout_teardown.v1"

    pending_claim = CleanupMessageFrame.model_validate(
        {
            **_frame_base("cleanup.message.v1"),
            "payload": {
                "message_id": str(uuid4()),
                "kind": "pending_claim_teardown.v1",
                "reservation_token": "reservation-token",
                "lease_expires_at": now("UTC").isoformat(),
                "delivery_count": 1,
                "work_queue_id": str(uuid4()),
                "target": {
                    "flow_run_id": str(uuid4()),
                    "claim_id": str(uuid7()),
                    "execution_id": str(uuid7()),
                    "infrastructure_pid": None,
                },
                "data": {},
            },
        }
    )

    assert pending_claim.payload.kind == "pending_claim_teardown.v1"

    with pytest.raises(ValidationError):
        CleanupMessageFrame.model_validate(
            {
                **_frame_base("cleanup.message.v1"),
                "payload": {
                    "message_id": str(uuid4()),
                    "kind": "pending_claim_teardown.v1",
                    "reservation_token": "reservation-token",
                    "lease_expires_at": now("UTC").isoformat(),
                    "delivery_count": 1,
                    "target": {"flow_run_id": str(uuid4())},
                    "data": {},
                },
            }
        )


def test_pending_claim_cleanup_accepts_required_target_fields_only():
    flow_run_id = uuid4()
    claim_id = uuid7()

    frame = CleanupMessageFrame.model_validate(
        _pending_claim_cleanup_frame(
            {
                "flow_run_id": str(flow_run_id),
                "claim_id": str(claim_id),
            }
        )
    )

    assert frame.payload.work_queue_id is None
    assert frame.payload.target.flow_run_id == flow_run_id
    assert frame.payload.target.claim_id == claim_id
    assert frame.payload.target.execution_id is None
    assert frame.payload.target.infrastructure_pid is None


@pytest.mark.parametrize("field", ["flow_run_id", "claim_id"])
def test_pending_claim_cleanup_requires_claim_identity(field: str):
    target = {
        "flow_run_id": str(uuid4()),
        "claim_id": str(uuid7()),
    }
    del target[field]

    with pytest.raises(ValidationError):
        CleanupMessageFrame.model_validate(_pending_claim_cleanup_frame(target))


def test_pending_claim_cleanup_preserves_forward_compatible_hints():
    frame = CleanupMessageFrame.model_validate(
        _pending_claim_cleanup_frame(
            {
                "flow_run_id": str(uuid4()),
                "claim_id": str(uuid7()),
                "execution_id": str(uuid7()),
                "infrastructure_pid": "provider/resource",
                "future_target_hint": {"label": "claim"},
            },
            data={"future_data_hint": {"region": "us-east"}},
        )
    )

    assert frame.payload.target.model_dump()["future_target_hint"] == {"label": "claim"}
    assert frame.payload.data == {"future_data_hint": {"region": "us-east"}}


def test_pending_claim_cleanup_preserves_unknown_routing_looking_target_fields():
    work_pool_id = uuid4()
    work_queue_id = uuid4()

    frame = CleanupMessageFrame.model_validate(
        _pending_claim_cleanup_frame(
            {
                "flow_run_id": str(uuid4()),
                "claim_id": str(uuid7()),
                "work_pool_id": str(work_pool_id),
                "work_queue_id": str(work_queue_id),
            }
        )
    )

    target = frame.payload.target.model_dump()
    assert target["work_pool_id"] == str(work_pool_id)
    assert target["work_queue_id"] == str(work_queue_id)


@pytest.mark.parametrize("field", ["work_pool_id", "idempotency_key"])
def test_cleanup_wire_payload_rejects_internal_enqueue_fields(field: str):
    with pytest.raises(ValidationError):
        CleanupMessageFrame.model_validate(
            _pending_claim_cleanup_frame(
                {
                    "flow_run_id": str(uuid4()),
                    "claim_id": str(uuid7()),
                },
                **{field: str(uuid4())},
            )
        )


def test_pending_claim_cleanup_treats_delivered_identifiers_as_opaque_uuids():
    claim_id = uuid4()
    execution_id = uuid4()

    frame = CleanupMessageFrame.model_validate(
        _pending_claim_cleanup_frame(
            {
                "flow_run_id": str(uuid4()),
                "claim_id": str(claim_id),
                "execution_id": str(execution_id),
            }
        )
    )

    assert frame.payload.target.claim_id == claim_id
    assert frame.payload.target.execution_id == execution_id


def test_cleanup_operation_frames_and_results_validate_reservation_contract():
    operation_payload = {
        "message_id": str(uuid4()),
        "reservation_token": "reservation-token",
    }

    assert CleanupAckFrame.model_validate(
        {**_frame_base("cleanup.ack.v1"), "payload": operation_payload}
    )
    assert CleanupRenewFrame.model_validate(
        {**_frame_base("cleanup.renew.v1"), "payload": operation_payload}
    )
    assert CleanupReleaseFrame.model_validate(
        {
            **_frame_base("cleanup.release.v1"),
            "payload": {**operation_payload, "reason": "cannot_act"},
        }
    )

    with pytest.raises(ValidationError):
        CleanupReleaseFrame.model_validate(
            {**_frame_base("cleanup.release.v1"), "payload": operation_payload}
        )

    accepted_renew = CleanupOperationResultFrame.model_validate(
        {
            **_frame_base("cleanup.operation_result.v1"),
            "payload": {
                "request_frame_id": str(uuid7()),
                "message_id": operation_payload["message_id"],
                "operation": "renew",
                "status": "accepted",
                "lease_expires_at": now("UTC").isoformat(),
                "reason": None,
                "detail": None,
            },
        }
    )

    assert accepted_renew.payload.status == "accepted"

    with pytest.raises(ValidationError, match="reason"):
        CleanupOperationResultFrame.model_validate(
            {
                **_frame_base("cleanup.operation_result.v1"),
                "payload": {
                    "request_frame_id": str(uuid7()),
                    "message_id": operation_payload["message_id"],
                    "operation": "ack",
                    "status": "invalid_token",
                },
            }
        )

    with pytest.raises(ValidationError, match="lease_expires_at"):
        CleanupOperationResultFrame.model_validate(
            {
                **_frame_base("cleanup.operation_result.v1"),
                "payload": {
                    "request_frame_id": str(uuid7()),
                    "message_id": operation_payload["message_id"],
                    "operation": "ack",
                    "status": "accepted",
                    "lease_expires_at": now("UTC").isoformat(),
                },
            }
        )


def test_close_reason_categories_match_protocol_spec():
    assert set(WORKER_CHANNEL_CLOSE_POLICIES) == {
        WorkerChannelCloseReason.AUTHENTICATION_FAILED,
        WorkerChannelCloseReason.AUTHORIZATION_FAILED,
        WorkerChannelCloseReason.UNSUPPORTED_VERSION,
        WorkerChannelCloseReason.PROTOCOL_ERROR,
        WorkerChannelCloseReason.HEARTBEAT_PERSISTENCE_FAILED,
        WorkerChannelCloseReason.TRANSIENT_SERVER_ERROR,
    }
    assert (
        WORKER_CHANNEL_CLOSE_POLICIES[
            WorkerChannelCloseReason.AUTHENTICATION_FAILED
        ].websocket_code
        == 1008
    )
    assert (
        WORKER_CHANNEL_CLOSE_POLICIES[
            WorkerChannelCloseReason.PROTOCOL_ERROR
        ].websocket_code
        == 1002
    )
    assert (
        WORKER_CHANNEL_CLOSE_POLICIES[
            WorkerChannelCloseReason.TRANSIENT_SERVER_ERROR
        ].websocket_code
        == 1011
    )
    assert not WORKER_CHANNEL_CLOSE_POLICIES[
        WorkerChannelCloseReason.UNSUPPORTED_VERSION
    ].retryable
    assert WORKER_CHANNEL_CLOSE_POLICIES[
        WorkerChannelCloseReason.HEARTBEAT_PERSISTENCE_FAILED
    ].retryable


def test_contract_states_channel_boundaries_and_rollout_expectations():
    contract = WORK_POOL_WORKER_CHANNEL_CONTRACT

    assert contract.route == WORK_POOL_WORKER_CHANNEL_ROUTE
    assert contract.scheduled_flow_run_acquisition == "rest"
    assert contract.worker_startup_rollout == "opportunistic_without_user_setting"
    assert contract.worker_side_cancellation_observation == "event_subscription"
    assert (
        contract.cleanup_delivery_guarantee
        == "at_least_once_one_active_reservation_per_message"
    )
    assert contract.cleanup_delivery_authority == "reservation_token"
    assert contract.cloud_authorization_internals == "excluded_from_shared_contract"
    assert set(contract.required_capabilities) == REQUIRED_WORKER_CHANNEL_CAPABILITIES
    assert contract.optional_capabilities == (CLEANUP_DELIVERY_CAPABILITY,)
    assert contract.supported_cleanup_kinds == SUPPORTED_CLEANUP_KINDS
