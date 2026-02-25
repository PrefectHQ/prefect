"""
Cloud command — native cyclopts implementation.

Authenticate and interact with Prefect Cloud.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Annotated, Any
from uuid import UUID

import cyclopts
from rich.panel import Panel
from rich.table import Table

import prefect.cli._app as _cli
from prefect.cli._cloud_utils import (
    check_key_is_valid_for_login,
    confirm_logged_in,
    get_current_workspace,
    login_with_browser,
    prompt_for_account_and_workspace,
    prompt_select_from_list,
    render_webhooks_into_table,
)
from prefect.cli._utilities import (
    exit_with_error,
    exit_with_success,
    with_cli_exception_handling,
)

if TYPE_CHECKING:
    from prefect.client.schemas import Workspace

cloud_app: cyclopts.App = cyclopts.App(
    name="cloud",
    help="Authenticate and interact with Prefect Cloud.",
    version_flags=[],
    help_flags=["--help"],
)

# --- workspace sub-app ---
workspace_app: cyclopts.App = cyclopts.App(
    name="workspace",
    alias="workspaces",
    help="View and set Prefect Cloud Workspaces.",
    version_flags=[],
    help_flags=["--help"],
)
cloud_app.command(workspace_app)

# --- webhook sub-app ---
webhook_app: cyclopts.App = cyclopts.App(
    name="webhook",
    alias="webhooks",
    help="Manage Prefect Cloud Webhooks.",
    version_flags=[],
    help_flags=["--help"],
)
cloud_app.command(webhook_app)

# --- ip-allowlist sub-app ---
ip_allowlist_app: cyclopts.App = cyclopts.App(
    name="ip-allowlist",
    alias="ip-allowlists",
    help="Manage Prefect Cloud IP Allowlists.",
    version_flags=[],
    help_flags=["--help"],
)
cloud_app.command(ip_allowlist_app)

# --- asset sub-app ---
asset_app: cyclopts.App = cyclopts.App(
    name="asset",
    alias="assets",
    help="Manage Prefect Cloud assets.",
    version_flags=[],
    help_flags=["--help"],
)
cloud_app.command(asset_app)


# =====================================================================
# cloud login / logout
# =====================================================================


@cloud_app.command(name="login")
@with_cli_exception_handling
async def login(
    *,
    key: Annotated[
        str | None,
        cyclopts.Parameter(
            "--key", alias="-k", help="API Key to authenticate with Prefect"
        ),
    ] = None,
    workspace_handle: Annotated[
        str | None,
        cyclopts.Parameter(
            "--workspace",
            alias="-w",
            help="Full handle of workspace, in format '<account_handle>/<workspace_handle>'",
        ),
    ] = None,
):
    """Log in to Prefect Cloud.
    Creates a new profile configured to use the specified PREFECT_API_KEY.
    Uses a previously configured profile if it exists.
    """
    import httpx

    from prefect.cli._prompts import confirm
    from prefect.client.cloud import CloudUnauthorizedError, get_cloud_client
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

    console = _cli.console

    if not _cli.is_interactive() and (not key or not workspace_handle):
        exit_with_error(
            "When not using an interactive terminal, you must supply a `--key` and"
            " `--workspace`."
        )

    profiles = load_profiles()
    current_profile = get_settings_context().profile
    env_var_api_key = os.getenv("PREFECT_API_KEY")
    selected_workspace: Workspace | None = None

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
        console.print("It looks like you're already authenticated on this profile.")
        if _cli.is_interactive():
            should_reauth = confirm(
                "Would you like to reauthenticate?", default=False, console=console
            )
        else:
            should_reauth = True

        if not should_reauth:
            console.print("Using the existing authentication on this profile.")
            key = PREFECT_API_KEY.value()

    elif already_logged_in_profiles:
        console.print(
            "It looks like you're already authenticated with another profile."
        )
        if confirm(
            "Would you like to switch profiles?",
            default=True,
            console=console,
        ):
            profile_name = prompt_select_from_list(
                console,
                "Which authenticated profile would you like to switch to?",
                already_logged_in_profiles,
            )

            profiles.set_active(profile_name)
            save_profiles(profiles)
            exit_with_success(f"Switched to authenticated profile {profile_name!r}.")

    if not key:
        choice = prompt_select_from_list(
            console,
            "How would you like to authenticate?",
            [
                ("browser", "Log in with a web browser"),
                ("key", "Paste an API key"),
            ],
        )

        if choice == "key":
            from prefect.cli._prompts import prompt as _prompt

            key = _prompt("Paste your API key", password=True, console=console)
        elif choice == "browser":
            key = await login_with_browser(console)

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
            console.print(
                f"You are currently using workspace {current_workspace.handle!r}."
            )
            prompt_switch_workspace = confirm(
                "Would you like to switch workspaces?", default=False, console=console
            )
    if prompt_switch_workspace:
        go_back = True
        while go_back:
            selected_workspace, go_back = await prompt_for_account_and_workspace(
                workspaces, console
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
        from prefect.client.schemas import Workspace as WorkspaceType

        assert isinstance(selected_workspace, WorkspaceType)

    update_current_profile(
        {
            PREFECT_API_KEY: key,
            PREFECT_API_URL: selected_workspace.api_url(),
        }
    )

    exit_with_success(
        f"Authenticated with Prefect Cloud! Using workspace {selected_workspace.handle!r}."
    )


@cloud_app.command(name="logout")
@with_cli_exception_handling
async def logout():
    """Logout the current workspace.
    Reset PREFECT_API_KEY and PREFECT_API_URL to default.
    """
    from prefect.context import get_settings_context
    from prefect.settings import (
        PREFECT_API_KEY,
        PREFECT_API_URL,
        update_current_profile,
    )

    current_profile = get_settings_context().profile

    if current_profile.settings.get(PREFECT_API_KEY) is None:
        exit_with_error("Current profile is not logged into Prefect Cloud.")

    update_current_profile(
        {
            PREFECT_API_URL: None,
            PREFECT_API_KEY: None,
        },
    )

    exit_with_success("Logged out from Prefect Cloud.")


# =====================================================================
# cloud workspace
# =====================================================================


@workspace_app.command(name="ls")
@with_cli_exception_handling
async def workspace_ls():
    """List available workspaces."""
    from prefect.client.cloud import CloudUnauthorizedError, get_cloud_client

    confirm_logged_in(console=_cli.console)

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

    _cli.console.print(table)


@workspace_app.command(name="set")
@with_cli_exception_handling
async def workspace_set(
    *,
    workspace_handle: Annotated[
        str | None,
        cyclopts.Parameter(
            "--workspace",
            alias="-w",
            help="Full handle of workspace, in format '<account_handle>/<workspace_handle>'",
        ),
    ] = None,
):
    """Set current workspace. Shows a workspace picker if no workspace is specified."""
    from prefect.client.cloud import CloudUnauthorizedError, get_cloud_client
    from prefect.settings import PREFECT_API_URL, update_current_profile

    confirm_logged_in(console=_cli.console)
    console = _cli.console

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

                workspace, go_back = await prompt_for_account_and_workspace(
                    workspaces, console
                )

            if workspace is None:
                exit_with_error("No workspace selected.")

        profile = update_current_profile({PREFECT_API_URL: workspace.api_url()})
        exit_with_success(
            f"Successfully set workspace to {workspace.handle!r} in profile"
            f" {profile.name!r}."
        )


# =====================================================================
# cloud webhook
# =====================================================================


@webhook_app.command(name="ls")
@with_cli_exception_handling
async def webhook_ls():
    """Fetch and list all webhooks in your workspace."""
    from prefect.client.cloud import get_cloud_client
    from prefect.settings import get_current_settings

    confirm_logged_in(console=_cli.console)

    async with get_cloud_client(host=get_current_settings().api.url) as client:
        retrieved_webhooks = await client.request("POST", "/webhooks/filter")
        display_table = render_webhooks_into_table(retrieved_webhooks)
        _cli.console.print(display_table)


@webhook_app.command(name="get")
@with_cli_exception_handling
async def webhook_get(
    webhook_id: Annotated[UUID, cyclopts.Parameter(help="The webhook ID to retrieve.")],
):
    """Retrieve a webhook by ID."""
    from prefect.client.cloud import get_cloud_client
    from prefect.settings import get_current_settings

    confirm_logged_in(console=_cli.console)

    async with get_cloud_client(host=get_current_settings().api.url) as client:
        webhook = await client.request("GET", f"/webhooks/{webhook_id}")
        display_table = render_webhooks_into_table([webhook])
        _cli.console.print(display_table)


@webhook_app.command(name="create")
@with_cli_exception_handling
async def webhook_create(
    webhook_name: Annotated[str, cyclopts.Parameter(help="The name of the webhook.")],
    *,
    description: Annotated[
        str,
        cyclopts.Parameter(
            "--description", alias="-d", help="Description of the webhook"
        ),
    ] = "",
    template: Annotated[
        str | None,
        cyclopts.Parameter("--template", alias="-t", help="Jinja2 template expression"),
    ] = None,
):
    """Create a new Cloud webhook."""
    from prefect.client.cloud import get_cloud_client
    from prefect.settings import get_current_settings

    if not template:
        exit_with_error(
            "Please provide a Jinja2 template expression in the --template flag \nwhich"
            ' should define (at minimum) the following attributes: \n{ "event":'
            ' "your.event.name", "resource": { "prefect.resource.id":'
            ' "your.resource.id" } }'
            " \nhttps://docs.prefect.io/latest/automate/events/webhook-triggers#webhook-templates"
        )

    confirm_logged_in(console=_cli.console)

    async with get_cloud_client(host=get_current_settings().api.url) as client:
        response = await client.request(
            "POST",
            "/webhooks/",
            json={
                "name": webhook_name,
                "description": description,
                "template": template,
            },
        )
        _cli.console.print(f"Successfully created webhook {response['name']}")


@webhook_app.command(name="rotate")
@with_cli_exception_handling
async def webhook_rotate(
    webhook_id: Annotated[UUID, cyclopts.Parameter(help="The webhook ID to rotate.")],
):
    """Rotate url for an existing Cloud webhook, in case it has been compromised."""
    from prefect.cli._prompts import confirm
    from prefect.client.cloud import get_cloud_client
    from prefect.settings import get_current_settings

    confirm_logged_in(console=_cli.console)

    if not confirm(
        "Are you sure you want to rotate? This will invalidate the old URL.",
        console=_cli.console,
    ):
        return

    async with get_cloud_client(host=get_current_settings().api.url) as client:
        response = await client.request("POST", f"/webhooks/{webhook_id}/rotate")
        _cli.console.print(f"Successfully rotated webhook URL to {response['slug']}")


@webhook_app.command(name="toggle")
@with_cli_exception_handling
async def webhook_toggle(
    webhook_id: Annotated[UUID, cyclopts.Parameter(help="The webhook ID to toggle.")],
):
    """Toggle the enabled status of an existing Cloud webhook."""
    from prefect.client.cloud import get_cloud_client
    from prefect.settings import get_current_settings

    confirm_logged_in(console=_cli.console)

    status_lookup = {True: "enabled", False: "disabled"}

    async with get_cloud_client(host=get_current_settings().api.url) as client:
        response = await client.request("GET", f"/webhooks/{webhook_id}")
        current_status = response["enabled"]
        new_status = not current_status

        await client.request(
            "PATCH", f"/webhooks/{webhook_id}", json={"enabled": new_status}
        )
        _cli.console.print(f"Webhook is now {status_lookup[new_status]}")


@webhook_app.command(name="update")
@with_cli_exception_handling
async def webhook_update(
    webhook_id: Annotated[UUID, cyclopts.Parameter(help="The webhook ID to update.")],
    *,
    webhook_name: Annotated[
        str | None,
        cyclopts.Parameter("--name", alias="-n", help="Webhook name"),
    ] = None,
    description: Annotated[
        str | None,
        cyclopts.Parameter(
            "--description", alias="-d", help="Description of the webhook"
        ),
    ] = None,
    template: Annotated[
        str | None,
        cyclopts.Parameter("--template", alias="-t", help="Jinja2 template expression"),
    ] = None,
):
    """Partially update an existing Cloud webhook."""
    from prefect.client.cloud import get_cloud_client
    from prefect.settings import get_current_settings

    confirm_logged_in(console=_cli.console)

    async with get_cloud_client(host=get_current_settings().api.url) as client:
        response = await client.request("GET", f"/webhooks/{webhook_id}")
        update_payload = {
            "name": webhook_name or response["name"],
            "description": description or response["description"],
            "template": template or response["template"],
        }

        await client.request("PUT", f"/webhooks/{webhook_id}", json=update_payload)
        _cli.console.print(f"Successfully updated webhook {webhook_id}")


@webhook_app.command(name="delete")
@with_cli_exception_handling
async def webhook_delete(
    webhook_id: Annotated[UUID, cyclopts.Parameter(help="The webhook ID to delete.")],
):
    """Delete an existing Cloud webhook."""
    from prefect.cli._prompts import confirm
    from prefect.client.cloud import get_cloud_client
    from prefect.exceptions import ObjectNotFound
    from prefect.settings import get_current_settings

    confirm_logged_in(console=_cli.console)

    if _cli.is_interactive() and not confirm(
        f"Are you sure you want to delete webhook with id '{webhook_id!s}'?",
        default=False,
        console=_cli.console,
    ):
        exit_with_error("Deletion aborted.")

    async with get_cloud_client(host=get_current_settings().api.url) as client:
        try:
            await client.request("DELETE", f"/webhooks/{webhook_id}")
            _cli.console.print(f"Successfully deleted webhook {webhook_id}")
        except ObjectNotFound:
            exit_with_error(f"Webhook with id '{webhook_id!s}' not found.")
        except Exception as exc:
            exit_with_error(f"Error deleting webhook: {exc}")


# =====================================================================
# cloud ip-allowlist
# =====================================================================


async def _check_ip_allowlist_access() -> bool:
    """Check if the account has access to IP allowlisting.

    Returns the enforce_ip_allowlist setting value.
    Exits with an error if the account does not have access.
    """
    from prefect.client.cloud import get_cloud_client

    confirm_logged_in(console=_cli.console)

    async with get_cloud_client(infer_cloud_url=True) as client:
        account_settings = await client.read_account_settings()

    if "enforce_ip_allowlist" not in account_settings:
        exit_with_error("IP allowlisting is not available for this account.")

    return account_settings.get("enforce_ip_allowlist", False)


def _print_ip_allowlist_table(ip_allowlist: Any, enabled: bool) -> None:
    from prefect.client.schemas.objects import IPAllowlist

    if TYPE_CHECKING:
        assert isinstance(ip_allowlist, IPAllowlist)

    if not ip_allowlist.entries:
        _cli.console.print(
            Panel(
                "IP allowlist is empty. Add an entry to secure access to your Prefect Cloud account.",
                expand=False,
            )
        )
        return

    red_asterisk_if_not_enabled = "[red]*[/red]" if enabled is False else ""

    table = Table(
        title="IP Allowlist " + red_asterisk_if_not_enabled,
        caption=f"{red_asterisk_if_not_enabled} Enforcement is "
        f"[bold]{'ENABLED' if enabled else '[red]DISABLED[/red]'}[/bold].",
        caption_style="not dim",
    )

    table.add_column("IP Address", style="cyan", no_wrap=True)
    table.add_column("Description", style="blue", no_wrap=False)
    table.add_column("Enabled", style="green", justify="right", no_wrap=True)
    table.add_column("Last Seen", style="magenta", justify="right", no_wrap=True)

    for entry in ip_allowlist.entries:
        table.add_row(
            str(entry.ip_network),
            entry.description,
            str(entry.enabled),
            entry.last_seen or "Never",
            style="dim" if not entry.enabled else None,
        )

    _cli.console.print(table)


def _handle_update_error(error: Any) -> None:
    from prefect.exceptions import PrefectHTTPStatusError

    if TYPE_CHECKING:
        assert isinstance(error, PrefectHTTPStatusError)
    if error.response.status_code == 422 and (
        details := (
            error.response.json().get("detail")
            or error.response.json().get("exception_detail")
        )
    ):
        exit_with_error(f"Error updating allowlist: {details}")
    else:
        raise error


def _parse_ip_network(val: str) -> Any:
    """Parse and validate an IP network argument."""
    from pydantic import BaseModel, IPvAnyNetwork, ValidationError

    class IPNetworkArg(BaseModel):
        raw: str
        parsed: IPvAnyNetwork

    try:
        return IPNetworkArg(raw=val, parsed=val)
    except ValidationError:
        exit_with_error(
            f"Invalid value for 'IP address or range': {val!r} is not a valid"
            " IP address or CIDR range."
        )


@ip_allowlist_app.command(name="enable")
@with_cli_exception_handling
async def ip_allowlist_enable():
    """Enable the IP allowlist for your account. When enabled, if the allowlist is non-empty, then access to your Prefect Cloud account will be restricted to only those IP addresses on the allowlist."""
    from prefect.cli._prompts import confirm
    from prefect.client.cloud import get_cloud_client

    enforcing_ip_allowlist = await _check_ip_allowlist_access()
    if enforcing_ip_allowlist:
        exit_with_success("IP allowlist is already enabled.")

    async with get_cloud_client(infer_cloud_url=True) as client:
        my_access_if_enabled = await client.check_ip_allowlist_access()
        from prefect.logging import get_logger

        get_logger(__name__).debug(my_access_if_enabled.detail)
        if not my_access_if_enabled.allowed:
            exit_with_error(
                f"Error enabling IP allowlist: {my_access_if_enabled.detail}"
            )

        if not confirm(
            "Enabling the IP allowlist will restrict Prefect Cloud API and UI access to only the IP addresses on the list. "
            "Continue?",
            console=_cli.console,
        ):
            exit_with_error("Aborted.")
        await client.update_account_settings({"enforce_ip_allowlist": True})

    exit_with_success("IP allowlist enabled.")


@ip_allowlist_app.command(name="disable")
@with_cli_exception_handling
async def ip_allowlist_disable():
    """Disable the IP allowlist for your account. When disabled, all IP addresses will be allowed to access your Prefect Cloud account."""
    from prefect.client.cloud import get_cloud_client

    await _check_ip_allowlist_access()

    async with get_cloud_client(infer_cloud_url=True) as client:
        await client.update_account_settings({"enforce_ip_allowlist": False})

    exit_with_success("IP allowlist disabled.")


@ip_allowlist_app.command(name="ls")
@with_cli_exception_handling
async def ip_allowlist_ls():
    """Fetch and list all IP allowlist entries in your account."""
    from prefect.client.cloud import get_cloud_client

    enforcing_ip_allowlist = await _check_ip_allowlist_access()

    async with get_cloud_client(infer_cloud_url=True) as client:
        ip_allowlist = await client.read_account_ip_allowlist()
        _print_ip_allowlist_table(ip_allowlist, enabled=enforcing_ip_allowlist)


@ip_allowlist_app.command(name="add")
@with_cli_exception_handling
async def ip_allowlist_add(
    ip_address_or_range: Annotated[
        str,
        cyclopts.Parameter(
            help="An IP address or range in CIDR notation. E.g. 192.168.1.0 or 192.168.1.0/24",
        ),
    ],
    *,
    description: Annotated[
        str | None,
        cyclopts.Parameter(
            "--description",
            alias="-d",
            help="A short description to annotate the entry with.",
        ),
    ] = None,
):
    """Add a new IP entry to your account IP allowlist."""
    from prefect.cli._prompts import confirm
    from prefect.client.cloud import get_cloud_client
    from prefect.client.schemas.objects import IPAllowlistEntry
    from prefect.exceptions import PrefectHTTPStatusError

    ip_arg = _parse_ip_network(ip_address_or_range)
    enforcing_ip_allowlist = await _check_ip_allowlist_access()

    new_entry = IPAllowlistEntry(
        ip_network=ip_arg.parsed, description=description, enabled=True
    )

    async with get_cloud_client(infer_cloud_url=True) as client:
        ip_allowlist = await client.read_account_ip_allowlist()

        existing_entry_with_same_ip = None
        for entry in ip_allowlist.entries:
            if entry.ip_network == ip_arg.parsed:
                existing_entry_with_same_ip = entry
                break

        if existing_entry_with_same_ip:
            if not confirm(
                f"There's already an entry for this IP ({ip_arg.raw}). Do you want to overwrite it?",
                console=_cli.console,
            ):
                exit_with_error("Aborted.")
            ip_allowlist.entries.remove(existing_entry_with_same_ip)

        ip_allowlist.entries.append(new_entry)

        try:
            await client.update_account_ip_allowlist(ip_allowlist)
        except PrefectHTTPStatusError as exc:
            _handle_update_error(exc)

        updated_ip_allowlist = await client.read_account_ip_allowlist()
        _print_ip_allowlist_table(updated_ip_allowlist, enabled=enforcing_ip_allowlist)


@ip_allowlist_app.command(name="remove")
@with_cli_exception_handling
async def ip_allowlist_remove(
    ip_address_or_range: Annotated[
        str,
        cyclopts.Parameter(
            help="An IP address or range in CIDR notation. E.g. 192.168.1.0 or 192.168.1.0/24",
        ),
    ],
):
    """Remove an IP entry from your account IP allowlist."""
    from prefect.client.cloud import get_cloud_client
    from prefect.exceptions import PrefectHTTPStatusError

    ip_arg = _parse_ip_network(ip_address_or_range)
    enforcing_ip_allowlist = await _check_ip_allowlist_access()

    async with get_cloud_client(infer_cloud_url=True) as client:
        ip_allowlist = await client.read_account_ip_allowlist()
        ip_allowlist.entries = [
            entry for entry in ip_allowlist.entries if entry.ip_network != ip_arg.parsed
        ]

        try:
            await client.update_account_ip_allowlist(ip_allowlist)
        except PrefectHTTPStatusError as exc:
            _handle_update_error(exc)

        updated_ip_allowlist = await client.read_account_ip_allowlist()
        _print_ip_allowlist_table(updated_ip_allowlist, enabled=enforcing_ip_allowlist)


@ip_allowlist_app.command(name="toggle")
@with_cli_exception_handling
async def ip_allowlist_toggle(
    ip_address_or_range: Annotated[
        str,
        cyclopts.Parameter(
            help="An IP address or range in CIDR notation. E.g. 192.168.1.0 or 192.168.1.0/24",
        ),
    ],
):
    """Toggle the enabled status of an individual IP entry in your account IP allowlist."""
    from prefect.client.cloud import get_cloud_client
    from prefect.exceptions import PrefectHTTPStatusError

    ip_arg = _parse_ip_network(ip_address_or_range)
    enforcing_ip_allowlist = await _check_ip_allowlist_access()

    async with get_cloud_client(infer_cloud_url=True) as client:
        ip_allowlist = await client.read_account_ip_allowlist()

        found_matching_entry = False
        for entry in ip_allowlist.entries:
            if entry.ip_network == ip_arg.parsed:
                entry.enabled = not entry.enabled
                found_matching_entry = True
                break

        if not found_matching_entry:
            exit_with_error(f"No entry found with IP address `{ip_arg.raw}`.")

        try:
            await client.update_account_ip_allowlist(ip_allowlist)
        except PrefectHTTPStatusError as exc:
            _handle_update_error(exc)

        updated_ip_allowlist = await client.read_account_ip_allowlist()
        _print_ip_allowlist_table(updated_ip_allowlist, enabled=enforcing_ip_allowlist)


# =====================================================================
# cloud asset
# =====================================================================


@asset_app.command(name="ls")
@with_cli_exception_handling
async def asset_ls(
    *,
    prefix: Annotated[
        str | None,
        cyclopts.Parameter("--prefix", alias="-p", help="Filter assets by key prefix"),
    ] = None,
    search: Annotated[
        str | None,
        cyclopts.Parameter(
            "--search", alias="-s", help="Filter assets by key substring"
        ),
    ] = None,
    limit: Annotated[
        int,
        cyclopts.Parameter(
            "--limit",
            alias="-l",
            help="Maximum number of assets to return (default 50, max 200)",
        ),
    ] = 50,
    output: Annotated[
        str | None,
        cyclopts.Parameter(
            "--output", alias="-o", help="Output format. Supports: json"
        ),
    ] = None,
):
    """List assets in the current workspace."""
    import orjson

    from prefect.client.cloud import get_cloud_client
    from prefect.settings import get_current_settings

    confirm_logged_in(console=_cli.console)

    if output and output.lower() != "json":
        exit_with_error("Only 'json' output format is supported.")

    if limit < 1 or limit > 200:
        exit_with_error("Limit must be between 1 and 200.")

    key_filter: dict[str, list[str]] = {}
    if prefix:
        key_filter["prefix"] = [prefix]
    if search:
        key_filter["search"] = [search]

    body: dict[str, object] = {"limit": limit}
    if key_filter:
        body["filter"] = {"key": key_filter}

    async with get_cloud_client(host=get_current_settings().api.url) as client:
        response = await client.request("POST", "/assets/filter", json=body)

    assets = response.get("assets", [])
    total = response.get("total", len(assets))

    if output and output.lower() == "json":
        json_output = orjson.dumps(assets, option=orjson.OPT_INDENT_2).decode()
        _cli.console.print(json_output)
    else:
        if not assets:
            _cli.console.print("No assets found in this workspace.")
            return

        table = Table(
            title="Assets",
            show_header=True,
        )

        table.add_column("Key", style="blue", no_wrap=False)
        table.add_column("Last Seen", style="cyan", no_wrap=True)

        for asset in sorted(assets, key=lambda x: x.get("key", "")):
            table.add_row(
                asset.get("key", ""),
                asset.get("last_seen", ""),
            )

        _cli.console.print(table)
        _cli.console.print(f"\nShowing {len(assets)} of {total} asset(s)")


@asset_app.command(name="delete")
@with_cli_exception_handling
async def asset_delete(
    key: Annotated[str, cyclopts.Parameter(help="The key of the asset to delete")],
    *,
    force: Annotated[
        bool,
        cyclopts.Parameter(
            "--force", alias="-f", negative="", help="Skip confirmation prompt"
        ),
    ] = False,
):
    """Delete an asset by its key.

    The key should be the full asset URI (e.g., 's3://bucket/data.csv').
    """
    from prefect.cli._prompts import confirm
    from prefect.client.cloud import get_cloud_client
    from prefect.exceptions import ObjectNotFound
    from prefect.settings import get_current_settings

    confirm_logged_in(console=_cli.console)

    if _cli.is_interactive() and not force:
        if not confirm(
            f"Are you sure you want to delete asset {key!r}?",
            default=False,
            console=_cli.console,
        ):
            exit_with_error("Deletion aborted.")

    async with get_cloud_client(host=get_current_settings().api.url) as client:
        try:
            await client.request("DELETE", "/assets/key", params={"key": key})
        except ObjectNotFound:
            exit_with_error(f"Asset {key!r} not found.")

    exit_with_success(f"Deleted asset {key!r}.")
