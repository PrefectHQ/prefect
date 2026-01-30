"""
Internal implementation for SDK Analytics.

This module contains internal functions that should not be used directly.
Use the public API from prefect.analytics instead.
"""

from prefect._internal.analytics.emit import (
    _is_interactive_terminal,
    emit_integration_event,
    emit_sdk_event,
)
from prefect._internal.analytics.enabled import is_telemetry_enabled
from prefect._internal.analytics.milestones import (
    _mark_existing_user_milestones,
    try_mark_milestone,
)
from prefect._internal.analytics.notice import maybe_show_telemetry_notice

# Track initialization state
_telemetry_initialized = False


def initialize_analytics() -> None:
    """
    Initialize SDK analytics on Prefect import.

    This function:
    1. Checks if telemetry is enabled (quick local checks only - non-blocking)
    2. Detects existing users and pre-marks their milestones (no events emitted)
    3. For new users: shows the first-run notice and emits first_sdk_import

    Onboarding events are only emitted in interactive terminals to avoid
    tracking deployed flow runs (e.g., Kubernetes jobs) as new users.

    Called automatically when Prefect is imported.
    """
    global _telemetry_initialized

    if _telemetry_initialized:
        return

    _telemetry_initialized = True

    # Quick local checks only - no network calls
    if not is_telemetry_enabled():
        return

    # Only emit onboarding events in interactive terminals
    # This prevents deployed flow runs from being counted as new users
    if not _is_interactive_terminal():
        return

    try:
        # Check for existing users and pre-mark their milestones
        # This must happen BEFORE any events are emitted
        is_existing_user = _mark_existing_user_milestones()

        # Don't emit onboarding events for existing users
        if is_existing_user:
            return

        # Show first-run notice (only in interactive terminals)
        maybe_show_telemetry_notice()

        # Emit first_sdk_import event for new users only (tracked as a milestone
        # so it is only emitted once per installation)
        try_mark_milestone("first_sdk_import")
    except Exception:
        pass  # Silently ignore initialization errors


__all__ = [
    "initialize_analytics",
    "is_telemetry_enabled",
    "emit_sdk_event",
    "emit_integration_event",
    "try_mark_milestone",
    "_is_interactive_terminal",
]
