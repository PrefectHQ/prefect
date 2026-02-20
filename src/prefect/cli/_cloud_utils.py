"""Shared cloud utilities used by both typer and cyclopts CLI implementations."""

from __future__ import annotations

import traceback
import urllib.parse
import uuid
import warnings
import webbrowser
from contextlib import asynccontextmanager
from typing import (
    TYPE_CHECKING,
    Iterable,
    Literal,
    NoReturn,
    TypeVar,
    overload,
)

import anyio
import anyio.abc
import readchar
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from rich.console import Console
from rich.live import Live
from rich.table import Table

if TYPE_CHECKING:
    from prefect.client.schemas import Workspace

T = TypeVar("T")


def _exit_with_error(message: str, console: Console | None = None) -> NoReturn:
    """Print a styled error message and exit."""
    target = console or Console(highlight=False, soft_wrap=True)
    if message:
        target.print(message, style="red")
    raise SystemExit(1)


# ---------------------------------------------------------------------------
# Pydantic models for browser-based login
# ---------------------------------------------------------------------------


class LoginSuccess(BaseModel):
    api_key: str


class LoginFailed(BaseModel):
    reason: str


class LoginResult(BaseModel):
    type: Literal["success", "failure"]
    content: LoginSuccess | LoginFailed


class ServerExit(Exception):
    pass


# ---------------------------------------------------------------------------
# Login API (FastAPI app for browser-based OAuth callback)
# ---------------------------------------------------------------------------


def set_login_api_ready_event() -> None:
    login_api.extra["ready-event"].set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        set_login_api_ready_event()
        yield
    finally:
        pass


login_api: FastAPI = FastAPI(lifespan=lifespan)
"""
This small API server is used for data transmission for browser-based log in.
"""

login_api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@login_api.post("/success")
def receive_login(payload: LoginSuccess) -> None:
    login_api.extra["result"] = LoginResult(type="success", content=payload)
    login_api.extra["result-event"].set()


@login_api.post("/failure")
def receive_failure(payload: LoginFailed) -> None:
    login_api.extra["result"] = LoginResult(type="failure", content=payload)
    login_api.extra["result-event"].set()


# ---------------------------------------------------------------------------
# Shared helper functions
# ---------------------------------------------------------------------------


def get_current_workspace(workspaces: Iterable[Workspace]) -> Workspace | None:
    from prefect.settings import PREFECT_API_URL

    current_api_url = PREFECT_API_URL.value()

    if not current_api_url:
        return None

    for workspace in workspaces:
        if workspace.api_url() == current_api_url:
            return workspace

    return None


def confirm_logged_in(console: Console | None = None) -> None:
    import prefect.context
    from prefect.settings import PREFECT_API_KEY

    if not PREFECT_API_KEY:
        profile = prefect.context.get_settings_context().profile
        _exit_with_error(
            f"Currently not authenticated in profile {profile.name!r}. "
            "Please log in with `prefect cloud login`.",
            console=console,
        )


async def check_key_is_valid_for_login(key: str) -> bool:
    from prefect.client.cloud import CloudUnauthorizedError, get_cloud_client

    async with get_cloud_client(api_key=key) as client:
        try:
            await client.read_workspaces()
            return True
        except CloudUnauthorizedError:
            return False


# ---------------------------------------------------------------------------
# Interactive prompt utilities
# ---------------------------------------------------------------------------


@overload
def prompt_select_from_list(
    console: Console, prompt: str, options: list[str]
) -> str: ...


@overload
def prompt_select_from_list(
    console: Console, prompt: str, options: list[tuple[T, str]]
) -> T: ...


def prompt_select_from_list(
    console: Console, prompt: str, options: list[str] | list[tuple[T, str]]
) -> str | T:
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

        table = Table(box=None, header_style=None, padding=(0, 0))
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
            try:
                key = readchar.readkey()
            except KeyboardInterrupt:
                raise SystemExit(130)

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
                # gracefully exit with no message (130 = 128 + SIGINT)
                raise SystemExit(130)
            elif key == readchar.key.ENTER or key == readchar.key.CR:
                selected_option = options[current_idx]
                # Break out of the loop immediately after setting selected_option
                break

            live.update(build_table(), refresh=True)

    # Convert tuple to its first element if needed
    if isinstance(selected_option, tuple):
        selected_option = selected_option[0]

    return selected_option


# ---------------------------------------------------------------------------
# Workspace / account selection
# ---------------------------------------------------------------------------


async def prompt_for_account_and_workspace(
    workspaces: list[Workspace],
    console: Console,
) -> tuple[Workspace | None, bool]:
    if len(workspaces) > 10:
        # Group workspaces by account_id
        workspace_by_account: dict[uuid.UUID, list[Workspace]] = {}
        for workspace in workspaces:
            workspace_by_account.setdefault(workspace.account_id, []).append(workspace)

        if len(workspace_by_account) == 1:
            account_id = next(iter(workspace_by_account.keys()))
            workspaces = workspace_by_account[account_id]
        else:
            accounts = [
                {
                    "account_id": account_id,
                    "account_handle": workspace_by_account[account_id][
                        0
                    ].account_handle,
                }
                for account_id in workspace_by_account.keys()
            ]
            account_options = [
                (account, str(account["account_handle"])) for account in accounts
            ]
            account = prompt_select_from_list(
                console,
                "Which account would you like to use?",
                options=account_options,
            )
            account_id = account["account_id"]
            if TYPE_CHECKING:
                assert isinstance(account_id, uuid.UUID)
            workspaces = workspace_by_account[account_id]

    workspace_options: list[tuple[Workspace | None, str]] = [
        (workspace, workspace.handle) for workspace in workspaces
    ]
    go_back_option = (
        None,
        "[bold]Go back to account selection[/bold]",
    )

    result = prompt_select_from_list(
        console,
        "Which workspace would you like to use?",
        options=workspace_options + [go_back_option],
    )

    if not result:
        return None, True
    else:
        return result, False


# ---------------------------------------------------------------------------
# Browser-based login flow
# ---------------------------------------------------------------------------


async def serve_login_api(
    cancel_scope: anyio.CancelScope,
    console: Console,
    *,
    task_status: anyio.abc.TaskStatus[uvicorn.Server],
) -> None:
    config = uvicorn.Config(login_api, port=0, log_level="critical")
    server = uvicorn.Server(config)

    try:
        # Yield the server object
        task_status.started(server)
        with warnings.catch_warnings():
            # Uvicorn uses the deprecated pieces of websockets, filter out
            # the warnings until uvicorn has its dependencies updated
            warnings.filterwarnings(
                "ignore", category=DeprecationWarning, module="websockets"
            )
            warnings.filterwarnings(
                "ignore",
                category=DeprecationWarning,
                module="uvicorn.protocols.websockets",
            )
            await server.serve()
    except anyio.get_cancelled_exc_class():
        pass  # Already cancelled, do not cancel again
    except SystemExit as exc:
        # If uvicorn is misconfigured, it will throw a system exit and hide the exc
        console.print("[red][bold]X Error starting login service!")
        cause = exc.__context__  # Hide the system exit
        if TYPE_CHECKING:
            assert isinstance(cause, BaseException)
        traceback.print_exception(type(cause), value=cause, tb=cause.__traceback__)
        cancel_scope.cancel()
    else:
        # Exit if we are done serving the API
        # Uvicorn overrides signal handlers so without this Ctrl-C is broken
        cancel_scope.cancel()


async def login_with_browser(console: Console) -> str:
    """
    Perform login using the browser.

    On failure, this function will exit the process.
    On success, it will return an API key.
    """
    from prefect.settings import PREFECT_CLOUD_UI_URL
    from prefect.utilities.asyncutils import run_sync_in_worker_thread

    # Set up an event that the login API will toggle on startup
    ready_event = login_api.extra["ready-event"] = anyio.Event()

    # Set up an event that the login API will set when a response comes from the UI
    result_event = login_api.extra["result-event"] = anyio.Event()

    timeout_scope = None
    async with anyio.create_task_group() as tg:
        # Run a server in the background to get payload from the browser
        server = await tg.start(serve_login_api, tg.cancel_scope, console)

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
        console.print("Opening browser...")
        await run_sync_in_worker_thread(webbrowser.open_new_tab, ui_login_url)

        # Wait for the response from the browser,
        with anyio.move_on_after(120) as timeout_scope:
            console.print("Waiting for response...")
            await result_event.wait()

        # Shut down the background uvicorn server
        tg.cancel_scope.cancel()

    result = login_api.extra.get("result")
    if not result:
        if timeout_scope and timeout_scope.cancel_called:
            _exit_with_error("Timed out while waiting for authorization.", console)
        else:
            _exit_with_error("Aborted.", console)

    if result.type == "success":
        return result.content.api_key
    else:
        _exit_with_error(f"Failed to log in. {result.content.reason}", console)


# ---------------------------------------------------------------------------
# Webhook table rendering
# ---------------------------------------------------------------------------


def render_webhooks_into_table(webhooks: list[dict[str, str]]) -> Table:
    display_table = Table(show_lines=True)
    for field in ["webhook id", "url slug", "name", "enabled?", "template"]:
        display_table.add_column(field, overflow="fold")

    for webhook in webhooks:
        display_table.add_row(
            webhook["id"],
            webhook["slug"],
            webhook["name"],
            str(webhook["enabled"]),
            webhook["template"],
        )
    return display_table
