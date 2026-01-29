"""
Event emission for SDK analytics.
"""

import logging
import sys
from typing import Any

from prefect._internal.analytics.client import track_event
from prefect._internal.analytics.device_id import get_or_create_device_id
from prefect._internal.analytics.enabled import is_telemetry_enabled
from prefect._internal.analytics.events import SDKEvent

logger = logging.getLogger("prefect.sdk_analytics")


def _is_interactive_terminal() -> bool:
    """Check if we're running in an interactive terminal."""
    try:
        return sys.stdout.isatty() or sys.stderr.isatty()
    except Exception:
        return False


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
