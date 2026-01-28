"""
SDK Analytics module for Prefect telemetry.

This module provides anonymous usage telemetry to help improve Prefect.
All data collection is:
- Anonymous (no user-identifiable information)
- Opt-out (can be disabled via environment variable)
- Transparent (see https://docs.prefect.io/concepts/telemetry)

To opt out:
    # On the server:
    export PREFECT_SERVER_ANALYTICS_ENABLED=false
    # Or on the client:
    export DO_NOT_TRACK=1

Public API:
    emit_integration_event: Emit telemetry events from integration libraries
    is_telemetry_enabled: Check if telemetry is enabled
"""

import logging
from typing import Any

# Re-export internal functions for backwards compatibility with Prefect internals
from prefect.sdk_analytics._internal import (
    _is_interactive_terminal,
    emit_sdk_event,
    initialize_analytics,
    is_telemetry_enabled,
)

# Re-export milestone functions used by Prefect internals
from prefect.sdk_analytics._internal.milestones import try_mark_milestone

logger: logging.Logger = logging.getLogger("prefect.sdk_analytics")


def emit_integration_event(
    integration: str,
    event_name: str,
    extra_properties: dict[str, Any] | None = None,
) -> bool:
    """
    Emit a telemetry event from an integration library.

    This is the public API for integration libraries (e.g., prefect-aws,
    prefect-gcp) to emit telemetry events. Events are automatically
    namespaced with the integration name.

    Args:
        integration: The integration name (e.g., "prefect-aws", "prefect-gcp")
        event_name: The event name (e.g., "s3_block_created")
        extra_properties: Additional event properties

    Returns:
        True if the event was tracked, False otherwise

    Example:
        >>> from prefect.sdk_analytics import emit_integration_event
        >>> emit_integration_event(
        ...     integration="prefect-aws",
        ...     event_name="s3_block_created",
        ...     extra_properties={"bucket_region": "us-east-1"}
        ... )
    """
    if not is_telemetry_enabled():
        return False

    try:
        from prefect.sdk_analytics._internal.client import track_event
        from prefect.sdk_analytics._internal.device_id import get_or_create_device_id

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


__all__ = [
    "emit_integration_event",
    "is_telemetry_enabled",
]
