from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from prefect._internal.uuid7 import uuid7
from prefect.client.schemas.pending_claims import (
    BindExecutionRequest,
    ClaimInfrastructureRequest,
    ExecutionLineage,
    PendingClaim,
    PendingClaimCreate,
    PendingClaimOperationResult,
    PendingClaimReference,
    PendingTimeoutCount,
)


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
def test_initial_claim_request_rejects_server_fields(field: str, value: object):
    with pytest.raises(ValidationError):
        PendingClaimCreate.model_validate(
            {
                "id": uuid7(),
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
def test_running_reference_rejects_server_fields(field: str, value: object):
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
