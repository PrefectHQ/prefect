"""
Command line interface for interacting with Prefect Cloud
"""
from typing import Dict, Iterable, List

import httpx
import inquirer
import typer

import prefect.context
import prefect.settings

from prefect.cli.base import (
    PrefectTyper,
    app,
    exit_with_error,
    exit_with_success,
)

from prefect.settings import PREFECT_API_KEY, PREFECT_API_URL, PREFECT_CLOUD_URL

cloud_app = PrefectTyper(
    name="cloud", help="Commands for interacting with Prefect Cloud"
)
workspace_app = PrefectTyper(
    name="workspace", help="Commands for interacting with Prefect Cloud Workspaces"
)
cloud_app.add_typer(workspace_app)
app.add_typer(cloud_app)


def build_url_from_workspace(workspace: Dict) -> str:
    return f"{PREFECT_CLOUD_URL.value()}" \
           f"/accounts/{workspace['account_id']}" \
           f"/workspaces/{workspace['workspace_id']}"


def confirm_logged_in():
    if PREFECT_API_KEY.value() is None:
        exit_with_error(
            "Currently not logged in. "
            "Please login with `prefect cloud login --key <API_KEY>`."
        )


class CloudClient:
    def __init__(
        self,
        host: str = PREFECT_CLOUD_URL.value(),
        api_key: str = PREFECT_API_KEY.value(),
        httpx_settings: dict = None,
    ) -> None:

        httpx_settings = httpx_settings or {}
        httpx_settings.setdefault("headers", {})
        httpx_settings["headers"].setdefault("Authorization", f"Bearer {api_key}")

        httpx_settings.setdefault("base_url", host)
        self._client = httpx.AsyncClient(**httpx_settings)

    async def get(self, route, **kwargs):
        try:
            res = await self._client.get(route, **kwargs)
            res.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 403:
                exit_with_error(
                    "Unable to authenticate. Please ensure your credentials are correct."
                )
            else:
                raise exc

        return res.json()

    async def read_workspaces(self) -> List[Dict]:
        return await self.get("/me/workspaces")


def prompt_select_workspace(workspaces: Iterable[str]) -> str:
    """
    Prompt the user to select a workspace via the CLI.

    Args:
        workspaces: list of workspaces

    Returns:
        the workspace that was selected
    """
    questions = [
        inquirer.List(
            "workspace",
            message="Select a workspace",
            choices=sorted(workspaces),
            carousel=True,
        )
    ]
    return inquirer.prompt(questions)["workspace"]


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
    Login into Prefect Cloud.
    Sets PREFECT_API_URL and PREFECT_API_KEY for profile.
    If those values are already set they will be overwritten.
    """

    client = CloudClient(api_key=key)

    workspaces = await client.read_workspaces()
    workspaces = {
        f"{workspace['account_handle']}/{workspace['workspace_handle']}": workspace
        for workspace in workspaces
    }

    if not workspace_handle:
        workspace_handle = prompt_select_workspace(workspaces.keys())

    if workspace_handle not in workspaces:
        exit_with_error(
            f"Workspace {workspace_handle!r} not found. "
            f"Leave `--workspace` blank to select a workspace."
        )

    profiles = prefect.settings.load_profiles()
    profile = prefect.context.get_profile_context()
    env = profiles[profile.name]

    env["PREFECT_API_URL"] = build_url_from_workspace(workspaces[workspace_handle])
    env["PREFECT_API_KEY"] = key
    prefect.settings.write_profiles(profiles)

    exit_with_success(f"Successfully logged in and set workspace to "
                      f"{workspace_handle!r} with profile {profile.name!r}.")


@cloud_app.command()
async def logout():
    """
    Logout of Prefect Cloud.
    Removes PREFECT_API_URL and PREFECT_API_KEY from profile.
    """
    confirm_logged_in()

    profiles = prefect.settings.load_profiles()
    profile = prefect.context.get_profile_context()
    env = profiles[profile.name]

    if "PREFECT_API_URL" in env:
        env.pop("PREFECT_API_URL")
    if "PREFECT_API_KEY" in env:
        env.pop("PREFECT_API_KEY")
    prefect.settings.write_profiles(profiles)

    exit_with_success(f"Successfully logged out with profile {profile.name!r}")


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

    client = CloudClient()
    workspaces = await client.read_workspaces()
    workspaces = {
        f"{workspace['account_handle']}/{workspace['workspace_handle']}": workspace
        for workspace in workspaces
    }

    if not workspace_handle:
        workspace_handle = prompt_select_workspace(workspaces)

    if workspace_handle not in workspaces:
        exit_with_error(
            f"Workspace {workspace_handle!r} not found. "
            f"Leave `--workspace` blank to select a workspace."
        )

    profiles = prefect.settings.load_profiles()
    profile = prefect.context.get_profile_context()
    env = profiles[profile.name]

    env["PREFECT_API_URL"] = build_url_from_workspace(workspaces[workspace_handle])
    prefect.settings.write_profiles(profiles)
    exit_with_success(
        f"Successfully set workspace to {workspace_handle!r} with profile {profile.name!r}."
    )
