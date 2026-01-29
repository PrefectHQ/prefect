"""
Public analytics API for Prefect integration libraries.

To opt out of telemetry:
    # On the server:
    export PREFECT_SERVER_ANALYTICS_ENABLED=false
    # Or on the client:
    export DO_NOT_TRACK=1
"""

from typing import Any

from prefect._internal.analytics import (
    emit_integration_event as _emit_integration_event,
)
from prefect._internal.analytics import is_telemetry_enabled as _is_telemetry_enabled


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
        >>> from prefect.analytics import emit_integration_event
        >>> emit_integration_event(
        ...     integration="prefect-aws",
        ...     event_name="s3_block_created",
        ...     extra_properties={"bucket_region": "us-east-1"}
        ... )
    """
    return _emit_integration_event(integration, event_name, extra_properties)


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
    return _is_telemetry_enabled()


__all__ = ["emit_integration_event", "is_telemetry_enabled"]
