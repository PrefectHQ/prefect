from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from prefect._internal.uuid7 import uuid7
from prefect.client.schemas.pending_claims import (
    PENDING_CLAIM_CONTRACT,
    BindExecutionRequest,
    ClaimInfrastructureRequest,
    ExecutionLineage,
    PendingClaim,
    PendingClaimCreate,
    PendingClaimReference,
    PendingTimeoutCount,
    pending_claim_teardown_idempotency_key,
)


def test_pending_claim_metadata_supports_unbound_execution_and_future_fields():
    claim_id = uuid7()

    claim = PendingClaim.model_validate(
        {
            "id": claim_id,
            "execution_id": None,
            "timeout_seconds": 300,
            "max_timeouts": 3,
            "future_policy": {"mode": "adaptive"},
        }
    )

    assert claim.id == claim_id
    assert claim.execution_id is None
    assert claim.model_dump()["future_policy"] == {"mode": "adaptive"}


@pytest.mark.parametrize("field", ["timeout_seconds", "max_timeouts"])
def test_pending_claim_metadata_requires_resolved_server_policy(field: str):
    payload = {
        "id": uuid7(),
        "timeout_seconds": 300,
        "max_timeouts": 3,
    }
    del payload[field]

    with pytest.raises(ValidationError):
        PendingClaim.model_validate(payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("execution_id", uuid7()),
        ("timeout_seconds", 1),
        ("timeout_seconds", 3600),
        ("max_timeouts", 1),
        ("max_timeouts", 100),
        ("pending_timeout_count", 0),
        ("pending_timeout_count", 999),
    ],
)
def test_initial_claim_cannot_rewrite_server_policy_or_count(field: str, value: object):
    with pytest.raises(ValidationError):
        PendingClaimCreate.model_validate({"id": uuid7(), field: value})


def test_claim_and_execution_identifiers_must_be_uuid7():
    with pytest.raises(ValidationError):
        PendingClaimCreate(id=uuid4())

    with pytest.raises(ValidationError):
        PendingClaimReference(claim_id=uuid4(), execution_id=uuid7())

    with pytest.raises(ValidationError):
        PendingClaimReference(claim_id=uuid7(), execution_id=uuid4())


def test_claim_execution_request_schemas_share_identifier_contract():
    claim_id = uuid7()
    execution_id = uuid7()

    reference = PendingClaimReference(
        claim_id=claim_id,
        execution_id=execution_id,
    )
    binding = BindExecutionRequest(
        claim_id=claim_id,
        execution_id=execution_id,
    )
    infrastructure = ClaimInfrastructureRequest(
        claim_id=claim_id,
        execution_id=execution_id,
        infrastructure_pid="provider/resource",
    )

    assert reference.model_dump() == binding.model_dump()
    assert infrastructure.claim_id == claim_id
    assert infrastructure.execution_id == execution_id


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("timeout_seconds", 300),
        ("max_timeouts", 3),
        ("pending_timeout_count", 1),
        ("execution_lineage", {"claim_id": uuid7(), "execution_id": uuid7()}),
    ],
)
def test_running_reference_rejects_stored_or_server_authored_fields(
    field: str, value: object
):
    with pytest.raises(ValidationError):
        PendingClaimReference.model_validate(
            {
                "claim_id": uuid7(),
                "execution_id": uuid7(),
                field: value,
            }
        )


@pytest.mark.parametrize(
    ("model", "payload", "missing_field"),
    [
        (
            PendingClaimReference,
            {"claim_id": uuid7(), "execution_id": uuid7()},
            "claim_id",
        ),
        (
            PendingClaimReference,
            {"claim_id": uuid7(), "execution_id": uuid7()},
            "execution_id",
        ),
        (
            BindExecutionRequest,
            {"claim_id": uuid7(), "execution_id": uuid7()},
            "claim_id",
        ),
        (
            BindExecutionRequest,
            {"claim_id": uuid7(), "execution_id": uuid7()},
            "execution_id",
        ),
        (
            ClaimInfrastructureRequest,
            {
                "claim_id": uuid7(),
                "execution_id": uuid7(),
                "infrastructure_pid": "provider/resource",
            },
            "claim_id",
        ),
        (
            ClaimInfrastructureRequest,
            {
                "claim_id": uuid7(),
                "execution_id": uuid7(),
                "infrastructure_pid": "provider/resource",
            },
            "execution_id",
        ),
        (
            ClaimInfrastructureRequest,
            {
                "claim_id": uuid7(),
                "execution_id": uuid7(),
                "infrastructure_pid": "provider/resource",
            },
            "infrastructure_pid",
        ),
    ],
)
def test_claim_execution_requests_require_operation_identifiers(
    model: type[
        PendingClaimReference | BindExecutionRequest | ClaimInfrastructureRequest
    ],
    payload: dict[str, object],
    missing_field: str,
):
    del payload[missing_field]

    with pytest.raises(ValidationError):
        model.model_validate(payload)


def test_execution_lineage_is_server_authored_and_forward_compatible():
    lineage = ExecutionLineage.model_validate(
        {
            "claim_id": uuid7(),
            "execution_id": uuid7(),
            "future_lineage_hint": "value",
        }
    )

    assert lineage.model_dump()["future_lineage_hint"] == "value"


def test_pending_timeout_count_is_non_negative():
    adapter = TypeAdapter(PendingTimeoutCount)

    assert adapter.validate_python(0) == 0
    assert adapter.validate_python(2) == 2
    with pytest.raises(ValidationError):
        adapter.validate_python(-1)


def test_contract_defines_canonical_ownership_and_cross_claim_count():
    assert PENDING_CLAIM_CONTRACT.initial_claim_client_fields == ("id",)
    assert PENDING_CLAIM_CONTRACT.initial_claim_server_managed_fields == (
        "execution_id",
        "timeout_seconds",
        "max_timeouts",
        "pending_timeout_count",
    )
    assert (
        PENDING_CLAIM_CONTRACT.ownership_authority
        == "canonical_current_orchestration_state"
    )
    assert (
        PENDING_CLAIM_CONTRACT.ownership_serialization
        == "owning_state_transition_per_flow_run"
    )
    assert PENDING_CLAIM_CONTRACT.serialized_ownership_mutations == (
        "binding",
        "ownership_transfer",
        "forced_exit",
        "expiry",
    )
    assert (
        PENDING_CLAIM_CONTRACT.timeout_count_authority
        == "canonical_current_orchestration_state"
    )
    assert (
        PENDING_CLAIM_CONTRACT.pending_substate_identity
        == "claim_id_not_state_record_id"
    )
    assert (
        PENDING_CLAIM_CONTRACT.pending_substate_behavior
        == "preserve_pending_claim_and_timeout_count"
    )
    assert PENDING_CLAIM_CONTRACT.replacement_claim_behavior == "preserve_timeout_count"
    assert (
        PENDING_CLAIM_CONTRACT.valid_expiry_behavior
        == "atomically_increment_timeout_count"
    )
    assert (
        PENDING_CLAIM_CONTRACT.accepted_running_behavior
        == "clear_pending_claim_and_timeout_count_write_execution_lineage"
    )


def test_stale_or_mismatched_startup_aborts_without_user_code():
    assert PENDING_CLAIM_CONTRACT.stale_or_mismatched_startup_outcome == "ABORT"
    assert PENDING_CLAIM_CONTRACT.abort_action == "exit_without_user_code"


def test_contract_defines_claim_aware_startup_outcomes():
    assert PENDING_CLAIM_CONTRACT.matching_bound_startup_outcome == "ACCEPT"
    assert PENDING_CLAIM_CONTRACT.unbound_execution_startup_outcome == "WAIT"
    assert PENDING_CLAIM_CONTRACT.accept_action == "start_user_code"
    assert PENDING_CLAIM_CONTRACT.wait_action == "retry"
    assert PENDING_CLAIM_CONTRACT.reject_action == "exit_without_user_code"
    assert PENDING_CLAIM_CONTRACT.abort_action == "exit_without_user_code"


def test_pending_claim_teardown_identity_excludes_optional_targeting_fields():
    flow_run_id = uuid4()
    claim_id = uuid7()

    assert pending_claim_teardown_idempotency_key(flow_run_id, claim_id) == (
        f"pending_claim_teardown.v1:{flow_run_id}:{claim_id}"
    )
    assert PENDING_CLAIM_CONTRACT.teardown_semantic_idempotency == "claim_id"
