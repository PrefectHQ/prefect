"""
Telemetry enabled check for SDK analytics.
"""

import os

from prefect._internal.analytics.ci_detection import is_ci_environment


def is_telemetry_enabled() -> bool:
    """
    Quick non-blocking check of local telemetry settings.

    Telemetry is disabled if:
    - DO_NOT_TRACK environment variable is set (client-side)
    - Running in a CI environment

    Note: Server-side analytics check is performed in the background service
    to avoid blocking the main thread.

    Returns:
        True if local telemetry checks pass, False otherwise
    """
    # Check DO_NOT_TRACK standard (client-side setting)
    do_not_track = os.environ.get("DO_NOT_TRACK", "").lower()
    if do_not_track in ("1", "true", "yes"):
        return False

    # Check CI environment
    if is_ci_environment():
        return False

    return True
