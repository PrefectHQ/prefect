"""
Event emission for SDK analytics.
"""

import sys
from typing import Any

from prefect._internal.analytics.device_id import get_or_create_device_id
from prefect._internal.analytics.events import SDKEvent
from prefect._internal.analytics.service import AnalyticsEvent, AnalyticsService


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
    Events are queued for processing in a background thread (non-blocking).

    Args:
        event_name: The name of the event to track
        extra_properties: Additional event properties

    Returns:
        True if the event was queued, False otherwise
    """
    try:
        device_id = get_or_create_device_id()
        event = AnalyticsEvent(
            event_name=event_name,
            device_id=device_id,
            extra_properties=extra_properties,
        )
        AnalyticsService.instance().enqueue(event)
        return True
    except Exception:
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
        True if the event was queued, False otherwise
    """
    try:
        # Namespace the event with the integration name
        namespaced_event = f"{integration}:{event_name}"

        device_id = get_or_create_device_id()

        # Add integration name to properties
        properties = {"integration": integration}
        if extra_properties:
            properties.update(extra_properties)

        event = AnalyticsEvent(
            event_name=namespaced_event,
            device_id=device_id,
            extra_properties=properties,
        )
        AnalyticsService.instance().enqueue(event)
        return True
    except Exception:
        return False
