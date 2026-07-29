"""
Shared pending-claim protocol contract.

Request models in this module are strict because clients may only author fields
owned by that operation. Persisted metadata models allow unknown fields so old
readers can preserve future protocol extensions during rolling deployments.

The claim fields on canonical current orchestration state are authoritative.
Binding, ownership transfer, forced exit, and expiry must serialize through the
owning state-transition module's per-flow-run mechanism.
"""

from typing import ClassVar
from uuid import UUID

from pydantic import UUID7, ConfigDict, Field, model_validator
from typing_extensions import Literal, TypeAlias

from prefect._internal.schemas.bases import PrefectBaseModel
from prefect.client.schemas.responses import SetStateStatus
from prefect.types import NonNegativeInteger, PositiveInteger

PENDING_CLAIM_TEARDOWN: Literal["pending_claim_teardown.v1"] = (
    "pending_claim_teardown.v1"
)

PendingTimeoutCount: TypeAlias = NonNegativeInteger
PendingClaimOperationStatus: TypeAlias = Literal["accepted", "not_current", "conflict"]
PendingClaimStartupAction: TypeAlias = Literal[
    "start_user_code", "retry", "exit_without_user_code"
]


class PendingClaim(PrefectBaseModel):
    """Server-resolved ownership metadata for an active pending attempt."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow")

    id: UUID
    execution_id: UUID | None = None
    timeout_seconds: PositiveInteger
    max_timeouts: PositiveInteger


class ExecutionLineage(PrefectBaseModel):
    """Server-authored lineage for an accepted claim-aware execution."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow")

    claim_id: UUID
    execution_id: UUID


class PendingClaimStateDetails(PrefectBaseModel):
    """
    Claim-owned projection of canonical orchestration state details.

    `pending_timeout_count` belongs to the contiguous startup-recovery sequence,
    not to one claim, so replacement claims inherit it. Accepted RUNNING state
    clears the active fields and retains only `execution_lineage`.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow")

    pending_claim: PendingClaim | None = None
    pending_timeout_count: PendingTimeoutCount | None = None
    execution_lineage: ExecutionLineage | None = None


class _StrictPendingClaimRequest(PrefectBaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")


class PendingClaimCreate(_StrictPendingClaimRequest):
    """Client-authored metadata for an initial claim-bearing PENDING proposal."""

    id: UUID7


class PendingClaimCreateFields(_StrictPendingClaimRequest):
    """Client-writable state-details fragment for an initial pending claim."""

    pending_claim: PendingClaimCreate


class _PendingClaimExecutionRequest(_StrictPendingClaimRequest):
    claim_id: UUID7
    execution_id: UUID7


class PendingClaimReference(_PendingClaimExecutionRequest):
    """Request-only claim reference presented by a RUNNING proposal."""


class PendingClaimRunningFields(_StrictPendingClaimRequest):
    """Client-writable state-details fragment for claim-aware startup."""

    pending_claim: PendingClaimReference


class BindExecutionRequest(_PendingClaimExecutionRequest):
    """Bind one intended execution to the active pending claim."""


class ClaimInfrastructureRequest(_PendingClaimExecutionRequest):
    """Bind a provider infrastructure handle to a claim and execution."""

    infrastructure_pid: str = Field(min_length=1)


class PendingClaimOperationResult(PrefectBaseModel):
    """Forward-compatible result for claim-scoped binding operations."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow")

    status: PendingClaimOperationStatus
    reason: str | None = None

    @model_validator(mode="after")
    def require_failure_reason(self) -> "PendingClaimOperationResult":
        if self.status != "accepted" and not self.reason:
            raise ValueError(
                "`reason` is required for non-accepted pending-claim operations"
            )
        return self


def pending_claim_startup_disposition(
    canonical_state: PendingClaimStateDetails,
    reference: PendingClaimReference,
) -> SetStateStatus:
    """Classify claim-aware startup against canonical current state metadata."""

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


def pending_claim_startup_action(
    status: SetStateStatus,
) -> PendingClaimStartupAction:
    """Return the only permitted runtime action for an orchestration outcome."""

    if status == SetStateStatus.ACCEPT:
        return "start_user_code"
    if status == SetStateStatus.WAIT:
        return "retry"
    return "exit_without_user_code"


def pending_claim_teardown_idempotency_key(flow_run_id: UUID, claim_id: UUID) -> str:
    """Return the stable cleanup identity for one abandoned pending claim."""

    return f"{PENDING_CLAIM_TEARDOWN}:{flow_run_id}:{claim_id}"


__all__ = [
    "PENDING_CLAIM_TEARDOWN",
    "BindExecutionRequest",
    "ClaimInfrastructureRequest",
    "ExecutionLineage",
    "PendingClaim",
    "PendingClaimCreate",
    "PendingClaimCreateFields",
    "PendingClaimOperationResult",
    "PendingClaimOperationStatus",
    "PendingClaimReference",
    "PendingClaimRunningFields",
    "PendingClaimStartupAction",
    "PendingClaimStateDetails",
    "PendingTimeoutCount",
    "pending_claim_startup_action",
    "pending_claim_startup_disposition",
    "pending_claim_teardown_idempotency_key",
]
