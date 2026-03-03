"""
Dashboard command — native cyclopts implementation.

Open the Prefect UI in the browser.
"""

import webbrowser

import cyclopts

from prefect.cli._utilities import (
    exit_with_error,
    exit_with_success,
    with_cli_exception_handling,
)

dashboard_app: cyclopts.App = cyclopts.App(
    name="dashboard",
    help="Commands for interacting with the Prefect UI.",
    version_flags=[],
    help_flags=["--help"],
)


@dashboard_app.command(name="open")
@with_cli_exception_handling
async def open_dashboard():
    """Open the Prefect UI in the browser."""
    from prefect.settings import get_current_settings
    from prefect.utilities.asyncutils import run_sync_in_worker_thread

    if not (ui_url := get_current_settings().ui_url):
        exit_with_error(
            "`PREFECT_UI_URL` must be set to the URL of a running Prefect server or Prefect Cloud workspace."
        )

    await run_sync_in_worker_thread(webbrowser.open_new_tab, ui_url)

    exit_with_success(f"Opened {ui_url!r} in browser.")
