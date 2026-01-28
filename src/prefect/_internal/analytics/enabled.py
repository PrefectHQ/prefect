"""
Telemetry enabled check for SDK analytics.
"""

import os
from functools import lru_cache

import httpx

from prefect._internal.analytics.ci_detection import is_ci_environment
from prefect.settings import PREFECT_API_URL


@lru_cache(maxsize=1)
def _get_server_analytics_enabled() -> bool:
    """
    Check if the server has analytics enabled.

    Caches the result to avoid multiple API calls per session.
    Returns False if the server is unreachable.
    """
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
