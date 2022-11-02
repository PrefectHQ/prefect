"""
Command line interface for interacting with Prefect Cloud
"""
import re
import signal
import traceback
import urllib.parse
import webbrowser
from typing import Dict, Iterable, List, Optional, Tuple, Union

import anyio
import httpx
import readchar
import typer
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from rich.live import Live
from rich.table import Table
from typing_extensions import Literal

import prefect.context
import prefect.settings
from prefect.cli import app
from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.root import app
from prefect.client.cloud import CloudUnauthorizedError, get_cloud_client
from prefect.context import get_settings_context
from prefect.settings import (
    PREFECT_API_KEY,
    PREFECT_API_URL,
    PREFECT_CLOUD_API_URL,
    PREFECT_UI_URL,
    load_profiles,
    save_profiles,
    update_current_profile,
)

# Set up the `prefect cloud` and `prefect cloud workspaces` CLI applications
cloud_app = PrefectTyper(
    name="cloud", help="Commands for interacting with Prefect Cloud"
)
workspace_app = PrefectTyper(
    name="workspace", help="Commands for interacting with Prefect Cloud Workspaces"
)
cloud_app.add_typer(workspace_app, aliases=["workspaces"])
app.add_typer(cloud_app)


# Set up a little API server for browser based `prefect cloud login`


def set_login_api_ready_event():
    login_api.extra["ready-event"].set()


login_api = FastAPI(on_startup=[set_login_api_ready_event])

login_api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoginSuccess(BaseModel):
    api_key: str


class LoginFailed(BaseModel):
    reason: str


class LoginResult(BaseModel):
    type: Literal["success", "failure"]
    content: Union[LoginSuccess, LoginFailed]


class ServerExit(Exception):
    pass


@login_api.post("/success")
def receive_login(payload: LoginSuccess):
    login_api.extra["result"] = LoginResult(type="success", content=payload)
    login_api.extra["result-event"].set()


@login_api.post("/failure")
def receive_failure(payload: LoginFailed):
    login_api.extra["result"] = LoginResult(type="failure", content=payload)
    login_api.extra["result-event"].set()


async def serve_login_api(cancel_scope):
    config = uvicorn.Config(login_api, port=3001, log_level="critical")
    server = uvicorn.Server(config)

    try:
        await server.serve()
    except anyio.get_cancelled_exc_class():
        pass  # Already cancelled, do not cancel again
    except SystemExit as exc:
        # If uvicorn is misconfigured, it will throw a system exit and hide the exc
        app.console.print("[red][bold]X Error starting login service!")
        cause = exc.__context__  # Hide the system exit
        traceback.print_exception(type(cause), value=cause, tb=cause.__traceback__)
        cancel_scope.cancel()
    else:
        # Exit if we are done serving the API
        # Uvicorn overrides signal handlers so without this Ctrl-C is broken
        cancel_scope.cancel()


def build_url_from_workspace(workspace: Dict) -> str:
    return (
        f"{PREFECT_CLOUD_API_URL.value()}"
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


def prompt_select_from_list(
    console, prompt: str, options: Union[List[str], List[Tuple[str, str]]]
) -> str:
    """
    Given a list of options, display the values to user in a table and prompt them
    to select one.

    Args:
        options: A list of options to present to the user.
            A list of tuples can be passed as key value pairs. If a value is chosen, the
            key will be returned.

    Returns:
        str: the selected option
    """

    current_idx = 0
    selected_option = None

    def build_table() -> Table:
        """
        Generate a table of options. The `current_idx` will be highlighted.
        """

        table = Table(box=False, header_style=None, padding=(0, 0))
        table.add_column(
            f"? [bold]{prompt}[/] [bright_blue][Use arrows to move; enter to select]",
            justify="left",
            no_wrap=True,
        )

        for i, option in enumerate(options):
            if isinstance(option, tuple):
                option = option[1]

            if i == current_idx:
                # Use blue for selected options
                table.add_row("[bold][blue]> " + option)
            else:
                table.add_row("  " + option)
        return table

    with Live(build_table(), auto_refresh=False, console=console) as live:
        while selected_option is None:
            key = readchar.readkey()

            if key == readchar.key.UP:
                current_idx = current_idx - 1
                # wrap to bottom if at the top
                if current_idx < 0:
                    current_idx = len(options) - 1
            elif key == readchar.key.DOWN:
                current_idx = current_idx + 1
                # wrap to top if at the bottom
                if current_idx >= len(options):
                    current_idx = 0
            elif key == readchar.key.CTRL_C:
                # gracefully exit with no message
                exit_with_error("")
            elif key == readchar.key.ENTER:
                selected_option = options[current_idx]
                if isinstance(selected_option, tuple):
                    selected_option = selected_option[0]

            live.update(build_table(), refresh=True)

        return selected_option


async def login_with_browser() -> str:
    """
    Perform login using the browser.

    On failure, this function will exit the process.
    On success, it will return an API key.
    """
    # TODO: Search for a valid port
    target = urllib.parse.quote("http://localhost:3001")
    ui_login_url = PREFECT_UI_URL.value() + f"/auth/client?callback={target}"

    # Set up an event that the login API will toggle on startup
    ready_event = login_api.extra["ready-event"] = anyio.Event()

    # Set up an event that the login API will set when a response comes from the UI
    result_event = login_api.extra["result-event"] = anyio.Event()

    timeout_scope = None
    async with anyio.create_task_group() as tg:

        # Run a server in the background to get payload from the browser
        tg.start_soon(serve_login_api, tg.cancel_scope)

        # Wait for the login server to be ready
        async with anyio.fail_after(10):
            await ready_event.wait()

        # Then open the authorization page in a new browser tab
        app.console.print("Opening browser...")
        webbrowser.open_new_tab(ui_login_url)

        # Wait for the response from the browser,
        async with anyio.move_on_after(120) as timeout_scope:
            app.console.print("Waiting for response...")
            await result_event.wait()

        # Uvicorn installs signal handlers, this is the cleanest way to shutdown the
        # login API
        signal.raise_signal(signal.SIGINT)

    result = login_api.extra.get("result")
    if not result:
        if timeout_scope and timeout_scope.cancel_called:
            exit_with_error("Timed out while waiting for authorization.")
        else:
            exit_with_error(f"Aborted.")

    if result.type == "success":
        return result.content.api_key
    elif result.type == "failure":
        exit_with_success(f"Failed to login: {result.content.reason}")


@cloud_app.command()
async def login(
    key: Optional[str] = typer.Option(
        None, "--key", "-k", help="API Key to authenticate with Prefect"
    ),
    workspace_handle: Optional[str] = typer.Option(
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
    current_profile = get_settings_context().profile

    if key and PREFECT_API_KEY.value() == key:
        exit_with_success("This profile is already authenticated with that key.")

    already_logged_in_profiles = []
    for name, profile in profiles.items():
        profile_key = profile.settings.get(PREFECT_API_KEY)
        if not key or (key and profile_key == key):
            already_logged_in_profiles.append(name)

    current_profile_is_logged_in = current_profile.name in already_logged_in_profiles

    if current_profile_is_logged_in:
        app.console.print("It looks like you're already authenticated on this profile.")
        should_reauth = typer.confirm(
            "? Would you like to reauthenticate?", default=False
        )
        if not should_reauth:
            exit_with_success("Using the existing authentication on this profile.")

    elif already_logged_in_profiles:
        app.console.print(
            "It looks like you're already authenticated on another profile."
        )
        should_reauth = typer.confirm(
            "? Would you like to reauthenticate on this profile?", default=False
        )

        if not should_reauth:
            should_switch = typer.confirm(
                "? Would you like to switch to an authenticated profile?", default=True
            )
        else:
            should_switch = False

        if should_switch:
            if len(already_logged_in_profiles) == 1:
                profile_name = already_logged_in_profiles[0]
            else:
                profile_name = prompt_select_from_list(
                    app.console,
                    "Which authenticated profile would you like to switch to?",
                    already_logged_in_profiles,
                )

            profiles.set_active(profile_name)
            save_profiles(profiles)
            exit_with_success("Switched to authenticated profile {profile_name!r}.")

    if not key:
        choice = prompt_select_from_list(
            app.console,
            "How would you like to authenticate the Prefect CLI?",
            [
                ("browser", "Login with a web browser"),
                ("key", "Paste an authentication key"),
            ],
        )

        if choice == "key":
            key = typer.prompt("Paste your authentication key")
        elif choice == "browser":
            key = await login_with_browser()

    async with get_cloud_client(api_key=key) as client:
        try:
            workspaces = await client.read_workspaces()
            workspace_handle_details = {
                f"{workspace['account_handle']}/{workspace['workspace_handle']}": workspace
                for workspace in workspaces
            }
        except CloudUnauthorizedError:
            if key.startswith("pcu"):
                help_message = "It looks like you're using API key from Cloud 1 (https://cloud.prefect.io). Make sure that you generate API key using Cloud 2 (https://app.prefect.cloud)"
            elif not key.startswith("pnu"):
                help_message = "Your key is not in our expected format."
            else:
                help_message = "Please ensure your credentials are correct."
            exit_with_error(
                f"Unable to authenticate with Prefect Cloud. {help_message}"
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

    if not workspace_handle:
        workspace_handle = select_workspace(workspace_handle_details.keys())

    if workspace_handle not in workspace_handle_details:
        exit_with_error(f"Workspace {workspace_handle!r} not found.")

    current_profile = update_current_profile(
        {
            PREFECT_API_URL: build_url_from_workspace(
                workspace_handle_details[workspace_handle]
            ),
            PREFECT_API_KEY: key,
        },
    )

    exit_with_success(
        f"Logged in to Prefect Cloud using profile {current_profile.name!r}.\n"
        f"Workspace is currently set to {workspace_handle!r}. "
        f"The workspace can be changed using `prefect cloud workspace set`."
    )


@cloud_app.command()
async def logout():
    """
    Logout the current workspace.
    Reset PREFECT_API_KEY and PREFECT_API_URL to default.
    """
    current_profile = prefect.context.get_settings_context().profile
    if current_profile is None:
        exit_with_error("There is no current profile set.")

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
