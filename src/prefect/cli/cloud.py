"""
Command line interface for interacting with Prefect Cloud
"""
from typing import Dict, Iterable, List

import httpx
import inquirer
import typer

import prefect.context
import prefect.settings
from prefect.cli.base import PrefectTyper, app, exit_with_error, exit_with_success
from prefect.settings import PREFECT_API_KEY, PREFECT_CLOUD_URL, update_profile

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
        profile = prefect.context.get_profile_context()
        exit_with_error(
            f"Currently not authenticated in profile {profile.name!r}. "
            "Please login with `prefect cloud login --key <API_KEY>`."
        )


def get_cloud_client(host: str = None, api_key: str = None) -> "CloudClient":
    profile = prefect.context.get_profile_context()
    return CloudClient(
        host=host or PREFECT_CLOUD_URL.value_from(profile.settings),
        api_key=api_key or PREFECT_API_KEY.value_from(profile.settings),
    )


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
            if exc.response.status_code == 403:
                exit_with_error(
                    "Unable to authenticate. Please ensure your credentials are correct."
                )
            else:
                raise exc

        return res.json()


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
    Log in to Prefect Cloud.
    Sets PREFECT_API_URL and PREFECT_API_KEY for profile.
    If those values are already set they will be overwritten.
    """

    async with get_cloud_client(api_key=key) as client:
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
            "Leave `--workspace` blank to select a workspace."
        )

    update_profile(
        PREFECT_API_URL=build_url_from_workspace(workspaces[workspace_handle]),
        PREFECT_API_KEY=key,
    )

    profile = prefect.context.get_profile_context()
    exit_with_success(
        "Successfully logged in and set workspace to "
        f"{workspace_handle!r} in profile: {profile.name!r}."
    )


@cloud_app.command()
async def logout():
    """
    Log out of Prefect Cloud.
    Removes PREFECT_API_URL and PREFECT_API_KEY from profile.
    """
    confirm_logged_in()

    update_profile(PREFECT_API_URL=None, PREFECT_API_KEY=None)

    profile = prefect.context.get_profile_context()
    exit_with_success(f"Successfully logged out in profile {profile.name!r}")


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
            "Leave `--workspace` blank to select a workspace."
        )

    update_profile(
        PREFECT_API_URL=build_url_from_workspace(workspaces[workspace_handle])
    )

    profile = prefect.context.get_profile_context()
    exit_with_success(
        f"Successfully set workspace to {workspace_handle!r} in profile: {profile.name!r}."
    )
