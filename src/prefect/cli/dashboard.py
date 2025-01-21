import webbrowser

from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.root import app
from prefect.settings import PREFECT_UI_URL
from prefect.utilities.asyncutils import run_sync_in_worker_thread

dashboard_app: PrefectTyper = PrefectTyper(
    name="dashboard",
    help="Commands for interacting with the Prefect UI.",
)
app.add_typer(dashboard_app)


@dashboard_app.command()
async def open() -> None:
    """
    Open the Prefect UI in the browser.
    """

    if not (ui_url := PREFECT_UI_URL.value()):
        exit_with_error(
            "`PREFECT_UI_URL` must be set to the URL of a running Prefect server or Prefect Cloud workspace."
        )

    await run_sync_in_worker_thread(webbrowser.open_new_tab, ui_url)

    exit_with_success(f"Opened {ui_url!r} in browser.")
