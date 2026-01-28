"""
Internal implementation for SDK Analytics.

This module contains internal functions that should not be used directly.
Use the public API from prefect.analytics instead.
"""

import logging

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

logger: logging.Logger = logging.getLogger("prefect.sdk_analytics")

# Track initialization state
_telemetry_initialized = False


def initialize_analytics() -> None:
    """
    Initialize SDK analytics on Prefect import.

    This function:
    1. Checks if telemetry is enabled and running in an interactive terminal
    2. Detects existing users and pre-marks their milestones (no events emitted)
    3. For new users: shows the first-run notice and emits sdk_imported

    Onboarding events are only emitted in interactive terminals to avoid
    tracking deployed flow runs (e.g., Kubernetes jobs) as new users.

    Called automatically when Prefect is imported.
    """
    global _telemetry_initialized

    if _telemetry_initialized:
        return

    _telemetry_initialized = True

    if not is_telemetry_enabled():
        return

    # Only emit onboarding events in interactive terminals
    # This prevents deployed flow runs from being counted as new users
    if not _is_interactive_terminal():
        logger.debug("Non-interactive terminal, skipping onboarding events")
        return

    try:
        # Check for existing users and pre-mark their milestones
        # This must happen BEFORE any events are emitted
        is_existing_user = _mark_existing_user_milestones()

        # Don't emit onboarding events for existing users
        if is_existing_user:
            logger.debug("Existing Prefect user detected, skipping onboarding events")
            return

        # Show first-run notice (only in interactive terminals)
        maybe_show_telemetry_notice()

        # Emit sdk_imported event for new users only
        emit_sdk_event("sdk_imported")
    except Exception as exc:
        logger.debug(f"Failed to initialize SDK analytics: {exc}")


__all__ = [
    "initialize_analytics",
    "is_telemetry_enabled",
    "emit_sdk_event",
    "emit_integration_event",
    "try_mark_milestone",
    "_is_interactive_terminal",
]
