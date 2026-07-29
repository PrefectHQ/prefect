"""
Shared pending-claim protocol contract.

Request models in this module are strict because clients may only author fields
owned by that operation. Persisted metadata models allow unknown fields so old
readers can preserve future protocol extensions during rolling deployments.
"""

from typing import ClassVar
from uuid import UUID

from pydantic import UUID7, ConfigDict, Field
from typing_extensions import Literal, TypeAlias

from prefect._internal.schemas.bases import PrefectBaseModel
from prefect.types import NonNegativeInteger, PositiveInteger

PENDING_CLAIM_TEARDOWN: Literal["pending_claim_teardown.v1"] = (
    "pending_claim_teardown.v1"
)

PendingTimeoutCount: TypeAlias = NonNegativeInteger


class PendingClaim(PrefectBaseModel):
    """Server-resolved ownership metadata for an active pending attempt."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow")

    id: UUID7
    execution_id: UUID7 | None = None
    timeout_seconds: PositiveInteger
    max_timeouts: PositiveInteger


class ExecutionLineage(PrefectBaseModel):
    """Server-authored lineage for an accepted claim-aware execution."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow")

    claim_id: UUID7
    execution_id: UUID7


class _StrictPendingClaimRequest(PrefectBaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")


class PendingClaimCreate(_StrictPendingClaimRequest):
    """Client-authored metadata for an initial claim-bearing PENDING proposal."""

    id: UUID7


class _PendingClaimExecutionRequest(_StrictPendingClaimRequest):
    claim_id: UUID7
    execution_id: UUID7


class PendingClaimReference(_PendingClaimExecutionRequest):
    """Request-only claim reference presented by a RUNNING proposal."""


class BindExecutionRequest(_PendingClaimExecutionRequest):
    """Bind one intended execution to the active pending claim."""


class ClaimInfrastructureRequest(_PendingClaimExecutionRequest):
    """Bind a provider infrastructure handle to a claim and execution."""

    infrastructure_pid: str = Field(min_length=1)


class PendingClaimContract(PrefectBaseModel):
    """Machine-readable cross-system pending-claim behavior."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    pending_state_field: Literal["pending_claim"]
    running_proposal_field: Literal["pending_claim"]
    accepted_lineage_field: Literal["execution_lineage"]
    timeout_count_field: Literal["pending_timeout_count"]
    ownership_authority: Literal["canonical_current_orchestration_state"]
    timeout_count_authority: Literal["canonical_current_orchestration_state"]
    ownership_serialization: Literal["owning_state_transition_per_flow_run"]
    serialized_ownership_mutations: tuple[
        Literal["binding", "ownership_transfer", "forced_exit", "expiry"], ...
    ]
    pending_substate_identity: Literal["claim_id_not_state_record_id"]
    pending_substate_behavior: Literal["preserve_pending_claim_and_timeout_count"]
    replacement_claim_behavior: Literal["preserve_timeout_count"]
    valid_expiry_behavior: Literal["atomically_increment_timeout_count"]
    accepted_running_behavior: Literal[
        "clear_pending_claim_and_timeout_count_write_execution_lineage"
    ]
    initial_claim_client_fields: tuple[Literal["id"], ...]
    initial_claim_server_managed_fields: tuple[
        Literal[
            "execution_id",
            "timeout_seconds",
            "max_timeouts",
            "pending_timeout_count",
        ],
        ...,
    ]
    matching_bound_startup_outcome: Literal["ACCEPT"]
    unbound_execution_startup_outcome: Literal["WAIT"]
    stale_or_mismatched_startup_outcome: Literal["ABORT"]
    accept_action: Literal["start_user_code"]
    wait_action: Literal["retry"]
    reject_action: Literal["exit_without_user_code"]
    abort_action: Literal["exit_without_user_code"]
    teardown_delivery: Literal["at_least_once"]
    teardown_semantic_idempotency: Literal["claim_id"]
    cloud_authorization_internals: Literal["excluded_from_shared_contract"]


PENDING_CLAIM_CONTRACT = PendingClaimContract(
    pending_state_field="pending_claim",
    running_proposal_field="pending_claim",
    accepted_lineage_field="execution_lineage",
    timeout_count_field="pending_timeout_count",
    ownership_authority="canonical_current_orchestration_state",
    timeout_count_authority="canonical_current_orchestration_state",
    ownership_serialization="owning_state_transition_per_flow_run",
    serialized_ownership_mutations=(
        "binding",
        "ownership_transfer",
        "forced_exit",
        "expiry",
    ),
    pending_substate_identity="claim_id_not_state_record_id",
    pending_substate_behavior="preserve_pending_claim_and_timeout_count",
    replacement_claim_behavior="preserve_timeout_count",
    valid_expiry_behavior="atomically_increment_timeout_count",
    accepted_running_behavior=(
        "clear_pending_claim_and_timeout_count_write_execution_lineage"
    ),
    initial_claim_client_fields=("id",),
    initial_claim_server_managed_fields=(
        "execution_id",
        "timeout_seconds",
        "max_timeouts",
        "pending_timeout_count",
    ),
    matching_bound_startup_outcome="ACCEPT",
    unbound_execution_startup_outcome="WAIT",
    stale_or_mismatched_startup_outcome="ABORT",
    accept_action="start_user_code",
    wait_action="retry",
    reject_action="exit_without_user_code",
    abort_action="exit_without_user_code",
    teardown_delivery="at_least_once",
    teardown_semantic_idempotency="claim_id",
    cloud_authorization_internals="excluded_from_shared_contract",
)


def pending_claim_teardown_idempotency_key(flow_run_id: UUID, claim_id: UUID) -> str:
    """Return the stable cleanup identity for one abandoned pending claim."""

    return f"{PENDING_CLAIM_TEARDOWN}:{flow_run_id}:{claim_id}"


__all__ = [
    "PENDING_CLAIM_CONTRACT",
    "PENDING_CLAIM_TEARDOWN",
    "BindExecutionRequest",
    "ClaimInfrastructureRequest",
    "ExecutionLineage",
    "PendingClaim",
    "PendingClaimContract",
    "PendingClaimCreate",
    "PendingClaimReference",
    "PendingTimeoutCount",
    "pending_claim_teardown_idempotency_key",
]
