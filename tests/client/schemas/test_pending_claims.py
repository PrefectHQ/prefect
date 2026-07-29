from uuid import UUID, uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from prefect._internal.uuid7 import uuid7
from prefect.client.schemas.pending_claims import (
    BindExecutionRequest,
    ClaimInfrastructureRequest,
    ExecutionLineage,
    PendingClaim,
    PendingClaimCreate,
    PendingClaimCreateFields,
    PendingClaimOperationResult,
    PendingClaimReference,
    PendingClaimRunningFields,
    PendingClaimStateDetails,
    PendingTimeoutCount,
    pending_claim_startup_action,
    pending_claim_startup_disposition,
    pending_claim_teardown_idempotency_key,
)
from prefect.client.schemas.responses import SetStateStatus


def _pending_claim(
    *,
    claim_id: UUID | None = None,
    execution_id: UUID | None = None,
) -> PendingClaim:
    return PendingClaim(
        id=claim_id or uuid7(),
        execution_id=execution_id,
        timeout_seconds=300,
        max_timeouts=3,
    )


def _startup_scenario(
    expected: SetStateStatus,
    *,
    bound: bool = True,
    matching_claim: bool = True,
    matching_execution: bool = True,
) -> tuple[PendingClaim, PendingClaimReference, SetStateStatus]:
    claim_id = uuid7()
    bound_execution_id = uuid7() if bound else None
    active_claim = _pending_claim(
        claim_id=claim_id,
        execution_id=bound_execution_id,
    )
    reference = PendingClaimReference(
        claim_id=claim_id if matching_claim else uuid7(),
        execution_id=(
            bound_execution_id
            if bound_execution_id is not None and matching_execution
            else uuid7()
        ),
    )
    return active_claim, reference, expected


def test_pending_claim_metadata_supports_unbound_execution_and_future_fields():
    claim_id = uuid4()

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
    ],
)
def test_initial_claim_cannot_rewrite_nested_server_fields(field: str, value: object):
    with pytest.raises(ValidationError):
        PendingClaimCreateFields.model_validate(
            {
                "pending_claim": {
                    "id": uuid7(),
                    field: value,
                }
            }
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("pending_timeout_count", 0),
        ("pending_timeout_count", 999),
        (
            "execution_lineage",
            {"claim_id": uuid7(), "execution_id": uuid7()},
        ),
    ],
)
def test_initial_claim_cannot_inject_sibling_server_fields(field: str, value: object):
    with pytest.raises(ValidationError):
        PendingClaimCreateFields.model_validate(
            {
                "pending_claim": {"id": uuid7()},
                field: value,
            }
        )


def test_claim_and_execution_requests_require_uuid7():
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
        PendingClaimRunningFields.model_validate(
            {
                "pending_claim": {
                    "claim_id": uuid7(),
                    "execution_id": uuid7(),
                },
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


def test_persisted_lineage_accepts_opaque_uuids_and_future_fields():
    claim_id = uuid4()
    execution_id = uuid4()

    lineage = ExecutionLineage.model_validate(
        {
            "claim_id": claim_id,
            "execution_id": execution_id,
            "future_lineage_hint": "value",
        }
    )

    assert lineage.claim_id == claim_id
    assert lineage.execution_id == execution_id
    assert lineage.model_dump()["future_lineage_hint"] == "value"


def test_pending_timeout_count_is_non_negative():
    adapter = TypeAdapter(PendingTimeoutCount)

    assert adapter.validate_python(0) == 0
    assert adapter.validate_python(2) == 2
    with pytest.raises(ValidationError):
        adapter.validate_python(-1)


def test_named_pending_substate_round_trip_preserves_claim_and_sequence_count():
    active_claim = _pending_claim(execution_id=uuid7())
    canonical = PendingClaimStateDetails(
        pending_claim=active_claim,
        pending_timeout_count=2,
        future_state_hint={"source": "server"},
    )
    original_state_record_id = uuid4()
    named_substate_record_id = uuid4()

    named_substate = PendingClaimStateDetails.model_validate(
        canonical.model_dump(mode="json")
    )

    assert named_substate_record_id != original_state_record_id
    assert named_substate.pending_claim == active_claim
    assert named_substate.pending_timeout_count == 2
    assert named_substate.model_dump()["future_state_hint"] == {"source": "server"}


def test_replacement_claim_inherits_count_until_running_is_accepted():
    first_claim = _pending_claim()
    canonical = PendingClaimStateDetails(
        pending_claim=first_claim,
        pending_timeout_count=1,
    )
    assert canonical.pending_timeout_count is not None
    count_after_valid_expiry = canonical.pending_timeout_count + 1
    replacement_claim = _pending_claim()
    replacement = PendingClaimStateDetails(
        pending_claim=replacement_claim,
        pending_timeout_count=count_after_valid_expiry,
    )

    assert replacement.pending_claim.id != first_claim.id
    assert replacement.pending_timeout_count == 2

    accepted_running = PendingClaimStateDetails(
        execution_lineage=ExecutionLineage(
            claim_id=replacement_claim.id,
            execution_id=uuid7(),
        )
    )

    assert accepted_running.pending_claim is None
    assert accepted_running.pending_timeout_count is None
    assert accepted_running.execution_lineage is not None
    assert accepted_running.execution_lineage.claim_id == replacement_claim.id


@pytest.mark.parametrize(
    ("active_claim", "reference", "expected"),
    [
        pytest.param(
            *_startup_scenario(SetStateStatus.ACCEPT),
            id="matching-bound-execution",
        ),
        pytest.param(
            *_startup_scenario(
                SetStateStatus.WAIT,
                bound=False,
            ),
            id="matching-unbound-execution",
        ),
        pytest.param(
            *_startup_scenario(
                SetStateStatus.ABORT,
                matching_claim=False,
            ),
            id="stale-claim",
        ),
        pytest.param(
            *_startup_scenario(
                SetStateStatus.ABORT,
                matching_execution=False,
            ),
            id="mismatched-execution",
        ),
        pytest.param(
            None,
            PendingClaimReference(
                claim_id=uuid7(),
                execution_id=uuid7(),
            ),
            SetStateStatus.ABORT,
            id="no-active-claim",
        ),
    ],
)
def test_startup_disposition_uses_canonical_current_claim(
    active_claim: PendingClaim | None,
    reference: PendingClaimReference,
    expected: SetStateStatus,
):
    canonical = PendingClaimStateDetails(pending_claim=active_claim)

    assert pending_claim_startup_disposition(canonical, reference) == expected


@pytest.mark.parametrize(
    ("status", "expected_action"),
    [
        (SetStateStatus.ACCEPT, "start_user_code"),
        (SetStateStatus.WAIT, "retry"),
        (SetStateStatus.REJECT, "exit_without_user_code"),
        (SetStateStatus.ABORT, "exit_without_user_code"),
    ],
)
def test_startup_action_requires_explicit_accept(
    status: SetStateStatus,
    expected_action: str,
):
    assert pending_claim_startup_action(status) == expected_action


@pytest.mark.parametrize(
    ("scenario", "payload"),
    [
        (
            "first or duplicate exact binding",
            {"status": "accepted"},
        ),
        (
            "stale or mismatched canonical claim",
            {"status": "not_current", "reason": "Claim is no longer current."},
        ),
        (
            "different execution or infrastructure binding",
            {"status": "conflict", "reason": "Claim is already bound."},
        ),
    ],
)
def test_binding_result_contract_distinguishes_outcomes(
    scenario: str,
    payload: dict[str, str],
):
    result = PendingClaimOperationResult.model_validate(
        {**payload, "future_result_hint": scenario}
    )

    assert result.status == payload["status"]
    assert result.model_dump()["future_result_hint"] == scenario


@pytest.mark.parametrize("status", ["not_current", "conflict"])
def test_binding_failures_require_a_reason(status: str):
    with pytest.raises(ValidationError, match="reason"):
        PendingClaimOperationResult.model_validate({"status": status})


def test_pending_claim_teardown_identity_excludes_optional_targeting_fields():
    flow_run_id = uuid4()
    claim_id = uuid7()

    assert pending_claim_teardown_idempotency_key(flow_run_id, claim_id) == (
        f"pending_claim_teardown.v1:{flow_run_id}:{claim_id}"
    )
