"""
Command line interface for interacting with Prefect Cloud
"""

from __future__ import annotations

import os
import uuid
from typing import (
    TYPE_CHECKING,
    Optional,
)

import httpx
import typer
from rich.table import Table

import prefect.context
from prefect.cli._cloud_utils import (
    LoginFailed,
    LoginSuccess,
    LoginResult,
    ServerExit,
    check_key_is_valid_for_login,
    confirm_logged_in,
    get_current_workspace,
    login_with_browser,
    prompt_for_account_and_workspace,
    prompt_select_from_list,
)
from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.root import app, is_interactive
from prefect.client.cloud import CloudUnauthorizedError, get_cloud_client
from prefect.client.schemas import Workspace
from prefect.context import get_settings_context
from prefect.settings import (
    PREFECT_API_KEY,
    PREFECT_API_URL,
    PREFECT_CLOUD_UI_URL,
    load_profiles,
    save_profiles,
    update_current_profile,
)
from prefect.utilities.collections import listrepr

# Re-export shared utilities so existing imports continue to work.
_prompt_select_from_list = prompt_select_from_list
_get_current_workspace = get_current_workspace
_confirm_logged_in = confirm_logged_in
_check_key_is_valid_for_login = check_key_is_valid_for_login
_prompt_for_account_and_workspace = prompt_for_account_and_workspace

# Set up the `prefect cloud` and `prefect cloud workspaces` CLI applications
cloud_app: PrefectTyper = PrefectTyper(
    name="cloud", help="Authenticate and interact with Prefect Cloud"
)
workspace_app: PrefectTyper = PrefectTyper(
    name="workspace", help="View and set Prefect Cloud Workspaces"
)
cloud_app.add_typer(workspace_app, aliases=["workspaces"])
app.add_typer(cloud_app)


@cloud_app.command()
async def login(
    key: Optional[str] = typer.Option(
        None, "--key", "-k", help="API Key to authenticate with Prefect"
    ),
    workspace_handle: Optional[str] = typer.Option(
        None,
        "--workspace",
        "-w",
        help=(
            "Full handle of workspace, in format '<account_handle>/<workspace_handle>'"
        ),
    ),
):
    """
    Log in to Prefect Cloud.
    Creates a new profile configured to use the specified PREFECT_API_KEY.
    Uses a previously configured profile if it exists.
    """
    if not is_interactive() and (not key or not workspace_handle):
        exit_with_error(
            "When not using an interactive terminal, you must supply a `--key` and"
            " `--workspace`."
        )

    profiles = load_profiles()
    current_profile = get_settings_context().profile
    env_var_api_key = os.getenv("PREFECT_API_KEY")
    selected_workspace = None

    if env_var_api_key and key and env_var_api_key != key:
        exit_with_error(
            "Cannot log in with a key when a different PREFECT_API_KEY is present as an"
            " environment variable that will override it."
        )

    if key and env_var_api_key and env_var_api_key == key:
        is_valid_key = await check_key_is_valid_for_login(key)
        is_correct_key_format = key.startswith("pnu_") or key.startswith("pnb_")
        if not is_valid_key:
            help_message = "Please ensure your credentials are correct and unexpired."
            if not is_correct_key_format:
                help_message = "Your key is not in our expected format."
            exit_with_error(
                f"Unable to authenticate with Prefect Cloud. {help_message}"
            )

    already_logged_in_profiles: list[str] = []
    for name, profile in profiles.items():
        profile_key = profile.settings.get(PREFECT_API_KEY)
        if (
            # If a key is provided, only show profiles with the same key
            (key and profile_key == key)
            # Otherwise, show all profiles with a key set
            or (not key and profile_key is not None)
            # Check that the key is usable to avoid suggesting unauthenticated profiles
            and await check_key_is_valid_for_login(profile_key)
        ):
            already_logged_in_profiles.append(name)

    current_profile_is_logged_in = current_profile.name in already_logged_in_profiles

    if current_profile_is_logged_in:
        app.console.print("It looks like you're already authenticated on this profile.")
        if is_interactive():
            should_reauth = typer.confirm(
                "? Would you like to reauthenticate?", default=False
            )
        else:
            should_reauth = True

        if not should_reauth:
            app.console.print("Using the existing authentication on this profile.")
            key = PREFECT_API_KEY.value()

    elif already_logged_in_profiles:
        app.console.print(
            "It looks like you're already authenticated with another profile."
        )
        if typer.confirm(
            "? Would you like to switch profiles?",
            default=True,
        ):
            profile_name = prompt_select_from_list(
                app.console,
                "Which authenticated profile would you like to switch to?",
                already_logged_in_profiles,
            )

            profiles.set_active(profile_name)
            save_profiles(profiles)
            exit_with_success(f"Switched to authenticated profile {profile_name!r}.")

    if not key:
        choice = prompt_select_from_list(
            app.console,
            "How would you like to authenticate?",
            [
                ("browser", "Log in with a web browser"),
                ("key", "Paste an API key"),
            ],
        )

        if choice == "key":
            key = typer.prompt("Paste your API key", hide_input=True)
        elif choice == "browser":
            key = await login_with_browser(app.console)

    if TYPE_CHECKING:
        assert isinstance(key, str)

    async with get_cloud_client(api_key=key) as client:
        try:
            workspaces = await client.read_workspaces()
            current_workspace = get_current_workspace(workspaces)
            prompt_switch_workspace = False
        except CloudUnauthorizedError:
            if key.startswith("pcu"):
                help_message = (
                    "It looks like you're using API key from Cloud 1"
                    " (https://cloud.prefect.io). Make sure that you generate API key"
                    " using Cloud 2 (https://app.prefect.cloud)"
                )
            elif not key.startswith("pnu_") and not key.startswith("pnb_"):
                help_message = (
                    "Your key is not in our expected format: 'pnu_' or 'pnb_'."
                )
            else:
                help_message = (
                    "Please ensure your credentials are correct and unexpired."
                )
            exit_with_error(
                f"Unable to authenticate with Prefect Cloud. {help_message}"
            )
        except httpx.HTTPStatusError as exc:
            exit_with_error(f"Error connecting to Prefect Cloud: {exc!r}")

    if workspace_handle:
        # Search for the given workspace
        for workspace in workspaces:
            if workspace.handle == workspace_handle:
                selected_workspace = workspace
                break
        else:
            if workspaces:
                hint = (
                    " Available workspaces:"
                    f" {listrepr((w.handle for w in workspaces), ', ')}"
                )
            else:
                hint = ""

            exit_with_error(f"Workspace {workspace_handle!r} not found." + hint)
    else:
        # Prompt a switch if the number of workspaces is greater than one
        prompt_switch_workspace = len(workspaces) > 1

        # Confirm that we want to switch if the current profile is already logged in
        if (
            current_profile_is_logged_in and current_workspace is not None
        ) and prompt_switch_workspace:
            app.console.print(
                f"You are currently using workspace {current_workspace.handle!r}."
            )
            prompt_switch_workspace = typer.confirm(
                "? Would you like to switch workspaces?", default=False
            )
    if prompt_switch_workspace:
        go_back = True
        while go_back:
            selected_workspace, go_back = await prompt_for_account_and_workspace(
                workspaces, app.console
            )
        if selected_workspace is None:
            exit_with_error("No workspace selected.")

    elif not selected_workspace and not workspace_handle:
        if current_workspace:
            selected_workspace = current_workspace
        elif len(workspaces) > 0:
            selected_workspace = workspaces[0]
        else:
            exit_with_error(
                "No workspaces found! Create a workspace at"
                f" {PREFECT_CLOUD_UI_URL.value()} and try again."
            )

    if TYPE_CHECKING:
        assert isinstance(selected_workspace, Workspace)

    update_current_profile(
        {
            PREFECT_API_KEY: key,
            PREFECT_API_URL: selected_workspace.api_url(),
        }
    )

    exit_with_success(
        f"Authenticated with Prefect Cloud! Using workspace {selected_workspace.handle!r}."
    )


@cloud_app.command()
async def logout():
    """
    Logout the current workspace.
    Reset PREFECT_API_KEY and PREFECT_API_URL to default.
    """
    current_profile = prefect.context.get_settings_context().profile

    if current_profile.settings.get(PREFECT_API_KEY) is None:
        exit_with_error("Current profile is not logged into Prefect Cloud.")

    update_current_profile(
        {
            PREFECT_API_URL: None,
            PREFECT_API_KEY: None,
        },
    )

    exit_with_success("Logged out from Prefect Cloud.")


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

    current_workspace = get_current_workspace(workspaces)

    table = Table(caption="* active workspace")
    table.add_column(
        "[#024dfd]Workspaces:", justify="left", style="#8ea0ae", no_wrap=True
    )

    for workspace_handle in sorted(workspace.handle for workspace in workspaces):
        if current_workspace and workspace_handle == current_workspace.handle:
            table.add_row(f"[green]* {workspace_handle}[/green]")
        else:
            table.add_row(f"  {workspace_handle}")

    app.console.print(table)


@workspace_app.command()
async def set(
    workspace_handle: str = typer.Option(
        None,
        "--workspace",
        "-w",
        help=(
            "Full handle of workspace, in format '<account_handle>/<workspace_handle>'"
        ),
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

        if workspace_handle:
            # Search for the given workspace
            for workspace in workspaces:
                if workspace.handle == workspace_handle:
                    break
            else:
                exit_with_error(f"Workspace {workspace_handle!r} not found.")
        else:
            if not workspaces:
                exit_with_error("No workspaces found in the selected account.")

            # Store the original list of workspaces
            original_workspaces = workspaces.copy()

            go_back = True
            workspace = None
            loop_count = 0

            while go_back:
                loop_count += 1

                # If we're going back, use the original list of workspaces
                if loop_count > 1:
                    workspaces = original_workspaces.copy()

                workspace, go_back = await _prompt_for_account_and_workspace(
                    workspaces, app.console
                )

            if workspace is None:
                exit_with_error("No workspace selected.")

        profile = update_current_profile({PREFECT_API_URL: workspace.api_url()})
        exit_with_success(
            f"Successfully set workspace to {workspace.handle!r} in profile"
            f" {profile.name!r}."
        )
