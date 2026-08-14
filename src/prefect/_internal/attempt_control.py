"""Shared types and wire framing for the internal Attempt Control Session."""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from enum import Enum
from typing import Literal, TypeAlias
from uuid import UUID

Intent = Literal["cancel", "reschedule", "relinquish"]

BYTE_FOR_INTENT: dict[Intent, bytes] = {
    "cancel": b"c",
    "reschedule": b"r",
    "relinquish": b"q",
}
INTENT_FOR_BYTE: dict[bytes, Intent] = {
    value: key for key, value in BYTE_FOR_INTENT.items()
}

LEGACY_PROTOCOL_VERSION = 1
CURRENT_PROTOCOL_VERSION = 2
RECEIPT_CAPABILITY = 1 << 0

# The child-initiated hello deliberately contains no legacy acknowledgement byte
# (`b"a"`), so a version-one supervisor can safely ignore it.
NEGOTIATION_PREFIX = b"\x00PF"
NEGOTIATION_FRAME_SIZE = len(NEGOTIATION_PREFIX) + 2
RECEIPT_PREFIX = b"\x01"
RECEIPT_ACK = b"\x02"
MAX_RECEIPT_SIZE = 4096


class EngineDisposition(str, Enum):
    STATE_REPORTED = "STATE_REPORTED"
    ORCHESTRATION_ABORTED = "ORCHESTRATION_ABORTED"


@dataclass(frozen=True)
class EngineOutcomeReceipt:
    """Sanitized evidence that an engine concluded an execution attempt."""

    disposition: EngineDisposition
    state_id: UUID | None = None
    state_type: str | None = None
    state_name: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.disposition, EngineDisposition):
            raise TypeError("Receipt disposition must be an EngineDisposition")
        state_fields = (self.state_id, self.state_type, self.state_name)
        if self.disposition is EngineDisposition.STATE_REPORTED:
            if any(value is None for value in state_fields):
                raise ValueError("STATE_REPORTED receipts require all state fields")
            if not isinstance(self.state_id, UUID):
                raise TypeError("Receipt state ID must be a UUID")
            if not isinstance(self.state_type, str) or not isinstance(
                self.state_name, str
            ):
                raise TypeError("Receipt state type and name must be strings")
            if not self.state_type:
                raise ValueError("Receipt state type must not be empty")
            if len(self.state_type) > 64:
                raise ValueError("Receipt state type is too long")
        elif any(value is not None for value in state_fields):
            raise ValueError(
                "ORCHESTRATION_ABORTED receipts cannot include state fields"
            )

    @classmethod
    def state_reported(
        cls, *, state_id: UUID, state_type: str, state_name: str
    ) -> EngineOutcomeReceipt:
        return cls(
            disposition=EngineDisposition.STATE_REPORTED,
            state_id=state_id,
            state_type=state_type,
            state_name=state_name,
        )

    @classmethod
    def orchestration_aborted(cls) -> EngineOutcomeReceipt:
        return cls(disposition=EngineDisposition.ORCHESTRATION_ABORTED)


@dataclass(frozen=True)
class StateOwnershipDelegation:
    """Evidence that the supervisor's acknowledged control intent won."""

    intent: Intent


AttemptConclusion: TypeAlias = EngineOutcomeReceipt | StateOwnershipDelegation


def encode_negotiation(version: int, capabilities: int) -> bytes:
    if not 0 <= version <= 255 or not 0 <= capabilities <= 255:
        raise ValueError("Protocol version and capabilities must fit in one byte")
    return NEGOTIATION_PREFIX + bytes((version, capabilities))


def decode_negotiation(frame: bytes) -> tuple[int, int]:
    if len(frame) != NEGOTIATION_FRAME_SIZE or not frame.startswith(NEGOTIATION_PREFIX):
        raise ValueError("Malformed Attempt Control Session negotiation")
    return frame[-2], frame[-1]


def encode_receipt(receipt: EngineOutcomeReceipt) -> bytes:
    payload: dict[str, str] = {"disposition": receipt.disposition.value}
    if receipt.disposition is EngineDisposition.STATE_REPORTED:
        assert receipt.state_id is not None
        assert receipt.state_type is not None
        assert receipt.state_name is not None
        payload.update(
            {
                "state_id": str(receipt.state_id),
                "state_type": receipt.state_type,
                "state_name": receipt.state_name,
            }
        )
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    if len(encoded) > MAX_RECEIPT_SIZE:
        raise ValueError("Receipt payload is too large")
    return RECEIPT_PREFIX + struct.pack("!I", len(encoded)) + encoded


def decode_receipt(payload: bytes) -> EngineOutcomeReceipt:
    if len(payload) > MAX_RECEIPT_SIZE:
        raise ValueError("Receipt payload is too large")
    try:
        decoded = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Malformed receipt payload") from exc
    if not isinstance(decoded, dict):
        raise TypeError("Receipt payload must be an object")

    try:
        disposition = EngineDisposition(decoded["disposition"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Receipt disposition is invalid") from exc

    if disposition is EngineDisposition.ORCHESTRATION_ABORTED:
        if set(decoded) != {"disposition"}:
            raise ValueError("Aborted receipt contains unexpected fields")
        return EngineOutcomeReceipt.orchestration_aborted()

    if set(decoded) != {"disposition", "state_id", "state_type", "state_name"}:
        raise ValueError("State receipt fields are invalid")
    try:
        return EngineOutcomeReceipt.state_reported(
            state_id=UUID(decoded["state_id"]),
            state_type=decoded["state_type"],
            state_name=decoded["state_name"],
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("State receipt fields are invalid") from exc
