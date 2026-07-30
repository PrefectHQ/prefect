from dataclasses import dataclass
from typing import Protocol
from uuid import UUID, uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from prefect._internal.uuid7 import uuid7
from prefect.client.schemas.objects import StateType
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


@dataclass(frozen=True)
class CanonicalStateSnapshot:
    """Storage-neutral current orchestration state observed by the contract."""

    state_type: StateType
    details: PendingClaimStateDetails


def _copy_canonical_state(state: CanonicalStateSnapshot) -> CanonicalStateSnapshot:
    return CanonicalStateSnapshot(
        state_type=state.state_type,
        details=state.details.model_copy(deep=True),
    )


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
        canonical_state: CanonicalStateSnapshot,
        mirrored_state: CanonicalStateSnapshot,
        reference: PendingClaimReference,
    ) -> SetStateStatus: ...

    def startup_action(self, status: SetStateStatus) -> str: ...

    def bind_execution(
        self,
        canonical_state: CanonicalStateSnapshot,
        mirrored_state: CanonicalStateSnapshot,
        request: BindExecutionRequest,
    ) -> tuple[PendingClaimOperationResult, CanonicalStateSnapshot]: ...

    def claim_infrastructure(
        self,
        canonical_state: CanonicalStateSnapshot,
        mirrored_state: CanonicalStateSnapshot,
        infrastructure_pid: str | None,
        request: ClaimInfrastructureRequest,
    ) -> tuple[PendingClaimOperationResult, str | None]: ...

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


def _observe_bind_execution(
    adapter: PendingClaimContractAdapter,
    canonical_state: CanonicalStateSnapshot,
    mirrored_state: CanonicalStateSnapshot,
    request: BindExecutionRequest,
) -> tuple[PendingClaimOperationResult, CanonicalStateSnapshot]:
    before_canonical = _copy_canonical_state(canonical_state)
    before_mirror = _copy_canonical_state(mirrored_state)
    before_request = request.model_copy(deep=True)

    result, observed_state = adapter.bind_execution(
        canonical_state,
        mirrored_state,
        request,
    )

    assert canonical_state == before_canonical
    assert mirrored_state == before_mirror
    assert request == before_request
    return result, observed_state


def _observe_infrastructure_claim(
    adapter: PendingClaimContractAdapter,
    canonical_state: CanonicalStateSnapshot,
    mirrored_state: CanonicalStateSnapshot,
    infrastructure_pid: str | None,
    request: ClaimInfrastructureRequest,
) -> tuple[PendingClaimOperationResult, str | None]:
    before_canonical = _copy_canonical_state(canonical_state)
    before_mirror = _copy_canonical_state(mirrored_state)
    before_request = request.model_copy(deep=True)

    result, observed_pid = adapter.claim_infrastructure(
        canonical_state,
        mirrored_state,
        infrastructure_pid,
        request,
    )

    assert canonical_state == before_canonical
    assert mirrored_state == before_mirror
    assert request == before_request
    return result, observed_pid


class ReferencePendingClaimContract:
    """Test-only reference adapter for the shared conformance cases."""

    def startup_disposition(
        self,
        canonical_state: CanonicalStateSnapshot,
        mirrored_state: CanonicalStateSnapshot,
        reference: PendingClaimReference,
    ) -> SetStateStatus:
        if canonical_state.state_type != StateType.PENDING:
            return SetStateStatus.ABORT
        active_claim = canonical_state.details.pending_claim
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
        canonical_state: CanonicalStateSnapshot,
        mirrored_state: CanonicalStateSnapshot,
        request: BindExecutionRequest,
    ) -> tuple[PendingClaimOperationResult, CanonicalStateSnapshot]:
        active_claim = canonical_state.details.pending_claim
        if (
            canonical_state.state_type != StateType.PENDING
            or active_claim is None
            or active_claim.id != request.claim_id
        ):
            return (
                PendingClaimOperationResult(
                    status="not_current",
                    reason="Claim is no longer current.",
                ),
                canonical_state,
            )
        if active_claim.execution_id is None:
            bound_details = canonical_state.details.model_copy(deep=True)
            assert bound_details.pending_claim is not None
            bound_details.pending_claim.execution_id = request.execution_id
            return (
                PendingClaimOperationResult(status="accepted"),
                CanonicalStateSnapshot(
                    state_type=canonical_state.state_type,
                    details=bound_details,
                ),
            )
        if active_claim.execution_id == request.execution_id:
            return PendingClaimOperationResult(status="accepted"), canonical_state
        return (
            PendingClaimOperationResult(
                status="conflict",
                reason="Claim is already bound to another execution.",
            ),
            canonical_state,
        )

    def claim_infrastructure(
        self,
        canonical_state: CanonicalStateSnapshot,
        mirrored_state: CanonicalStateSnapshot,
        infrastructure_pid: str | None,
        request: ClaimInfrastructureRequest,
    ) -> tuple[PendingClaimOperationResult, str | None]:
        active_claim = canonical_state.details.pending_claim
        execution_lineage = canonical_state.details.execution_lineage
        owns_pending = (
            canonical_state.state_type == StateType.PENDING
            and active_claim is not None
            and active_claim.id == request.claim_id
            and active_claim.execution_id == request.execution_id
        )
        owns_running = (
            canonical_state.state_type == StateType.RUNNING
            and active_claim is None
            and execution_lineage is not None
            and execution_lineage.claim_id == request.claim_id
            and execution_lineage.execution_id == request.execution_id
        )
        if not owns_pending and not owns_running:
            return (
                PendingClaimOperationResult(
                    status="not_current",
                    reason="Execution lineage is no longer current.",
                ),
                infrastructure_pid,
            )
        if infrastructure_pid is None:
            return (
                PendingClaimOperationResult(status="accepted"),
                request.infrastructure_pid,
            )
        if infrastructure_pid == request.infrastructure_pid:
            return PendingClaimOperationResult(status="accepted"), infrastructure_pid
        return (
            PendingClaimOperationResult(
                status="conflict",
                reason="Execution lineage is already bound to other infrastructure.",
            ),
            infrastructure_pid,
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
        canonical_state: CanonicalStateSnapshot,
        mirrored_state: CanonicalStateSnapshot,
        reference: PendingClaimReference,
    ) -> SetStateStatus:
        return super().startup_disposition(mirrored_state, canonical_state, reference)


class DropExecutionBindingAdapter(ReferencePendingClaimContract):
    def bind_execution(
        self,
        canonical_state: CanonicalStateSnapshot,
        mirrored_state: CanonicalStateSnapshot,
        request: BindExecutionRequest,
    ) -> tuple[PendingClaimOperationResult, CanonicalStateSnapshot]:
        result, _ = super().bind_execution(
            canonical_state,
            mirrored_state,
            request,
        )
        return result, canonical_state


class DropInfrastructureBindingAdapter(ReferencePendingClaimContract):
    def claim_infrastructure(
        self,
        canonical_state: CanonicalStateSnapshot,
        mirrored_state: CanonicalStateSnapshot,
        infrastructure_pid: str | None,
        request: ClaimInfrastructureRequest,
    ) -> tuple[PendingClaimOperationResult, str | None]:
        result, _ = super().claim_infrastructure(
            canonical_state,
            mirrored_state,
            infrastructure_pid,
            request,
        )
        return result, infrastructure_pid


class MutateBindingInputsAdapter(ReferencePendingClaimContract):
    def bind_execution(
        self,
        canonical_state: CanonicalStateSnapshot,
        mirrored_state: CanonicalStateSnapshot,
        request: BindExecutionRequest,
    ) -> tuple[PendingClaimOperationResult, CanonicalStateSnapshot]:
        result, observed_state = super().bind_execution(
            canonical_state,
            mirrored_state,
            request,
        )
        canonical_state.details.pending_timeout_count = 999
        request.execution_id = uuid7()
        return result, observed_state


class MutateInfrastructureInputsAdapter(ReferencePendingClaimContract):
    def claim_infrastructure(
        self,
        canonical_state: CanonicalStateSnapshot,
        mirrored_state: CanonicalStateSnapshot,
        infrastructure_pid: str | None,
        request: ClaimInfrastructureRequest,
    ) -> tuple[PendingClaimOperationResult, str | None]:
        result, observed_pid = super().claim_infrastructure(
            canonical_state,
            mirrored_state,
            infrastructure_pid,
            request,
        )
        canonical_state.details.pending_timeout_count = 999
        request.infrastructure_pid = "provider/mutated"
        return result, observed_pid


class IgnoreBindingStateTypeAdapter(ReferencePendingClaimContract):
    def bind_execution(
        self,
        canonical_state: CanonicalStateSnapshot,
        mirrored_state: CanonicalStateSnapshot,
        request: BindExecutionRequest,
    ) -> tuple[PendingClaimOperationResult, CanonicalStateSnapshot]:
        return super().bind_execution(
            CanonicalStateSnapshot(
                state_type=StateType.PENDING,
                details=canonical_state.details,
            ),
            mirrored_state,
            request,
        )


class IgnoreInfrastructureStateTypeAdapter(ReferencePendingClaimContract):
    def claim_infrastructure(
        self,
        canonical_state: CanonicalStateSnapshot,
        mirrored_state: CanonicalStateSnapshot,
        infrastructure_pid: str | None,
        request: ClaimInfrastructureRequest,
    ) -> tuple[PendingClaimOperationResult, str | None]:
        if canonical_state.state_type not in (StateType.PENDING, StateType.RUNNING):
            canonical_state = CanonicalStateSnapshot(
                state_type=(
                    StateType.PENDING
                    if canonical_state.details.pending_claim is not None
                    else StateType.RUNNING
                ),
                details=canonical_state.details,
            )
        return super().claim_infrastructure(
            canonical_state,
            mirrored_state,
            infrastructure_pid,
            request,
        )


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
    canonical = CanonicalStateSnapshot(
        state_type=StateType.PENDING,
        details=PendingClaimStateDetails(
            pending_claim=active_claim,
            pending_timeout_count=1,
            future_state_hint={"source": "canonical"},
        ),
    )
    matching_reference = PendingClaimReference(
        claim_id=claim_id,
        execution_id=execution_id,
    )
    empty_pending = CanonicalStateSnapshot(
        state_type=StateType.PENDING,
        details=PendingClaimStateDetails(),
    )

    assert (
        adapter.startup_disposition(
            canonical,
            empty_pending,
            matching_reference,
        )
        == SetStateStatus.ACCEPT
    )

    unbound = CanonicalStateSnapshot(
        state_type=StateType.PENDING,
        details=PendingClaimStateDetails(
            pending_claim=_pending_claim(claim_id=claim_id),
            pending_timeout_count=1,
            future_state_hint={"source": "unbound"},
        ),
    )
    assert (
        adapter.startup_disposition(
            unbound,
            empty_pending,
            matching_reference,
        )
        == SetStateStatus.WAIT
    )

    stale_canonical = CanonicalStateSnapshot(
        state_type=StateType.PENDING,
        details=PendingClaimStateDetails(
            pending_claim=_pending_claim(execution_id=uuid7())
        ),
    )
    matching_mirror = _copy_canonical_state(canonical)
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

    terminal_with_claim = CanonicalStateSnapshot(
        state_type=StateType.COMPLETED,
        details=canonical.details.model_copy(deep=True),
    )
    assert (
        adapter.startup_disposition(
            terminal_with_claim,
            matching_mirror,
            matching_reference,
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
    expected_bound_state = _copy_canonical_state(unbound)
    assert expected_bound_state.details.pending_claim is not None
    expected_bound_state.details.pending_claim.execution_id = execution_id
    first_bind, bound_state = _observe_bind_execution(
        adapter,
        unbound,
        empty_pending,
        unbound_request,
    )
    assert first_bind.status == "accepted"
    assert bound_state == expected_bound_state

    before_duplicate = _copy_canonical_state(bound_state)
    duplicate_bind, duplicate_state = _observe_bind_execution(
        adapter,
        bound_state,
        empty_pending,
        unbound_request,
    )
    assert duplicate_bind.status == "accepted"
    assert duplicate_state == before_duplicate

    conflict_request = BindExecutionRequest(
        claim_id=claim_id,
        execution_id=uuid7(),
    )
    before_conflict = _copy_canonical_state(bound_state)
    conflicting_bind, conflicting_state = _observe_bind_execution(
        adapter,
        bound_state,
        empty_pending,
        conflict_request,
    )
    assert conflicting_bind.status == "conflict"
    assert conflicting_state == before_conflict

    before_stale_bind = _copy_canonical_state(stale_canonical)
    stale_bind, stale_state = _observe_bind_execution(
        adapter,
        stale_canonical,
        matching_mirror,
        unbound_request,
    )
    assert stale_bind.status == "not_current"
    assert stale_state == before_stale_bind

    before_terminal_bind = _copy_canonical_state(terminal_with_claim)
    terminal_bind, terminal_state = _observe_bind_execution(
        adapter,
        terminal_with_claim,
        matching_mirror,
        unbound_request,
    )
    assert terminal_bind.status == "not_current"
    assert terminal_state == before_terminal_bind

    expected_infrastructure_pid = "provider/resource"
    infrastructure_request = ClaimInfrastructureRequest(
        claim_id=claim_id,
        execution_id=execution_id,
        infrastructure_pid=expected_infrastructure_pid,
    )
    pending_infrastructure, pending_binding = _observe_infrastructure_claim(
        adapter,
        canonical,
        stale_canonical,
        None,
        infrastructure_request,
    )
    assert pending_infrastructure.status == "accepted"
    assert pending_binding == expected_infrastructure_pid

    running_state = CanonicalStateSnapshot(
        state_type=StateType.RUNNING,
        details=PendingClaimStateDetails(
            execution_lineage=ExecutionLineage(
                claim_id=claim_id,
                execution_id=execution_id,
            )
        ),
    )
    replacement_pending_state = CanonicalStateSnapshot(
        state_type=StateType.PENDING,
        details=PendingClaimStateDetails(
            pending_claim=_pending_claim(execution_id=uuid7()),
            execution_lineage=running_state.details.execution_lineage,
        ),
    )
    terminal_running_state = CanonicalStateSnapshot(
        state_type=StateType.COMPLETED,
        details=running_state.details.model_copy(deep=True),
    )
    infrastructure_cases = [
        (
            "duplicate exact pending binding",
            canonical,
            stale_canonical,
            pending_binding,
            infrastructure_request,
            "accepted",
            pending_binding,
        ),
        (
            "conflicting infrastructure pid",
            canonical,
            stale_canonical,
            pending_binding,
            ClaimInfrastructureRequest(
                claim_id=claim_id,
                execution_id=execution_id,
                infrastructure_pid="provider/other-resource",
            ),
            "conflict",
            pending_binding,
        ),
        (
            "stale canonical claim with matching mirror",
            stale_canonical,
            matching_mirror,
            pending_binding,
            infrastructure_request,
            "not_current",
            pending_binding,
        ),
        (
            "matching claim with wrong execution",
            canonical,
            empty_pending,
            None,
            ClaimInfrastructureRequest(
                claim_id=claim_id,
                execution_id=uuid7(),
                infrastructure_pid="provider/resource",
            ),
            "not_current",
            None,
        ),
        (
            "late exact running lineage",
            running_state,
            empty_pending,
            None,
            infrastructure_request,
            "accepted",
            expected_infrastructure_pid,
        ),
        (
            "duplicate exact running lineage",
            running_state,
            empty_pending,
            pending_binding,
            infrastructure_request,
            "accepted",
            pending_binding,
        ),
        (
            "conflicting running infrastructure pid",
            running_state,
            empty_pending,
            pending_binding,
            ClaimInfrastructureRequest(
                claim_id=claim_id,
                execution_id=execution_id,
                infrastructure_pid="provider/other-resource",
            ),
            "conflict",
            pending_binding,
        ),
        (
            "running lineage with wrong execution",
            running_state,
            empty_pending,
            pending_binding,
            ClaimInfrastructureRequest(
                claim_id=claim_id,
                execution_id=uuid7(),
                infrastructure_pid="provider/resource",
            ),
            "not_current",
            pending_binding,
        ),
        (
            "replacement pending claim supersedes old running lineage",
            replacement_pending_state,
            running_state,
            None,
            infrastructure_request,
            "not_current",
            None,
        ),
        (
            "terminal state retaining pending claim",
            terminal_with_claim,
            matching_mirror,
            pending_binding,
            infrastructure_request,
            "not_current",
            pending_binding,
        ),
        (
            "terminal state retaining running lineage",
            terminal_running_state,
            running_state,
            pending_binding,
            infrastructure_request,
            "not_current",
            pending_binding,
        ),
    ]
    for (
        scenario,
        canonical_state,
        mirrored_state,
        current_pid,
        request,
        expected_status,
        expected_pid,
    ) in infrastructure_cases:
        result, observed_pid = _observe_infrastructure_claim(
            adapter,
            canonical_state,
            mirrored_state,
            current_pid,
            request,
        )
        assert (result.status, observed_pid) == (
            expected_status,
            expected_pid,
        ), scenario

    source_state_id = uuid4()
    target_state_id = uuid4()
    assert source_state_id != target_state_id
    named_substate = adapter.preserve_pending_substate(
        canonical.details,
        source_state_id,
        target_state_id,
    )
    assert named_substate.pending_claim == canonical.details.pending_claim
    assert (
        named_substate.pending_timeout_count == canonical.details.pending_timeout_count
    )
    assert named_substate.model_dump()["future_state_hint"] == {"source": "canonical"}

    replacement_claim = _pending_claim()
    expired, replacement = adapter.expire_and_replace(
        canonical.details,
        replacement_claim,
    )
    assert expired.pending_claim is None
    assert expired.pending_timeout_count == 2
    assert replacement.pending_claim == replacement_claim
    assert replacement.pending_claim.id != active_claim.id
    assert replacement.pending_timeout_count == expired.pending_timeout_count

    accepted_running = adapter.accept_running(canonical.details, matching_reference)
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
        pytest.param(DropExecutionBindingAdapter(), id="binding-not-persisted"),
        pytest.param(
            DropInfrastructureBindingAdapter(),
            id="infrastructure-not-persisted",
        ),
        pytest.param(MutateBindingInputsAdapter(), id="binding-mutates-inputs"),
        pytest.param(
            MutateInfrastructureInputsAdapter(),
            id="infrastructure-mutates-inputs",
        ),
        pytest.param(
            IgnoreBindingStateTypeAdapter(),
            id="binding-ignores-state-type",
        ),
        pytest.param(
            IgnoreInfrastructureStateTypeAdapter(),
            id="infrastructure-ignores-state-type",
        ),
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
