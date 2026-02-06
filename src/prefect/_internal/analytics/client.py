"""
Amplitude client wrapper for SDK telemetry.

Provides fire-and-forget event tracking with silent failure handling.
"""

import atexit
import logging
import platform
from typing import Any

from amplitude import Amplitude, BaseEvent, Config

import prefect

# Amplitude API key for SDK telemetry
# This is a write-only key that can only send events, not read data
try:
    from prefect._internal.analytics._config import AMPLITUDE_API_KEY
except ImportError:
    AMPLITUDE_API_KEY = "YOUR_AMPLITUDE_API_KEY_HERE"

# Module-level client instance
_amplitude_client: Amplitude | None = None
_initialized = False


def _get_event_properties() -> dict[str, str]:
    """Get common event properties included with all events."""
    return {
        "prefect_version": prefect.__version__,
        "python_version": platform.python_version(),
        "platform": platform.system(),
        "architecture": platform.machine(),
    }


def _initialize_client() -> bool:
    """
    Initialize the Amplitude client.

    Returns:
        True if initialization succeeded, False otherwise
    """
    global _amplitude_client, _initialized

    if _initialized:
        return _amplitude_client is not None

    _initialized = True

    if AMPLITUDE_API_KEY == "YOUR_AMPLITUDE_API_KEY_HERE":
        # API key not configured - telemetry disabled
        return False

    try:
        # Create a silent logger for Amplitude to prevent SDK errors from reaching users
        amplitude_logger = logging.getLogger("amplitude")
        amplitude_logger.setLevel(logging.CRITICAL)

        config = Config(
            # Flush events after a short delay to avoid blocking
            flush_interval_millis=10000,  # 10 seconds
            flush_queue_size=10,
            # Minimize network overhead
            min_id_length=1,
        )

        _amplitude_client = Amplitude(AMPLITUDE_API_KEY, config)

        # Register shutdown handler to flush remaining events
        atexit.register(_shutdown_client)

        return True
    except Exception:
        return False


def _shutdown_client() -> None:
    """Shutdown the Amplitude client, flushing any remaining events."""
    global _amplitude_client

    if _amplitude_client is not None:
        try:
            _amplitude_client.shutdown()
        except Exception:
            pass
        _amplitude_client = None


def track_event(
    event_name: str,
    device_id: str,
    extra_properties: dict[str, Any] | None = None,
) -> bool:
    """
    Track an event with Amplitude.

    Args:
        event_name: The name of the event to track
        device_id: The anonymous device identifier
        extra_properties: Additional event properties

    Returns:
        True if the event was tracked, False otherwise
    """
    properties = _get_event_properties()
    if extra_properties:
        properties.update(extra_properties)

    if not _initialize_client():
        return False

    try:
        event = BaseEvent(
            event_type=event_name,
            device_id=device_id,
            event_properties=properties,
        )
        _amplitude_client.track(event)
        return True
    except Exception:
        return False


def flush() -> None:
    """Flush any pending events immediately."""
    if _amplitude_client is not None:
        try:
            _amplitude_client.flush()
        except Exception:
            pass
