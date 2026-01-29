"""
First-run telemetry notice for SDK telemetry.

Displays a notice to users the first time telemetry is enabled,
but only in interactive terminal sessions.
"""

import sys
from pathlib import Path

from prefect._internal.analytics.emit import _is_interactive_terminal
from prefect.settings import get_current_settings

NOTICE_TEXT = """
Prefect collects anonymous usage data to improve the product.
To opt out: set PREFECT_SERVER_ANALYTICS_ENABLED=false on the server, or DO_NOT_TRACK=1 in the client.
Learn more: https://docs.prefect.io/concepts/telemetry
"""


def _get_notice_marker_path() -> Path:
    """Get the path to the notice marker file."""
    settings = get_current_settings()
    return settings.home / ".sdk_telemetry" / "notice_shown"


def _has_shown_notice() -> bool:
    """Check if the notice has been shown before."""
    return _get_notice_marker_path().exists()


def _mark_notice_shown() -> None:
    """Mark that the notice has been shown."""
    marker_path = _get_notice_marker_path()
    try:
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        marker_path.touch()
    except Exception:
        pass


def maybe_show_telemetry_notice() -> None:
    """
    Show the telemetry notice if appropriate.

    The notice is shown only:
    - The first time telemetry is enabled
    - In an interactive terminal (TTY)
    """
    # Only show in interactive terminals
    if not _is_interactive_terminal():
        return

    # Only show once
    if _has_shown_notice():
        return

    # Show notice and mark as shown
    print(NOTICE_TEXT, file=sys.stderr)
    _mark_notice_shown()
