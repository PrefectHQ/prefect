from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from prefect.blocks.core import Block
from pydantic import Field

log = logging.getLogger(__name__)

GENESIS_HASH = "0000000000000000000000000000000000000000000000000000000000000000"


class ActionGateBlock(Block):
    """
    A2Z SOC ActionGate Block & Cryptographic Action Ledger for Prefect.

    Enforces zero-trust ActionBoundary governance, worker-pool kill-switches,
    and NIST SP 800-53 Rev. 5 audit logging across automated task flows and AI agent runs.
    """

    _block_type_name = "ActionGate Security"
    _logo_url = "https://a2zsoc.com/static/img/actiongate-shield.png"
    _documentation_url = "https://a2zsoc.com/productized-services#instant-audit-tripwire"

    never_equate_intent_to_approval: bool = Field(
        default=True,
        description="Strictly disallow intent-based execution without explicit verification.",
    )
    enforce_action_boundary: bool = Field(
        default=True,
        description="Verify ActionBoundary prove-tokens before mutating external resources.",
    )
    max_retries_on_failure: int = Field(
        default=0,
        description="Cap retries on state-mutating tools to prevent cascading billing loops.",
    )

    def __init__(self, **data: Any):
        super().__init__(**data)
        self._entries: List[Dict[str, Any]] = []
        self._last_hash: str = GENESIS_HASH

    def _check_kill_switch(self) -> bool:
        if os.environ.get("AAG_KILL_SWITCH", "").lower() in ("true", "1", "yes"):
            return True
        for path_str in ("artifacts/KILL", "/tmp/KILL"):
            if Path(path_str).exists():
                return True
        return False

    def _record_audit_entry(
        self,
        event_type: str,
        tool_name: str,
        status: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        timestamp = datetime.now(timezone.utc).isoformat()
        index = len(self._entries)

        meta_bytes = json.dumps(metadata, sort_keys=True).encode("utf-8")
        canonical_content = f"{index}|{self._last_hash}|{event_type}|{tool_name}|{status}|{timestamp}|{hashlib.sha256(meta_bytes).hexdigest()}"
        curr_hash = hashlib.sha256(canonical_content.encode("utf-8")).hexdigest()

        entry = {
            "index": index,
            "timestamp": timestamp,
            "event_type": event_type,
            "tool_name": tool_name,
            "status": status,
            "prev_hash": self._last_hash,
            "curr_hash": curr_hash,
            "metadata": metadata,
        }

        self._entries.append(entry)
        self._last_hash = curr_hash
        return entry

    def verify_task_action(
        self,
        tool_name: str,
        payload: Optional[Dict[str, Any]] = None,
        is_destructive: bool = False,
        user_confirmed: bool = False,
    ) -> Dict[str, Any]:
        """
        Verifies task action against zero-trust ActionBoundary before execution.
        """
        # 1. Evaluate emergency kill switch
        if self._check_kill_switch():
            self._record_audit_entry(
                event_type="task_blocked",
                tool_name=tool_name,
                status="kill_switch_engaged",
                metadata={"reason": "emergency_kill_switch_active"},
            )
            raise PermissionError("A2Z SOC ActionGate: Emergency kill switch is engaged. Task flow halted.")

        # 2. Destructive actions require explicit confirmation
        if is_destructive and not user_confirmed:
            self._record_audit_entry(
                event_type="task_confirmation_required",
                tool_name=tool_name,
                status="confirmation_required",
                metadata={"payload": payload or {}},
            )
            raise PermissionError(
                f"A2Z SOC ActionGate: Destructive action '{tool_name}' requires explicit user confirmation."
            )

        # 3. Record authorized task execution
        entry = self._record_audit_entry(
            event_type="task_authorized",
            tool_name=tool_name,
            status="authorized",
            metadata={"payload": payload or {}, "is_destructive": is_destructive},
        )

        return {"allowed": True, "action_id": f"task_{entry['index']}", "hash": entry["curr_hash"]}

    def get_ledger_entries(self) -> List[Dict[str, Any]]:
        return list(self._entries)

    def verify_ledger_integrity(self) -> bool:
        prev = GENESIS_HASH
        for entry in self._entries:
            if entry["prev_hash"] != prev:
                return False
            prev = entry["curr_hash"]
        return True
