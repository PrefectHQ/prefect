"""
Telemetry state management in PREFECT_HOME.

This module manages persistent telemetry state like whether the user
has been prompted and their session ID.
"""

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

import toml

from prefect.logging import get_logger
from prefect.settings.constants import DEFAULT_PREFECT_HOME

logger = get_logger(__name__)


class TelemetryState:
    """Manages telemetry state in ~/.prefect/telemetry_state.toml"""

    def __init__(self, home_path: Optional[Path] = None):
        """Initialize telemetry state manager.

        Args:
            home_path: Path to PREFECT_HOME directory. Defaults to ~/.prefect
        """
        self.home_path = home_path or self._get_prefect_home()
        self.state_file = self.home_path / "telemetry_state.toml"
        self._state: Optional[Dict[str, Any]] = None

    def _get_prefect_home(self) -> Path:
        """Get the PREFECT_HOME directory path."""
        if prefect_home := os.environ.get("PREFECT_HOME"):
            return Path(prefect_home)
        return DEFAULT_PREFECT_HOME

    def _ensure_home_exists(self) -> None:
        """Ensure PREFECT_HOME directory exists."""
        self.home_path.mkdir(parents=True, exist_ok=True)

    def _load_state(self) -> Dict[str, Any]:
        """Load state from file or return default state."""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r") as f:
                    return toml.load(f)
            except Exception as e:
                logger.debug(f"Failed to load telemetry state: {e}")

        # Return default state
        return {
            "telemetry": {
                "prompted": False,
                "session_id": str(uuid4()),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        }

    def _save_state(self) -> None:
        """Save current state to file."""
        if self._state is None:
            return

        try:
            self._ensure_home_exists()
            with open(self.state_file, "w") as f:
                toml.dump(self._state, f)
        except Exception as e:
            logger.debug(f"Failed to save telemetry state: {e}")

    @property
    def state(self) -> Dict[str, Any]:
        """Get current state, loading if necessary."""
        if self._state is None:
            self._state = self._load_state()
        return self._state

    @property
    def prompted(self) -> bool:
        """Check if user has been prompted about telemetry."""
        return self.state.get("telemetry", {}).get("prompted", False)

    @prompted.setter
    def prompted(self, value: bool) -> None:
        """Set whether user has been prompted."""
        if "telemetry" not in self.state:
            self.state["telemetry"] = {}
        self.state["telemetry"]["prompted"] = value
        self.state["telemetry"]["prompt_date"] = datetime.now(timezone.utc).isoformat()
        self._save_state()

    @property
    def session_id(self) -> str:
        """Get or generate session ID."""
        session_id = self.state.get("telemetry", {}).get("session_id")
        if not session_id:
            session_id = str(uuid4())
            if "telemetry" not in self.state:
                self.state["telemetry"] = {}
            self.state["telemetry"]["session_id"] = session_id
            self._save_state()
        return session_id

    def record_decision(self, enabled: bool) -> None:
        """Record the user's telemetry decision.

        Args:
            enabled: Whether user enabled telemetry
        """
        if "telemetry" not in self.state:
            self.state["telemetry"] = {}
        self.state["telemetry"]["decision"] = enabled
        self.state["telemetry"]["decision_date"] = datetime.now(
            timezone.utc
        ).isoformat()
        self._save_state()

    def reset(self) -> None:
        """Reset telemetry state (useful for testing)."""
        self._state = None
        if self.state_file.exists():
            try:
                self.state_file.unlink()
            except Exception as e:
                logger.debug(f"Failed to delete telemetry state file: {e}")
