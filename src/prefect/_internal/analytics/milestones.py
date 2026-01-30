"""
Milestone tracking for SDK telemetry.

Tracks first-* events to avoid duplicate telemetry.
Milestones are stored in $PREFECT_HOME/.sdk_telemetry/milestones.json

For existing users (detected by presence of Prefect artifacts), all milestones
are pre-marked as reached to avoid emitting onboarding events on upgrade.
"""

import json
from pathlib import Path
from typing import Literal

from prefect._internal.analytics.emit import _is_interactive_terminal, emit_sdk_event
from prefect.settings import get_current_settings

MilestoneName = Literal[
    "first_sdk_import",
    "first_flow_defined",
    "first_flow_run",
    "first_deployment_created",
    "first_schedule_created",
]

# All milestone names for pre-marking existing users
ALL_MILESTONES: list[MilestoneName] = [
    "first_sdk_import",
    "first_flow_defined",
    "first_flow_run",
    "first_deployment_created",
    "first_schedule_created",
]

# Files/directories that indicate an existing Prefect user
_EXISTING_USER_INDICATORS = [
    "profiles.toml",  # User has configured profiles
    ".prefect.db",  # Local server database
    "prefect.db",  # Alternative database location
    "storage",  # Result storage directory
]


def _get_telemetry_dir() -> Path:
    """Get the path to the telemetry directory."""
    settings = get_current_settings()
    return settings.home / ".sdk_telemetry"


def _get_milestones_path() -> Path:
    """Get the path to the milestones file."""
    return _get_telemetry_dir() / "milestones.json"


def _read_milestones() -> dict[str, bool]:
    """Read milestones from disk."""
    milestones_path = _get_milestones_path()
    if milestones_path.exists():
        try:
            return json.loads(milestones_path.read_text())
        except Exception:
            pass
    return {}


def _write_milestones(milestones: dict[str, bool]) -> None:
    """Write milestones to disk."""
    milestones_path = _get_milestones_path()
    try:
        milestones_path.parent.mkdir(parents=True, exist_ok=True)
        milestones_path.write_text(json.dumps(milestones, indent=2))
    except Exception:
        pass


def _is_existing_user() -> bool:
    """
    Check if this is an existing Prefect user.

    An existing user is detected by the presence of common Prefect artifacts
    in PREFECT_HOME that would have been created before telemetry was added.

    Returns:
        True if existing user indicators are found
    """
    settings = get_current_settings()
    prefect_home = settings.home

    if not prefect_home.exists():
        return False

    for indicator in _EXISTING_USER_INDICATORS:
        if (prefect_home / indicator).exists():
            return True

    return False


def _mark_existing_user_milestones() -> bool:
    """
    Pre-mark all milestones for existing users.

    This prevents existing users from emitting onboarding events when they
    upgrade to a version with telemetry.

    Returns:
        True if milestones were pre-marked (existing user detected)
    """
    telemetry_dir = _get_telemetry_dir()

    # If telemetry directory already exists, we've already handled this
    if telemetry_dir.exists():
        return False

    # Check if this is an existing user
    if not _is_existing_user():
        return False

    # Pre-mark all milestones for existing users
    milestones = {milestone: True for milestone in ALL_MILESTONES}
    _write_milestones(milestones)
    return True


def has_reached_milestone(milestone: MilestoneName) -> bool:
    """
    Check if a milestone has been reached.

    Args:
        milestone: The milestone name to check

    Returns:
        True if the milestone has been recorded
    """
    milestones = _read_milestones()
    return milestones.get(milestone, False)


def mark_milestone(milestone: MilestoneName) -> None:
    """
    Mark a milestone as reached.

    Args:
        milestone: The milestone name to mark
    """
    milestones = _read_milestones()
    milestones[milestone] = True
    _write_milestones(milestones)


def try_mark_milestone(milestone: MilestoneName) -> bool:
    """
    Try to mark a milestone and emit an event if it's new.

    This is the primary entry point for milestone tracking.
    It checks if the milestone is new, marks it, and emits the event.

    Events are only emitted in interactive terminals to avoid tracking
    deployed flow runs (e.g., Kubernetes jobs) as new users.

    Args:
        milestone: The milestone name to mark

    Returns:
        True if this was the first time reaching the milestone
    """
    # Only emit events in interactive terminals
    # This prevents deployed flow runs from being counted as new users
    if not _is_interactive_terminal():
        return False

    if has_reached_milestone(milestone):
        return False

    mark_milestone(milestone)
    emit_sdk_event(milestone)
    return True
