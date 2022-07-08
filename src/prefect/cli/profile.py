"""
Command line interface for working with profiles.
"""
import textwrap
from typing import Optional

import typer

import prefect.context
import prefect.settings
from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.root import app

profile_app = PrefectTyper(
    name="profile", help="Commands for interacting with your Prefect profiles."
)
app.add_typer(profile_app)


@profile_app.command()
def ls():
    """
    List profile names.
    """
    profiles = prefect.settings.load_profiles()
    current_profile = prefect.context.get_settings_context().profile
    current_name = current_profile.name if current_profile is not None else None

    for name in profiles:
        if name == current_name:
            app.console.print(f"* {name}")
        else:
            app.console.print(name)


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

        from_blurb = f" matching {from_name!r}"
    else:
        from_blurb = ""
        profiles.add_profile(prefect.settings.Profile(name=name, settings={}))

    prefect.settings.save_profiles(profiles)

    app.console.print(
        textwrap.dedent(
            f"""
            [green]Created profile {name!r}{from_blurb}.[/green]

            Switch to your new profile with:

                prefect profile use {name!r}

            Or, to use it for a single command, include the `-p` option:

                prefect -p {name!r} config view
            """
        ).strip()
    )


@profile_app.command()
def use(name: str):
    """
    Set the given profile to active.
    """
    profiles = prefect.settings.load_profiles()
    if name not in profiles.names:
        exit_with_error(f"Profile {name!r} not found.")

    profiles.set_active(name)
    prefect.settings.save_profiles(profiles)
    exit_with_success(f"Profile {name!r} now active.")


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
