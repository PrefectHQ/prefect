"""
Command line interface for working with profiles
"""
import os
from typing import List, Optional

import typer

import prefect.context
import prefect.settings
from prefect.cli.base import (
    PrefectTyper,
    app,
    console,
    exit_with_error,
    exit_with_success,
)

help_message = """
    Commands for interacting with Prefect settings.
"""

config_app = PrefectTyper(name="config", help=help_message)
app.add_typer(config_app)


@config_app.command()
def set(variables: List[str]):
    """
    Change the value for a setting.

    Sets the value in the current profile.
    """
    profiles = prefect.settings.load_profiles()
    profile = prefect.context.get_profile_context()
    env = profiles[profile.name]

    parsed_variables = []
    for variable in variables:
        try:
            var, value = variable.split("=")
        except ValueError:
            exit_with_error(
                f"Failed to parse argument {variable!r}. Use the format 'VAR=VAL'."
            )

        parsed_variables.append((var, value))

    for var, value in parsed_variables:
        env[var] = value
        console.print(f"Set variable {var!r} to {value!r}")

    for var, _ in parsed_variables:
        if var in os.environ:
            console.print(
                f"[yellow]{var} is also set by an environment variable which will "
                f"override your config value. Run `unset {var}` to clear it."
            )

    prefect.settings.write_profiles(profiles)
    exit_with_success(f"Updated profile {profile.name!r}")


@config_app.command()
def unset(variables: List[str]):
    """
    Restore the default value for a setting.

    Removes the setting from the current profile.
    """
    profiles = prefect.settings.load_profiles()
    profile = prefect.context.get_profile_context()
    env = profiles[profile.name]

    for var in variables:
        if var not in env:
            exit_with_error(f"Variable {var!r} not found in profile {profile.name!r}.")
        env.pop(var)

    for var in variables:
        console.print(f"Unset variable {var!r}")

        if var in os.environ:
            console.print(
                f"[yellow]{var} is also set by an environment variable. "
                f"Use `unset {var}` to clear it."
            )

    prefect.settings.write_profiles(profiles)
    exit_with_success(f"Updated profile {profile.name!r}")


show_defaults_help = """
Toggle display of default settings.

--show-defaults displays all settings,
even if they are not changed from the
default values.

--hide-defaults displays only settings
that are changed from default values.

"""

show_sources_help = """
Toggle display of the source of a value for
a setting. 

The value for a setting can come from the 
current profile, environment variables, or 
the defaults.

"""


@config_app.command()
def view(
    show_defaults: Optional[bool] = typer.Option(
        False, "--show-defaults/--hide-defaults", help=(show_defaults_help)
    ),
    show_sources: Optional[bool] = typer.Option(
        True,
        "--show-sources/--hide-sources",
        help=(show_sources_help),
    ),
):
    """
    Display the current settings.
    """
    profile = prefect.context.get_profile_context()

    # Get settings at each level, converted to a flat dictionary for easy comparison
    default_settings = prefect.settings.get_default_settings().dict()
    env_settings = prefect.settings.get_settings_from_env().dict()
    current_profile_settings = profile.settings.dict()

    output = [f"PREFECT_PROFILE={profile.name!r}"]

    # The combination of environment variables and profile settings that are in use
    profile_overrides = {
        key: val
        for key, val in current_profile_settings.items()
        if val != default_settings[key]
    }

    # Used to see which settings in current_profile_settings came from env vars
    env_overrides = {
        key: val for key, val in env_settings.items() if val != default_settings[key]
    }

    for key, value in profile_overrides.items():
        source = "env" if env_overrides.get(key) is not None else "profile"
        source_blurb = f" (from {source})" if show_sources else ""
        output.append(f"{key}='{value}'{source_blurb}")

    if show_defaults:
        for key, value in sorted(default_settings.items()):
            source_blurb = " (from defaults)" if show_sources else ""
            output.append(f"{key}='{value}'{source_blurb}")

    console.print("\n".join(output))
