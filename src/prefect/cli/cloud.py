"""
Command line interface for interacting with Prefect Cloud
"""
import re
from typing import Dict, Iterable, List

import anyio
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
    load_profiles,
    save_profiles,
    update_current_profile,
)

cloud_app = PrefectTyper(
    name="cloud", help="Commands for interacting with Prefect Cloud"
)
workspace_app = PrefectTyper(
    name="workspace", help="Commands for interacting with Prefect Cloud Workspaces"
)
cloud_app.add_typer(workspace_app, aliases=["workspaces"])
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


def get_current_workspace(workspaces):
    workspace_handles_by_id = {
        workspace[
            "workspace_id"
        ]: f"{workspace['account_handle']}/{workspace['workspace_handle']}"
        for workspace in workspaces
    }
    current_workspace_id = re.match(
        r".*accounts/.{36}/workspaces/(.{36})\Z", PREFECT_API_URL.value()
    ).groups()[0]
    return workspace_handles_by_id[current_workspace_id]


def get_cloud_client(
    host: str = None,
    api_key: str = None,
    httpx_settings: dict = None,
    infer_cloud_url: bool = False,
) -> "CloudClient":
    if httpx_settings is not None:
        httpx_settings = httpx_settings.copy()

    if infer_cloud_url is False:
        host = host or PREFECT_CLOUD_URL.value()
    else:
        configured_url = prefect.settings.PREFECT_API_URL.value()
        host = re.sub(r"accounts/.{36}/workspaces/.{36}\Z", "", configured_url)

    return CloudClient(
        host=host,
        api_key=api_key or PREFECT_API_KEY.value(),
        httpx_settings=httpx_settings,
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

        httpx_settings = httpx_settings or dict()
        httpx_settings.setdefault("headers", dict())
        httpx_settings["headers"].setdefault("Authorization", f"Bearer {api_key}")

        httpx_settings.setdefault("base_url", host)
        self._client = httpx.AsyncClient(**httpx_settings)

    async def api_healthcheck(self):
        """
        Attempts to connect to the Cloud API and raises the encountered exception if not
        successful.

        If successful, returns `None`.
        """
        with anyio.fail_after(10):
            await self.read_workspaces()

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
    Creates a new profile configured to use the specified PREFECT_API_KEY.
    Uses a previously configured profile if it exists.
    """
    profiles = load_profiles()

    async with get_cloud_client(api_key=key) as client:
        try:
            workspaces = await client.read_workspaces()
            workspace_handle_details = {
                f"{workspace['account_handle']}/{workspace['workspace_handle']}": workspace
                for workspace in workspaces
            }
        except CloudUnauthorizedError:
            exit_with_error(
                "Unable to authenticate with Prefect Cloud. Please ensure your credentials are correct."
            )
        except httpx.HTTPStatusError as exc:
            exit_with_error(f"Error connecting to Prefect Cloud: {exc!r}")

    for profile_name in profiles:
        if key == profiles[profile_name].settings.get(PREFECT_API_KEY):
            profiles.set_active(profile_name)
            save_profiles(profiles)
            with prefect.context.use_profile(profile_name):
                current_workspace = get_current_workspace(workspaces)

                if workspace_handle is not None:
                    if workspace_handle not in workspace_handle_details:
                        exit_with_error(f"Workspace {workspace_handle!r} not found.")

                    update_current_profile(
                        {
                            PREFECT_API_URL: build_url_from_workspace(
                                workspace_handle_details[workspace_handle]
                            )
                        }
                    )
                    current_workspace = workspace_handle

                exit_with_success(
                    f"Logged in to Prefect Cloud using profile {profile_name!r}.\n"
                    f"Workspace is currently set to {current_workspace!r}. "
                    f"The workspace can be changed using `prefect cloud workspace set`."
                )

    workspace_handle_details = {
        f"{workspace['account_handle']}/{workspace['workspace_handle']}": workspace
        for workspace in workspaces
    }

    if not workspace_handle:
        workspace_handle = select_workspace(workspace_handle_details.keys())

    cloud_profile_name = app.console.input(
        "Creating a profile for this Prefect Cloud login. Please specify a profile name: "
    )

    cloud_profile_name = cloud_profile_name.strip()
    if cloud_profile_name == "":
        exit_with_error("Please provide a non-empty profile name.")

    if cloud_profile_name in profiles:
        exit_with_error(f"Profile {cloud_profile_name!r} already exists.")

    profiles.add_profile(
        profiles[profiles.active_name].copy(
            update={
                "name": cloud_profile_name,
            }
        )
    )

    profiles.update_profile(
        cloud_profile_name,
        {
            PREFECT_API_URL: build_url_from_workspace(
                workspace_handle_details[workspace_handle]
            ),
            PREFECT_API_KEY: key,
        },
    )

    profiles.set_active(cloud_profile_name)
    save_profiles(profiles)

    exit_with_success(
        f"Logged in to Prefect Cloud using profile {cloud_profile_name!r}.\n"
        f"Workspace is currently set to {workspace_handle!r}. "
        f"The workspace can be changed using `prefect cloud workspace set`."
    )


@workspace_app.command()
async def ls():
    """List available workspaces."""

    confirm_logged_in()

    async with get_cloud_client() as client:
        try:
            workspaces = await client.read_workspaces()
        except CloudUnauthorizedError:
            exit_with_error(
                "Unable to authenticate. Please ensure your credentials are correct."
            )

    workspace_handle_details = {
        f"{workspace['account_handle']}/{workspace['workspace_handle']}": workspace
        for workspace in workspaces
    }

    current_workspace = get_current_workspace(workspaces)

    table = Table(caption="* active workspace")
    table.add_column(
        "[#024dfd]Available Workspaces:", justify="right", style="#8ea0ae", no_wrap=True
    )

    for i, workspace_handle in enumerate(sorted(workspace_handle_details)):
        if workspace_handle == current_workspace:
            table.add_row(f"[green]  * {workspace_handle}[/green]")
        else:
            table.add_row(f"  {workspace_handle}")
    app.console.print(table)


@workspace_app.command()
async def set(
    workspace_handle: str = typer.Option(
        None,
        "--workspace",
        "-w",
        help="Full handle of workspace, in format '<account_handle>/<workspace_handle>'",
    ),
):
    """Set current workspace. Shows a workspace picker if no workspace is specified."""
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
