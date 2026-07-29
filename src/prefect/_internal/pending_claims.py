from uuid import UUID

from typing_extensions import Literal

PENDING_CLAIM_TEARDOWN: Literal["pending_claim_teardown.v1"] = (
    "pending_claim_teardown.v1"
)


def pending_claim_teardown_idempotency_key(flow_run_id: UUID, claim_id: UUID) -> str:
    """Return the stable cleanup identity for one abandoned pending claim."""

    return f"{PENDING_CLAIM_TEARDOWN}:{flow_run_id}:{claim_id}"


__all__ = [
    "PENDING_CLAIM_TEARDOWN",
    "pending_claim_teardown_idempotency_key",
]
