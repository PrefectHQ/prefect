"""
Command line interface for interacting with Prefect Cloud
"""
from typing import Dict, Iterable, List

import httpx
import readchar
import typer
from fastapi import status
from rich.live import Live
from rich.table import Table

import prefect.context
import prefect.settings
from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.root import app
from prefect.exceptions import PrefectException
from prefect.settings import (
    PREFECT_API_KEY,
    PREFECT_API_URL,
    PREFECT_CLOUD_URL,
    update_current_profile,
)

cloud_app = PrefectTyper(
    name="cloud", help="Commands for interacting with Prefect Cloud"
)
workspace_app = PrefectTyper(
    name="workspace", help="Commands for interacting with Prefect Cloud Workspaces"
)
cloud_app.add_typer(workspace_app)
app.add_typer(cloud_app)


def build_url_from_workspace(workspace: Dict) -> str:
    return (
        f"{PREFECT_CLOUD_URL.value()}"
        f"/accounts/{workspace['account_id']}"
        f"/workspaces/{workspace['workspace_id']}"
    )


def confirm_logged_in():
    if not PREFECT_API_KEY:
        profile = prefect.context.get_settings_context().profile
        exit_with_error(
            f"Currently not authenticated in profile {profile.name!r}. "
            "Please login with `prefect cloud login --key <API_KEY>`."
        )


def get_cloud_client(host: str = None, api_key: str = None) -> "CloudClient":
    return CloudClient(
        host=host or PREFECT_CLOUD_URL.value(),
        api_key=api_key or PREFECT_API_KEY.value(),
    )


class CloudUnauthorizedError(PrefectException):
    """
    Raised when the CloudClient receives a 401 or 403 from the Cloud API.
    """


class CloudClient:
    def __init__(
        self,
        host: str,
        api_key: str,
        httpx_settings: dict = None,
    ) -> None:

        httpx_settings = httpx_settings or {}
        httpx_settings.setdefault("headers", {})
        httpx_settings["headers"].setdefault("Authorization", f"Bearer {api_key}")

        httpx_settings.setdefault("base_url", host)
        self._client = httpx.AsyncClient(**httpx_settings)

    async def read_workspaces(self) -> List[Dict]:
        return await self.get("/me/workspaces")

    async def __aenter__(self):
        await self._client.__aenter__()
        return self

    async def __aexit__(self, *exc_info):
        return await self._client.__aexit__(*exc_info)

    def __enter__(self):
        raise RuntimeError(
            "The `CloudClient` must be entered with an async context. Use 'async "
            "with CloudClient(...)' not 'with CloudClient(...)'"
        )

    def __exit__(self, *_):
        assert False, "This should never be called but must be defined for __enter__"

    async def get(self, route, **kwargs):
        try:
            res = await self._client.get(route, **kwargs)
            res.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (
                status.HTTP_401_UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN,
            ):
                raise CloudUnauthorizedError
            else:
                raise exc

        return res.json()


def build_table(selected_idx: int, workspaces: Iterable[str]) -> Table:
    """
    Generate a table of workspaces. The `select_idx` of workspaces will be highlighted.

    Args:
        selected_idx: currently selected index
        workspaces: Iterable of strings

    Returns:
        rich.table.Table
    """

    table = Table()
    table.add_column(
        "[#024dfd]Select a Workspace:", justify="right", style="#8ea0ae", no_wrap=True
    )

    for i, workspace in enumerate(sorted(workspaces)):
        if i == selected_idx:
            table.add_row("[#024dfd on #FFFFFF]> " + workspace)
        else:
            table.add_row("  " + workspace)
    return table


def select_workspace(workspaces: Iterable[str]) -> str:
    """
    Given a list of workspaces, display them to user in a Table
    and allow them to select one.

    Args:
        workspaces: List of workspaces to choose from

    Returns:
        str: the selected workspace
    """

    workspaces = sorted(workspaces)
    current_idx = 0
    selected_workspace = None

    with Live(
        build_table(current_idx, workspaces), auto_refresh=False, console=app.console
    ) as live:
        while selected_workspace is None:
            key = readchar.readkey()

            if key == readchar.key.UP:
                current_idx = current_idx - 1
                # wrap to bottom if at the top
                if current_idx < 0:
                    current_idx = len(workspaces) - 1
            elif key == readchar.key.DOWN:
                current_idx = current_idx + 1
                # wrap to top if at the bottom
                if current_idx >= len(workspaces):
                    current_idx = 0
            elif key == readchar.key.CTRL_C:
                # gracefully exit with no message
                exit_with_error("")
            elif key == readchar.key.ENTER:
                selected_workspace = workspaces[current_idx]

            live.update(build_table(current_idx, workspaces), refresh=True)

        return selected_workspace


@cloud_app.command()
async def login(
    key: str = typer.Option(
        ..., "--key", "-k", help="API Key to authenticate with Prefect", prompt=True
    ),
    workspace_handle: str = typer.Option(
        None,
        "--workspace",
        "-w",
        help="Full handle of workspace, in format '<account_handle>/<workspace_handle>'",
    ),
):
    """
    Log in to Prefect Cloud.
    Sets PREFECT_API_URL and PREFECT_API_KEY for profile.
    If those values are already set they will be overwritten.
    """

    async with get_cloud_client(api_key=key) as client:
        try:
            workspaces = await client.read_workspaces()
        except CloudUnauthorizedError:
            exit_with_error(
                "Unable to authenticate. Please ensure your credentials are correct."
            )

    workspaces = {
        f"{workspace['account_handle']}/{workspace['workspace_handle']}": workspace
        for workspace in workspaces
    }

    if not workspace_handle:
        workspace_handle = select_workspace(workspaces.keys())

    if workspace_handle not in workspaces:
        exit_with_error(
            f"Workspace {workspace_handle!r} not found. "
            "Leave `--workspace` blank to select a workspace."
        )

    profile = update_current_profile(
        {
            PREFECT_API_URL: build_url_from_workspace(workspaces[workspace_handle]),
            PREFECT_API_KEY: key,
        }
    )

    exit_with_success(
        "Successfully logged in and set workspace to "
        f"{workspace_handle!r} in profile {profile.name!r}."
    )


@cloud_app.command()
async def logout():
    """
    Log out of Prefect Cloud.
    Removes PREFECT_API_URL and PREFECT_API_KEY from profile.
    """
    confirm_logged_in()
    profile = update_current_profile({PREFECT_API_URL: None, PREFECT_API_KEY: None})
    exit_with_success(f"Successfully logged out in profile {profile.name!r}.")


@workspace_app.command()
async def set(
    workspace_handle: str = typer.Option(
        None,
        "--workspace",
        "-w",
        help="Full handle of workspace, in format '<account_handle>/<workspace_handle>'",
    ),
):
    """Set current workspace."""
    confirm_logged_in()

    async with get_cloud_client() as client:
        try:
            workspaces = await client.read_workspaces()
        except CloudUnauthorizedError:
            exit_with_error(
                "Unable to authenticate. Please ensure your credentials are correct."
            )
    workspaces = {
        f"{workspace['account_handle']}/{workspace['workspace_handle']}": workspace
        for workspace in workspaces
    }

    if not workspace_handle:
        workspace_handle = select_workspace(workspaces)

    if workspace_handle not in workspaces:
        exit_with_error(
            f"Workspace {workspace_handle!r} not found. "
            "Leave `--workspace` blank to select a workspace."
        )

    profile = update_current_profile(
        {PREFECT_API_URL: build_url_from_workspace(workspaces[workspace_handle])}
    )

    exit_with_success(
        f"Successfully set workspace to {workspace_handle!r} in profile {profile.name!r}."
    )
