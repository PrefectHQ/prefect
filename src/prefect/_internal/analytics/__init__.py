"""
Internal implementation for SDK Analytics.

This module contains internal functions that should not be used directly.
Use the public API from prefect.analytics instead.
"""

import logging
import os
import sys
from functools import lru_cache
from typing import Any

import httpx

from prefect._internal.analytics.ci_detection import is_ci_environment
from prefect._internal.analytics.events import SDKEvent

logger: logging.Logger = logging.getLogger("prefect.sdk_analytics")


def _is_interactive_terminal() -> bool:
    """Check if we're running in an interactive terminal."""
    try:
        return sys.stdout.isatty()
    except Exception:
        return False


# Track initialization state
_telemetry_initialized = False


@lru_cache(maxsize=1)
def _get_server_analytics_enabled() -> bool:
    """
    Check if the server has analytics enabled.

    Caches the result to avoid multiple API calls per session.
    Returns False if the server is unreachable.
    """
    from prefect.settings import PREFECT_API_URL

    api_url = PREFECT_API_URL.value()
    if not api_url:
        return False

    try:
        response = httpx.get(f"{api_url}/admin/settings", timeout=5.0)
        response.raise_for_status()
        settings = response.json()
        return settings.get("server", {}).get("analytics_enabled", False)
    except Exception:
        return False


def is_telemetry_enabled() -> bool:
    """
    Check if telemetry is enabled.

    Telemetry is disabled if:
    - DO_NOT_TRACK environment variable is set (client-side)
    - Running in a CI environment
    - Server has PREFECT_SERVER_ANALYTICS_ENABLED=false
    - Server is unreachable

    Returns:
        True if telemetry is enabled, False otherwise
    """
    # Check DO_NOT_TRACK standard (client-side setting)
    do_not_track = os.environ.get("DO_NOT_TRACK", "").lower()
    if do_not_track in ("1", "true", "yes"):
        return False

    # Check CI environment
    if is_ci_environment():
        return False

    # Check server's analytics setting
    return _get_server_analytics_enabled()


def emit_sdk_event(
    event_name: SDKEvent,
    extra_properties: dict[str, Any] | None = None,
) -> bool:
    """
    Emit an SDK telemetry event.

    This is an internal function for tracking SDK events.
    Events are only sent if telemetry is enabled.

    Args:
        event_name: The name of the event to track
        extra_properties: Additional event properties

    Returns:
        True if the event was tracked, False otherwise
    """
    if not is_telemetry_enabled():
        return False

    try:
        from prefect._internal.analytics.client import track_event
        from prefect._internal.analytics.device_id import get_or_create_device_id

        device_id = get_or_create_device_id()
        return track_event(
            event_name=event_name,
            device_id=device_id,
            extra_properties=extra_properties,
        )
    except Exception as exc:
        logger.debug(f"Failed to emit SDK event {event_name}: {exc}")
        return False


def emit_integration_event(
    integration: str,
    event_name: str,
    extra_properties: dict[str, Any] | None = None,
) -> bool:
    """
    Emit a telemetry event from an integration library.

    This is exposed via the public API in prefect.analytics for integration
    libraries (e.g., prefect-aws, prefect-gcp) to emit telemetry events.
    Events are automatically namespaced with the integration name.

    Args:
        integration: The integration name (e.g., "prefect-aws", "prefect-gcp")
        event_name: The event name (e.g., "s3_block_created")
        extra_properties: Additional event properties

    Returns:
        True if the event was tracked, False otherwise
    """
    if not is_telemetry_enabled():
        return False

    try:
        from prefect._internal.analytics.client import track_event
        from prefect._internal.analytics.device_id import get_or_create_device_id

        # Namespace the event with the integration name
        namespaced_event = f"{integration}:{event_name}"

        device_id = get_or_create_device_id()

        # Add integration name to properties
        properties = {"integration": integration}
        if extra_properties:
            properties.update(extra_properties)

        return track_event(
            event_name=namespaced_event,
            device_id=device_id,
            extra_properties=properties,
        )
    except Exception as exc:
        logger.debug(
            f"Failed to emit integration event {integration}:{event_name}: {exc}"
        )
        return False


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
        from prefect._internal.analytics.milestones import (
            _mark_existing_user_milestones,
        )

        is_existing_user = _mark_existing_user_milestones()

        # Don't emit onboarding events for existing users
        if is_existing_user:
            logger.debug("Existing Prefect user detected, skipping onboarding events")
            return

        # Show first-run notice (only in interactive terminals)
        from prefect._internal.analytics.notice import maybe_show_telemetry_notice

        maybe_show_telemetry_notice()

        # Emit sdk_imported event for new users only
        emit_sdk_event("sdk_imported")
    except Exception as exc:
        logger.debug(f"Failed to initialize SDK analytics: {exc}")


# Re-export milestone function for internal use
from prefect._internal.analytics.milestones import try_mark_milestone

__all__ = [
    "initialize_analytics",
    "is_telemetry_enabled",
    "emit_sdk_event",
    "emit_integration_event",
    "try_mark_milestone",
    "_is_interactive_terminal",
]
