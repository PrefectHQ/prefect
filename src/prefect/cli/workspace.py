"""
Command line interface for interacting with workspaces
"""
from typing import List

import httpx
import typer

import prefect.context
import prefect.settings

import inquirer

from prefect.cli.base import (
    PrefectTyper,
    app,
    exit_with_error,
    exit_with_success,
)

from prefect.settings import PREFECT_API_KEY, PREFECT_BASE_URL

workspace_app = PrefectTyper(
    name="workspace", help="Commands for interacting with Prefect workspaces"
)
app.add_typer(workspace_app)


def format_handle(account_handle, workspace_handle) -> str:
    return f"{account_handle}/{workspace_handle}"


class NebulaClient:
    def __init__(
        self,
        host: str = PREFECT_BASE_URL.value(),
        api_key: str = PREFECT_API_KEY.value(),
        httpx_settings: dict = None,
    ) -> None:

        httpx_settings = httpx_settings or {}
        httpx_settings.setdefault("headers", {})
        if api_key:
            httpx_settings["headers"].setdefault("Authorization", f"Bearer {api_key}")

        httpx_settings.setdefault("base_url", host)
        self._client = httpx.AsyncClient(**httpx_settings)

    async def read_workspaces(self) -> List[dict]:
        res = await self._client.get("/api/me/workspaces")
        res.raise_for_status()
        return res.json()


@workspace_app.command()
async def login(
    api_key: str = typer.Option(
        ..., help="API Key to authenticate with Prefect", prompt=True
    ),
    workspace_handle: str = typer.Option(
        None,
        help="Full handle of workspace to login to (e.x. '<account_handle>`/<workspace_handle>').",
    ),
):
    """Login. Sets PREFECT_API_URL and PREFECT_API_KEY."""

    client = NebulaClient(api_key=api_key)
    try:
        workspaces = await client.read_workspaces()
    except httpx.HTTPStatusError:
        exit_with_error(
            "Unable to authenticate. Please ensure your credentials are correct."
        )

    workspaces = {
        f"{workspace['account_handle']}/{workspace['workspace_handle']}": workspace
        for workspace in workspaces
    }

    if workspace_handle:
        if workspace_handle not in workspaces:
            exit_with_error(
                f"Workspace {workspace_handle!r} not found. "
                f"Leave `--workspace-handle` blank to select a workspace."
            )
        workspace = workspaces[workspace_handle]
    else:
        questions = [
            inquirer.List(
                "handle",
                message="Select a workspace",
                choices=sorted(workspaces.keys()),
                carousel=True,
            )
        ]
        workspace_handle = inquirer.prompt(questions)["handle"]
        workspace = workspaces[workspace_handle]

    profiles = prefect.settings.load_profiles()
    profile = prefect.context.get_profile_context()
    env = profiles[profile.name]

    account_id = workspace["account_id"]
    workspace_id = workspace["workspace_id"]
    host_url = (
        f"{PREFECT_BASE_URL.value()}/accounts/{account_id}/workspaces/{workspace_id}/"
    )

    env["PREFECT_API_URL"] = host_url
    env["PREFECT_API_KEY"] = api_key
    prefect.settings.write_profiles(profiles)

    exit_with_success(
        f"Successfully logged into workspace {workspace_handle!r} with profile {profile.name!r}."
    )


@workspace_app.command()
async def logout():
    """Logout. Unsets PREFECT_API_URL and PREFECT_API_KEY."""
    profiles = prefect.settings.load_profiles()
    profile = prefect.context.get_profile_context()
    env = profiles[profile.name]

    env.pop("PREFECT_API_URL")
    env.pop("PREFECT_API_KEY")
    prefect.settings.write_profiles(profiles)

    exit_with_success(f"Successfully logged out with profile {profile.name!r}")
