"""
Command line interface for working with profiles.
"""
import os
import textwrap
from typing import Optional

import httpx
import typer
from fastapi import status
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

import prefect.context
import prefect.settings
from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.cloud import CloudUnauthorizedError, get_cloud_client
from prefect.cli.root import app
from prefect.client import get_client
from prefect.context import use_profile

profile_app = PrefectTyper(
    name="profile", help="Commands for interacting with your Prefect profiles."
)
app.add_typer(profile_app, aliases=["profiles"])


@profile_app.command()
def ls():
    """
    List profile names.
    """
    profiles = prefect.settings.load_profiles()
    current_profile = prefect.context.get_settings_context().profile
    current_name = current_profile.name if current_profile is not None else None

    table = Table(caption="* active profile")
    table.add_column(
        "[#024dfd]Available Profiles:", justify="right", style="#8ea0ae", no_wrap=True
    )

    for name in profiles:
        if name == current_name:
            table.add_row(f"[green]  * {name}[/green]")
        else:
            table.add_row(f"  {name}")
    app.console.print(table)


@profile_app.command()
def create(
    name: str,
    from_name: str = typer.Option(None, "--from", help="Copy an existing profile."),
):
    """
    Create a new profile.
    """

    profiles = prefect.settings.load_profiles()
    if name in profiles:
        app.console.print(
            textwrap.dedent(
                f"""
                [red]Profile {name!r} already exists.[/red]
                To create a new profile, remove the existing profile first:

                    prefect profile delete {name!r}
                """
            ).strip()
        )
        raise typer.Exit(1)

    if from_name:
        if from_name not in profiles:
            exit_with_error(f"Profile {from_name!r} not found.")

        # Create a copy of the profile with a new name and add to the collection
        profiles.add_profile(profiles[from_name].copy(update={"name": name}))
    else:
        profiles.add_profile(prefect.settings.Profile(name=name, settings={}))

    prefect.settings.save_profiles(profiles)

    app.console.print(
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


async def check_orion_connection(profile_name):
    with use_profile(profile_name, include_current_context=False):
        httpx_settings = dict(timeout=3)
        try:
            # attempt to infer Cloud 2.0 API from the connection URL
            cloud_client = get_cloud_client(
                httpx_settings=httpx_settings, infer_cloud_url=True
            )
            res = await cloud_client.api_healthcheck()
            exit_method, msg = (
                exit_with_success,
                f"Connected to Prefect Cloud using profile {profile_name!r}",
            )
        except CloudUnauthorizedError:
            # if the Cloud 2.0 API exists and fails to authenticate, notify the user
            exit_method, msg = (
                exit_with_error,
                f"Error authenticating with Prefect Cloud using profile {profile_name!r}",
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == status.HTTP_404_NOT_FOUND:
                # if the route does not exist, attmpt to connect as a hosted Orion instance
                try:
                    # inform the user if Prefect Orion endpoints exist, but there are
                    # connection issues
                    client = get_client(httpx_settings=httpx_settings)
                    connect_error = await client.api_healthcheck()
                    if connect_error is not None:
                        exit_method, msg = (
                            exit_with_error,
                            f"Error connecting to Prefect Orion using profile {profile_name!r}",
                        )
                    elif await client.using_ephemeral_app():
                        # if the client is using an ephemeral Orion app, inform the user
                        exit_method, msg = (
                            exit_with_success,
                            f"No Prefect Orion instance specified using profile {profile_name!r}. "
                            f"Flow run metadata will be stored at the locally configured database: {prefect.settings.PREFECT_ORION_DATABASE_CONNECTION_URL.value()}",
                        )
                    else:
                        exit_method, msg = (
                            exit_with_success,
                            f"Connected to Prefect Orion using profile {profile_name!r}",
                        )
                except Exception as exc:
                    exit_method, msg = (
                        exit_with_error,
                        f"Error connecting to Prefect Orion using profile {profile_name!r}",
                    )
            else:
                exit_method, msg = (
                    exit_with_error,
                    f"Error connecting to Prefect Cloud: {exc!r}",
                )
        except TypeError:
            # if no Prefect Orion API URL has been set, httpx will throw a TypeError
            try:
                # try to connect with the client anyway, it will likely use an
                # ephemeral Orion instance
                client = get_client(httpx_settings=httpx_settings)
                connect_error = await client.api_healthcheck()
                if connect_error is not None:
                    exit_method, msg = (
                        exit_with_error,
                        f"Error connecting to Prefect Orion using profile {profile_name!r}",
                    )
                elif await client.using_ephemeral_app():
                    exit_method, msg = (
                        exit_with_success,
                        f"No Prefect Orion instance specified using profile {profile_name!r}. "
                        f"Flow run metadata will be stored at the locally configured database: {prefect.settings.PREFECT_ORION_DATABASE_CONNECTION_URL.value()}",
                    )
                else:
                    exit_method, msg = (
                        exit_with_success,
                        f"Connected to Prefect Orion using profile {profile_name!r}",
                    )
            except Exception as exc:
                exit_method, msg = (
                    exit_with_error,
                    f"Error connecting to Prefect Orion using profile {profile_name!r}",
                )
        except (httpx.ConnectError, httpx.UnsupportedProtocol) as exc:
            exit_method, msg = exit_with_error, "Invalid Prefect API URL"

    return exit_method, msg


@profile_app.command()
async def use(name: str):
    """
    Set the given profile to active.
    """
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
            description="Connecting...",
            total=None,
        )
        exit_method, msg = await check_orion_connection(name)

    exit_method(msg)


@profile_app.command()
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
            f"Profile {name!r} is the active profile. You must switch profiles before it can be deleted."
        )

    profiles.remove_profile(name)

    verb = "Removed"
    if name == "default":
        verb = "Reset"

    prefect.settings.save_profiles(profiles)
    exit_with_success(f"{verb} profile {name!r}.")


@profile_app.command()
def rename(name: str, new_name: str):
    """
    Change the name of a profile.
    """
    profiles = prefect.settings.load_profiles()
    if name not in profiles:
        exit_with_error(f"Profile {name!r} not found.")

    if new_name in profiles:
        exit_with_error(f"Profile {new_name!r} already exists.")

    profiles.add_profile(profiles[name].copy(update={"name": new_name}))
    profiles.remove_profile(name)

    # If the active profile was renamed switch the active profile to the new name.
    context_profile = prefect.context.get_settings_context().profile
    if profiles.active_name == name:
        profiles.set_active(new_name)
    if os.environ.get("PREFECT_PROFILE") == name:
        app.console.print(
            f"You have set your current profile to {name!r} with the "
            "PREFECT_PROFILE environment variable. You must update this variable to "
            f"{new_name!r} to continue using the profile."
        )

    prefect.settings.save_profiles(profiles)
    exit_with_success(f"Renamed profile {name!r} to {new_name!r}.")


@profile_app.command()
def inspect(
    name: Optional[str] = typer.Argument(
        None, help="Name of profile to inspect; defaults to active profile."
    )
):
    """
    Display settings from a given profile; defaults to active.
    """
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
        # TODO: Consider instructing on how to add settings.
        print(f"Profile {name!r} is empty.")

    for setting, value in profiles[name].settings.items():
        app.console.print(f"{setting.name}='{value}'")
