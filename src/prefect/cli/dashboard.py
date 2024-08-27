import webbrowser

from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_success
from prefect.cli.cloud import get_current_workspace
from prefect.cli.root import app
from prefect.client.cloud import CloudUnauthorizedError, get_cloud_client
from prefect.settings import PREFECT_UI_URL
from prefect.utilities.asyncutils import run_sync_in_worker_thread

dashboard_app = PrefectTyper(
    name="dashboard",
    help="Commands for interacting with the Prefect UI.",
)
app.add_typer(dashboard_app)


@dashboard_app.command()
async def open():
    """
    Open the Prefect UI in the browser.
    """

    if not (ui_url := PREFECT_UI_URL.value()):
        raise RuntimeError(
            "`PREFECT_UI_URL` must be set to the URL of a running Prefect server or Prefect Cloud workspace."
        )

    await run_sync_in_worker_thread(webbrowser.open_new_tab, ui_url)

    async with get_cloud_client() as client:
        try:
            current_workspace = get_current_workspace(await client.read_workspaces())
        except CloudUnauthorizedError:
            current_workspace = None

    destination = (
        f"{current_workspace.account_handle}/{current_workspace.workspace_handle}"
        if current_workspace
        else ui_url
    )

    exit_with_success(f"Opened {destination!r} in browser.")
