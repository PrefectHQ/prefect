from typing import Protocol
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


class PendingClaimContractAdapter(Protocol):
    def startup_disposition(
        self,
        canonical_state: PendingClaimStateDetails,
        mirrored_state: PendingClaimStateDetails,
        reference: PendingClaimReference,
    ) -> SetStateStatus: ...

    def startup_action(self, status: SetStateStatus) -> str: ...

    def bind_execution(
        self,
        canonical_state: PendingClaimStateDetails,
        mirrored_state: PendingClaimStateDetails,
        request: BindExecutionRequest,
    ) -> PendingClaimOperationResult: ...

    def preserve_pending_substate(
        self,
        canonical_state: PendingClaimStateDetails,
        source_state_id: UUID,
        target_state_id: UUID,
    ) -> PendingClaimStateDetails: ...

    def expire_and_replace(
        self,
        canonical_state: PendingClaimStateDetails,
        replacement_claim: PendingClaim,
    ) -> tuple[PendingClaimStateDetails, PendingClaimStateDetails]: ...

    def accept_running(
        self,
        canonical_state: PendingClaimStateDetails,
        reference: PendingClaimReference,
    ) -> PendingClaimStateDetails: ...


class ReferencePendingClaimContract:
    """Test-only reference adapter for the shared conformance cases."""

    def startup_disposition(
        self,
        canonical_state: PendingClaimStateDetails,
        mirrored_state: PendingClaimStateDetails,
        reference: PendingClaimReference,
    ) -> SetStateStatus:
        active_claim = canonical_state.pending_claim
        if (
            active_claim is None
            or active_claim.id != reference.claim_id
            or (
                active_claim.execution_id is not None
                and active_claim.execution_id != reference.execution_id
            )
        ):
            return SetStateStatus.ABORT
        if active_claim.execution_id is None:
            return SetStateStatus.WAIT
        return SetStateStatus.ACCEPT

    def startup_action(self, status: SetStateStatus) -> str:
        if status == SetStateStatus.ACCEPT:
            return "start_user_code"
        if status == SetStateStatus.WAIT:
            return "retry"
        return "exit_without_user_code"

    def bind_execution(
        self,
        canonical_state: PendingClaimStateDetails,
        mirrored_state: PendingClaimStateDetails,
        request: BindExecutionRequest,
    ) -> PendingClaimOperationResult:
        active_claim = canonical_state.pending_claim
        if active_claim is None or active_claim.id != request.claim_id:
            return PendingClaimOperationResult(
                status="not_current",
                reason="Claim is no longer current.",
            )
        if active_claim.execution_id in (None, request.execution_id):
            return PendingClaimOperationResult(status="accepted")
        return PendingClaimOperationResult(
            status="conflict",
            reason="Claim is already bound to another execution.",
        )

    def preserve_pending_substate(
        self,
        canonical_state: PendingClaimStateDetails,
        source_state_id: UUID,
        target_state_id: UUID,
    ) -> PendingClaimStateDetails:
        return canonical_state.model_copy(deep=True)

    def expire_and_replace(
        self,
        canonical_state: PendingClaimStateDetails,
        replacement_claim: PendingClaim,
    ) -> tuple[PendingClaimStateDetails, PendingClaimStateDetails]:
        timeout_count = canonical_state.pending_timeout_count or 0
        expired = PendingClaimStateDetails(
            pending_timeout_count=timeout_count + 1,
        )
        replacement = PendingClaimStateDetails(
            pending_claim=replacement_claim,
            pending_timeout_count=expired.pending_timeout_count,
        )
        return expired, replacement

    def accept_running(
        self,
        canonical_state: PendingClaimStateDetails,
        reference: PendingClaimReference,
    ) -> PendingClaimStateDetails:
        return PendingClaimStateDetails(
            execution_lineage=ExecutionLineage(
                claim_id=reference.claim_id,
                execution_id=reference.execution_id,
            )
        )


class MirrorAuthorityAdapter(ReferencePendingClaimContract):
    def startup_disposition(
        self,
        canonical_state: PendingClaimStateDetails,
        mirrored_state: PendingClaimStateDetails,
        reference: PendingClaimReference,
    ) -> SetStateStatus:
        return super().startup_disposition(mirrored_state, canonical_state, reference)


class StateRecordIdentityAdapter(ReferencePendingClaimContract):
    def preserve_pending_substate(
        self,
        canonical_state: PendingClaimStateDetails,
        source_state_id: UUID,
        target_state_id: UUID,
    ) -> PendingClaimStateDetails:
        if source_state_id != target_state_id:
            return PendingClaimStateDetails()
        return canonical_state


class ResetTimeoutCountAdapter(ReferencePendingClaimContract):
    def expire_and_replace(
        self,
        canonical_state: PendingClaimStateDetails,
        replacement_claim: PendingClaim,
    ) -> tuple[PendingClaimStateDetails, PendingClaimStateDetails]:
        expired, replacement = super().expire_and_replace(
            canonical_state, replacement_claim
        )
        replacement.pending_timeout_count = 0
        return expired, replacement


class DoubleIncrementAdapter(ReferencePendingClaimContract):
    def expire_and_replace(
        self,
        canonical_state: PendingClaimStateDetails,
        replacement_claim: PendingClaim,
    ) -> tuple[PendingClaimStateDetails, PendingClaimStateDetails]:
        expired, replacement = super().expire_and_replace(
            canonical_state, replacement_claim
        )
        assert expired.pending_timeout_count is not None
        expired.pending_timeout_count += 1
        return expired, replacement


class RetainClaimOnRunningAdapter(ReferencePendingClaimContract):
    def accept_running(
        self,
        canonical_state: PendingClaimStateDetails,
        reference: PendingClaimReference,
    ) -> PendingClaimStateDetails:
        accepted = super().accept_running(canonical_state, reference)
        accepted.pending_claim = canonical_state.pending_claim
        accepted.pending_timeout_count = canonical_state.pending_timeout_count
        return accepted


class StartOnRejectAdapter(ReferencePendingClaimContract):
    def startup_action(self, status: SetStateStatus) -> str:
        if status == SetStateStatus.REJECT:
            return "start_user_code"
        return super().startup_action(status)


def _assert_pending_claim_contract(adapter: PendingClaimContractAdapter) -> None:
    claim_id = uuid7()
    execution_id = uuid7()
    active_claim = _pending_claim(
        claim_id=claim_id,
        execution_id=execution_id,
    )
    canonical = PendingClaimStateDetails(
        pending_claim=active_claim,
        pending_timeout_count=1,
        future_state_hint={"source": "canonical"},
    )
    matching_reference = PendingClaimReference(
        claim_id=claim_id,
        execution_id=execution_id,
    )

    assert (
        adapter.startup_disposition(
            canonical,
            PendingClaimStateDetails(),
            matching_reference,
        )
        == SetStateStatus.ACCEPT
    )

    unbound = PendingClaimStateDetails(pending_claim=_pending_claim(claim_id=claim_id))
    assert (
        adapter.startup_disposition(
            unbound,
            PendingClaimStateDetails(),
            matching_reference,
        )
        == SetStateStatus.WAIT
    )

    stale_canonical = PendingClaimStateDetails(
        pending_claim=_pending_claim(execution_id=uuid7())
    )
    matching_mirror = canonical.model_copy(deep=True)
    assert (
        adapter.startup_disposition(
            stale_canonical,
            matching_mirror,
            matching_reference,
        )
        == SetStateStatus.ABORT
    )

    wrong_execution = PendingClaimReference(
        claim_id=claim_id,
        execution_id=uuid7(),
    )
    assert (
        adapter.startup_disposition(
            canonical,
            matching_mirror,
            wrong_execution,
        )
        == SetStateStatus.ABORT
    )

    expected_actions = {
        SetStateStatus.ACCEPT: "start_user_code",
        SetStateStatus.WAIT: "retry",
        SetStateStatus.REJECT: "exit_without_user_code",
        SetStateStatus.ABORT: "exit_without_user_code",
    }
    assert {
        status: adapter.startup_action(status) for status in SetStateStatus
    } == expected_actions

    unbound_request = BindExecutionRequest(
        claim_id=claim_id,
        execution_id=execution_id,
    )
    assert (
        adapter.bind_execution(
            unbound,
            PendingClaimStateDetails(),
            unbound_request,
        ).status
        == "accepted"
    )
    assert (
        adapter.bind_execution(
            canonical,
            PendingClaimStateDetails(),
            unbound_request,
        ).status
        == "accepted"
    )
    assert (
        adapter.bind_execution(
            canonical,
            PendingClaimStateDetails(),
            BindExecutionRequest(
                claim_id=claim_id,
                execution_id=uuid7(),
            ),
        ).status
        == "conflict"
    )
    assert (
        adapter.bind_execution(
            stale_canonical,
            matching_mirror,
            unbound_request,
        ).status
        == "not_current"
    )

    source_state_id = uuid4()
    target_state_id = uuid4()
    assert source_state_id != target_state_id
    named_substate = adapter.preserve_pending_substate(
        canonical,
        source_state_id,
        target_state_id,
    )
    assert named_substate.pending_claim == canonical.pending_claim
    assert named_substate.pending_timeout_count == canonical.pending_timeout_count
    assert named_substate.model_dump()["future_state_hint"] == {"source": "canonical"}

    replacement_claim = _pending_claim()
    expired, replacement = adapter.expire_and_replace(
        canonical,
        replacement_claim,
    )
    assert expired.pending_claim is None
    assert expired.pending_timeout_count == 2
    assert replacement.pending_claim == replacement_claim
    assert replacement.pending_claim.id != active_claim.id
    assert replacement.pending_timeout_count == expired.pending_timeout_count

    accepted_running = adapter.accept_running(canonical, matching_reference)
    assert accepted_running.pending_claim is None
    assert accepted_running.pending_timeout_count is None
    assert accepted_running.execution_lineage == ExecutionLineage(
        claim_id=claim_id,
        execution_id=execution_id,
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


def test_reference_adapter_satisfies_pending_claim_contract():
    _assert_pending_claim_contract(ReferencePendingClaimContract())


@pytest.mark.parametrize(
    "adapter",
    [
        pytest.param(MirrorAuthorityAdapter(), id="non-canonical-authority"),
        pytest.param(StateRecordIdentityAdapter(), id="state-record-identity"),
        pytest.param(ResetTimeoutCountAdapter(), id="replacement-resets-count"),
        pytest.param(DoubleIncrementAdapter(), id="expiry-not-atomic"),
        pytest.param(RetainClaimOnRunningAdapter(), id="running-retains-claim"),
        pytest.param(StartOnRejectAdapter(), id="reject-starts-user-code"),
    ],
)
def test_contract_cases_reject_incorrect_implementations(
    adapter: PendingClaimContractAdapter,
):
    with pytest.raises(AssertionError):
        _assert_pending_claim_contract(adapter)


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
