"""
Profile command — native cyclopts implementation.

Manages Prefect profiles.
"""

import os
import shutil
import textwrap
from typing import Annotated, Optional

import cyclopts
import orjson
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm
from rich.table import Table

import prefect.cli._app as _cli
import prefect.context
import prefect.settings
from prefect.cli._utilities import (
    exit_with_error,
    exit_with_success,
    with_cli_exception_handling,
)
from prefect.context import use_profile
from prefect.settings import ProfilesCollection
from prefect.settings.profiles import _read_profiles_from, _write_profiles_to
from prefect.utilities.collections import AutoEnum

profile_app: cyclopts.App = cyclopts.App(
    name="profile", alias="profiles", help="Select and manage Prefect profiles."
)


@profile_app.command()
@with_cli_exception_handling
def ls():
    """
    List profile names.
    """
    profiles = prefect.settings.load_profiles(include_defaults=False)
    current_profile = prefect.context.get_settings_context().profile
    current_name = current_profile.name if current_profile is not None else None

    table = Table(caption="* active profile")
    table.add_column(
        "[#024dfd]Available Profiles:",
        justify="right",
        style="#8ea0ae",
        no_wrap=True,
    )

    for name in profiles:
        if name == current_name:
            table.add_row(f"[green]  * {name}[/green]")
        else:
            table.add_row(f"  {name}")
    _cli.console.print(table)


@profile_app.command()
@with_cli_exception_handling
def create(
    name: str,
    *,
    from_name: Annotated[
        Optional[str],
        cyclopts.Parameter("--from", help="Copy an existing profile."),
    ] = None,
):
    """
    Create a new profile.
    """
    profiles = prefect.settings.load_profiles(include_defaults=False)
    if name in profiles:
        _cli.console.print(
            textwrap.dedent(
                f"""
                [red]Profile {name!r} already exists.[/red]
                To create a new profile, remove the existing profile first:

                    prefect profile delete {name!r}
                """
            ).strip()
        )
        raise SystemExit(1)

    if from_name:
        if from_name not in profiles:
            exit_with_error(f"Profile {from_name!r} not found.")

        profiles.add_profile(profiles[from_name].model_copy(update={"name": name}))
    else:
        profiles.add_profile(prefect.settings.Profile(name=name, settings={}))

    prefect.settings.save_profiles(profiles)

    _cli.console.print(
        textwrap.dedent(
            f"""
            Created profile with properties:
                name - {name!r}
                from name - {from_name or None}

            Use created profile for future, subsequent commands:
                prefect profile use {name!r}

            Use created profile temporarily for a single command:
                prefect -p {name!r} config view
            """
        )
    )


@profile_app.command()
@with_cli_exception_handling
async def use(name: str):
    """
    Set the given profile to active.
    """
    status_messages = {
        ConnectionStatus.CLOUD_CONNECTED: (
            exit_with_success,
            f"Connected to Prefect Cloud using profile {name!r}",
        ),
        ConnectionStatus.CLOUD_ERROR: (
            exit_with_error,
            f"Error connecting to Prefect Cloud using profile {name!r}",
        ),
        ConnectionStatus.CLOUD_UNAUTHORIZED: (
            exit_with_error,
            f"Error authenticating with Prefect Cloud using profile {name!r}",
        ),
        ConnectionStatus.SERVER_CONNECTED: (
            exit_with_success,
            f"Connected to Prefect server using profile {name!r}",
        ),
        ConnectionStatus.SERVER_ERROR: (
            exit_with_error,
            f"Error connecting to Prefect server using profile {name!r}",
        ),
        ConnectionStatus.EPHEMERAL: (
            exit_with_success,
            (
                f"No Prefect server specified using profile {name!r} - the API will run"
                " in ephemeral mode."
            ),
        ),
        ConnectionStatus.UNCONFIGURED: (
            exit_with_error,
            (
                f"Prefect server URL not configured using profile {name!r} - please"
                " configure the server URL or enable ephemeral mode."
            ),
        ),
        ConnectionStatus.INVALID_API: (
            exit_with_error,
            "Error connecting to Prefect API URL",
        ),
    }

    profiles = prefect.settings.load_profiles()
    if name not in profiles.names:
        exit_with_error(f"Profile {name!r} not found.")

    profiles.set_active(name)
    prefect.settings.save_profiles(profiles)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=False,
    ) as progress:
        progress.add_task(
            description="Checking API connectivity...",
            total=None,
        )

        with use_profile(name, include_current_context=False):
            connection_status = await check_server_connection()

        exit_method, msg = status_messages[connection_status]

    exit_method(msg)


@profile_app.command()
@with_cli_exception_handling
def delete(name: str):
    """
    Delete the given profile.
    """
    profiles = prefect.settings.load_profiles()
    if name not in profiles:
        exit_with_error(f"Profile {name!r} not found.")

    current_profile = prefect.context.get_settings_context().profile
    if current_profile.name == name:
        exit_with_error(
            f"Profile {name!r} is the active profile. You must switch profiles before"
            " it can be deleted."
        )
    if _cli.is_interactive():
        if not Confirm.ask(
            f"Are you sure you want to delete profile with name {name!r}?",
            console=_cli.console,
            default=False,
        ):
            exit_with_error("Deletion aborted.")

    profiles.remove_profile(name)
    prefect.settings.save_profiles(profiles)
    exit_with_success(f"Removed profile {name!r}.")


@profile_app.command()
@with_cli_exception_handling
def rename(name: str, new_name: str):
    """
    Change the name of a profile.
    """
    profiles = prefect.settings.load_profiles(include_defaults=False)
    if name not in profiles:
        exit_with_error(f"Profile {name!r} not found.")

    if new_name in profiles:
        exit_with_error(f"Profile {new_name!r} already exists.")

    profiles.add_profile(profiles[name].model_copy(update={"name": new_name}))
    profiles.remove_profile(name)

    prefect.context.get_settings_context().profile
    if profiles.active_name == name:
        profiles.set_active(new_name)
    if os.environ.get("PREFECT_PROFILE") == name:
        _cli.console.print(
            f"You have set your current profile to {name!r} with the "
            "PREFECT_PROFILE environment variable. You must update this variable to "
            f"{new_name!r} to continue using the profile."
        )

    prefect.settings.save_profiles(profiles)
    exit_with_success(f"Renamed profile {name!r} to {new_name!r}.")


@profile_app.command()
@with_cli_exception_handling
def inspect(
    name: Annotated[
        Optional[str],
        cyclopts.Parameter(help="Name of profile to inspect; defaults to active."),
    ] = None,
    *,
    output: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--output",
            alias="-o",
            help="Specify an output format. Currently supports: json",
        ),
    ] = None,
):
    """
    Display settings from a given profile; defaults to active.
    """
    if output and output.lower() != "json":
        exit_with_error("Only 'json' output format is supported.")

    profiles = prefect.settings.load_profiles()
    if name is None:
        current_profile = prefect.context.get_settings_context().profile
        if not current_profile:
            exit_with_error("No active profile set - please provide a name to inspect.")
        name = current_profile.name
        print(f"No name provided, defaulting to {name!r}")
    if name not in profiles:
        exit_with_error(f"Profile {name!r} not found.")

    if not profiles[name].settings:
        if output and output.lower() == "json":
            _cli.console.print("{}")
        else:
            print(f"Profile {name!r} is empty.")
        return

    if output and output.lower() == "json":
        profile_data = {
            setting.name: value for setting, value in profiles[name].settings.items()
        }
        json_output = orjson.dumps(profile_data, option=orjson.OPT_INDENT_2).decode()
        _cli.console.print(json_output)
    else:
        for setting, value in profiles[name].settings.items():
            _cli.console.print(f"{setting.name}='{value}'")


@profile_app.command(name="populate-defaults")
@with_cli_exception_handling
def populate_defaults():
    """
    Populate the profiles configuration with default base profiles,
    preserving existing user profiles.
    """
    user_path = prefect.settings.PREFECT_PROFILES_PATH.value()
    default_profiles = _read_profiles_from(prefect.settings.DEFAULT_PROFILES_PATH)

    if user_path.exists():
        user_profiles = _read_profiles_from(user_path)

        if not _show_profile_changes(user_profiles, default_profiles):
            return

        if _cli.is_interactive():
            if Confirm.ask(
                f"\nBack up existing profiles to {user_path}.bak?",
                console=_cli.console,
            ):
                shutil.copy(user_path, f"{user_path}.bak")
                _cli.console.print(f"Profiles backed up to {user_path}.bak")
    else:
        user_profiles = ProfilesCollection([])
        _cli.console.print(
            "\n[bold]Creating new profiles file with default profiles.[/bold]"
        )
        _show_profile_changes(user_profiles, default_profiles)

    if _cli.is_interactive():
        if not Confirm.ask(
            f"\nUpdate profiles at {user_path}?",
            console=_cli.console,
        ):
            _cli.console.print("Operation cancelled.")
            return

    for name, profile in default_profiles.items():
        if name not in user_profiles:
            user_profiles.add_profile(profile)

    _write_profiles_to(user_path, user_profiles)
    _cli.console.print(f"\nProfiles updated in [green]{user_path}[/green]")
    _cli.console.print(
        "\nUse with [green]prefect profile use[/green] [blue][PROFILE-NAME][/blue]"
    )
    _cli.console.print("\nAvailable profiles:")
    for name in user_profiles.names:
        _cli.console.print(f"  - {name}")


def _show_profile_changes(
    user_profiles: ProfilesCollection, default_profiles: ProfilesCollection
) -> bool:
    """Show proposed profile changes and return True if there are any."""
    changes: list[tuple[str, str]] = []

    for name in default_profiles.names:
        if name not in user_profiles:
            changes.append(("add", name))

    if not changes:
        _cli.console.print(
            "[green]No changes needed. All profiles are up to date.[/green]"
        )
        return False

    _cli.console.print("\n[bold cyan]Proposed Changes:[/bold cyan]")
    for change in changes:
        if change[0] == "add":
            _cli.console.print(f"  [blue]\u2022[/blue] Add '{change[1]}'")

    return True


# Re-export for backwards compatibility (tests import show_profile_changes)
show_profile_changes = _show_profile_changes


class ConnectionStatus(AutoEnum):
    CLOUD_CONNECTED = AutoEnum.auto()
    CLOUD_ERROR = AutoEnum.auto()
    CLOUD_UNAUTHORIZED = AutoEnum.auto()
    SERVER_CONNECTED = AutoEnum.auto()
    SERVER_ERROR = AutoEnum.auto()
    UNCONFIGURED = AutoEnum.auto()
    EPHEMERAL = AutoEnum.auto()
    INVALID_API = AutoEnum.auto()


async def check_server_connection() -> ConnectionStatus:
    import httpx

    from prefect.client.base import determine_server_type
    from prefect.client.cloud import CloudUnauthorizedError, get_cloud_client
    from prefect.client.orchestration import ServerType, get_client

    httpx_settings = dict(timeout=3)
    try:
        server_type = determine_server_type()

        if server_type == ServerType.CLOUD:
            try:
                cloud_client = get_cloud_client(
                    httpx_settings=httpx_settings, infer_cloud_url=True
                )
                async with cloud_client:
                    await cloud_client.api_healthcheck()
                return ConnectionStatus.CLOUD_CONNECTED
            except CloudUnauthorizedError:
                return ConnectionStatus.CLOUD_UNAUTHORIZED
            except (httpx.HTTPStatusError, Exception):
                return ConnectionStatus.CLOUD_ERROR

        if server_type == ServerType.EPHEMERAL:
            return ConnectionStatus.EPHEMERAL
        elif server_type == ServerType.UNCONFIGURED:
            return ConnectionStatus.UNCONFIGURED

        try:
            client = get_client(httpx_settings=httpx_settings)
            async with client:
                connect_error = await client.api_healthcheck()
            if connect_error is not None:
                return ConnectionStatus.SERVER_ERROR
            else:
                return ConnectionStatus.SERVER_CONNECTED
        except Exception:
            return ConnectionStatus.SERVER_ERROR
    except TypeError:
        try:
            server_type = determine_server_type()
            if server_type == ServerType.EPHEMERAL:
                return ConnectionStatus.EPHEMERAL
            elif server_type == ServerType.UNCONFIGURED:
                return ConnectionStatus.UNCONFIGURED
            client = get_client(httpx_settings=httpx_settings)
            if client.server_type == ServerType.EPHEMERAL:
                return ConnectionStatus.EPHEMERAL
            async with client:
                connect_error = await client.api_healthcheck()
            if connect_error is not None:
                return ConnectionStatus.SERVER_ERROR
            else:
                return ConnectionStatus.SERVER_CONNECTED
        except Exception:
            return ConnectionStatus.SERVER_ERROR
    except (httpx.ConnectError, httpx.UnsupportedProtocol):
        return ConnectionStatus.INVALID_API
