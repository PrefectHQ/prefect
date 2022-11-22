"""
Command line interface for interacting with Prefect Cloud
"""
import signal
import traceback
import urllib.parse
import webbrowser
from typing import Hashable, Iterable, List, Optional, Tuple, Union

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
from prefect.utilities.asyncutils import run_sync_in_worker_thread
from prefect.utilities.collections import listrepr
from prefect.utilities.compat import raise_signal

# Set up the `prefect cloud` and `prefect cloud workspaces` CLI applications
cloud_app = PrefectTyper(
    name="cloud", help="Commands for interacting with Prefect Cloud"
)
workspace_app = PrefectTyper(
    name="workspace", help="Commands for interacting with Prefect Cloud Workspaces"
)
cloud_app.add_typer(workspace_app, aliases=["workspaces"])
app.add_typer(cloud_app)


def set_login_api_ready_event():
    login_api.extra["ready-event"].set()


login_api = FastAPI(on_startup=[set_login_api_ready_event])
"""
This small API server is used for data transmission for browser-based log in.
"""

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


async def serve_login_api(cancel_scope, task_status):
    config = uvicorn.Config(login_api, port=0, log_level="critical")
    server = uvicorn.Server(config)

    try:
        # Yield the server object
        task_status.started(server)
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


def confirm_logged_in():
    if not PREFECT_API_KEY:
        profile = prefect.context.get_settings_context().profile
        exit_with_error(
            f"Currently not authenticated in profile {profile.name!r}. "
            "Please log in with `prefect cloud login`."
        )


def get_current_workspace(workspaces: Iterable[Workspace]) -> Optional[Workspace]:
    current_api_url = PREFECT_API_URL.value()

    if not current_api_url:
        return None

    for workspace in workspaces:
        if workspace.api_url() == current_api_url:
            return workspace

    return None


def prompt_select_from_list(
    console, prompt: str, options: Union[List[str], List[Tuple[Hashable, str]]]
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

    # Set up an event that the login API will toggle on startup
    ready_event = login_api.extra["ready-event"] = anyio.Event()

    # Set up an event that the login API will set when a response comes from the UI
    result_event = login_api.extra["result-event"] = anyio.Event()

    timeout_scope = None
    async with anyio.create_task_group() as tg:

        # Run a server in the background to get payload from the browser
        server = await tg.start(serve_login_api, tg.cancel_scope)

        # Wait for the login server to be ready
        with anyio.fail_after(10):
            await ready_event.wait()

            # The server may not actually be serving as the lifespan is started first
            while not server.started:
                await anyio.sleep(0)

        # Get the port the server is using
        server_port = server.servers[0].sockets[0].getsockname()[1]
        callback = urllib.parse.quote(f"http://localhost:{server_port}")
        ui_login_url = (
            PREFECT_CLOUD_UI_URL.value() + f"/auth/client?callback={callback}"
        )

        # Then open the authorization page in a new browser tab
        app.console.print("Opening browser...")
        await run_sync_in_worker_thread(webbrowser.open_new_tab, ui_login_url)

        # Wait for the response from the browser,
        with anyio.move_on_after(120) as timeout_scope:
            app.console.print("Waiting for response...")
            await result_event.wait()

        # Uvicorn installs signal handlers, this is the cleanest way to shutdown the
        # login API
        raise_signal(signal.SIGINT)

    result = login_api.extra.get("result")
    if not result:
        if timeout_scope and timeout_scope.cancel_called:
            exit_with_error("Timed out while waiting for authorization.")
        else:
            exit_with_error(f"Aborted.")

    if result.type == "success":
        return result.content.api_key
    elif result.type == "failure":
        exit_with_error(f"Failed to log in. {result.content.reason}")


async def check_key_is_valid_for_login(key: str):
    """
    Attempt to use a key to see if it is valid
    """
    async with get_cloud_client(api_key=key) as client:
        try:
            await client.read_workspaces()
            return True
        except CloudUnauthorizedError:
            return False


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
    if not is_interactive() and (not key or not workspace_handle):
        exit_with_error(
            "When not using an interactive terminal, you must supply a `--key` and `--workspace`."
        )

    profiles = load_profiles()
    current_profile = get_settings_context().profile

    if key and PREFECT_API_KEY.value() == key:
        exit_with_success("This profile is already authenticated with that key.")

    already_logged_in_profiles = []
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
        should_reauth = typer.confirm(
            "? Would you like to reauthenticate?", default=False
        )
        if not should_reauth:
            app.console.print("Using the existing authentication on this profile.")
            key = PREFECT_API_KEY.value()

    elif already_logged_in_profiles:
        app.console.print(
            "It looks like you're already authenticated with another profile."
        )
        if not typer.confirm(
            "? Would you like to reauthenticate with this profile?", default=False
        ):
            if typer.confirm(
                "? Would you like to switch to an authenticated profile?", default=True
            ):
                profile_name = prompt_select_from_list(
                    app.console,
                    "Which authenticated profile would you like to switch to?",
                    already_logged_in_profiles,
                )

                profiles.set_active(profile_name)
                save_profiles(profiles)
                exit_with_success(
                    f"Switched to authenticated profile {profile_name!r}."
                )
            else:
                return

    if not key:
        choice = prompt_select_from_list(
            app.console,
            "How would you like to authenticate?",
            [
                ("browser", "Log in with a web browser"),
                ("key", "Paste an authentication key"),
            ],
        )

        if choice == "key":
            key = typer.prompt("Paste your authentication key", hide_input=True)
        elif choice == "browser":
            key = await login_with_browser()

    async with get_cloud_client(api_key=key) as client:
        try:
            workspaces = await client.read_workspaces()
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

    if workspace_handle:
        # Search for the given workspace
        for workspace in workspaces:
            if workspace.handle == workspace_handle:
                break
        else:
            if workspaces:
                hint = f" Available workspaces: {listrepr((w.handle for w in workspaces), ', ')}"
            else:
                hint = ""

            exit_with_error(f"Workspace {workspace_handle!r} not found." + hint)
    else:
        # Prompt a switch if the number of workspaces is greater than one
        prompt_switch_workspace = len(workspaces) > 1

        current_workspace = get_current_workspace(workspaces)

        # Confirm that we want to switch if the current profile is already logged in
        if (
            current_profile_is_logged_in or current_workspace is not None
        ) and prompt_switch_workspace:
            app.console.print(
                f"You are currently using workspace {current_workspace.handle!r}."
            )
            prompt_switch_workspace = typer.confirm(
                "? Would you like to switch workspaces?", default=False
            )

        if prompt_switch_workspace:
            workspace = prompt_select_from_list(
                app.console,
                "Which workspace would you like to use?",
                [(workspace, workspace.handle) for workspace in workspaces],
            )
        else:
            workspace = current_workspace or workspaces[0]

    update_current_profile(
        {
            PREFECT_API_KEY: key,
            PREFECT_API_URL: workspace.api_url(),
        }
    )

    exit_with_success(
        f"Authenticated with Prefect Cloud! Using workspace {workspace.handle!r}."
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

    current_workspace = get_current_workspace(workspaces)

    table = Table(caption="* active workspace")
    table.add_column(
        "[#024dfd]Workspaces:", justify="left", style="#8ea0ae", no_wrap=True
    )

    for workspace_handle in sorted(workspace.handle for workspace in workspaces):
        if workspace_handle == current_workspace.handle:
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

    if workspace_handle:
        # Search for the given workspace
        for workspace in workspaces:
            if workspace.handle == workspace_handle:
                break
        else:
            exit_with_error(f"Workspace {workspace_handle!r} not found.")
    else:
        workspace = prompt_select_from_list(
            app.console,
            "Which workspace would you like to use?",
            [(workspace, workspace.handle) for workspace in workspaces],
        )

    profile = update_current_profile({PREFECT_API_URL: workspace.api_url()})

    exit_with_success(
        f"Successfully set workspace to {workspace.handle!r} in profile {profile.name!r}."
    )
