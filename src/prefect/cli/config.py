"""
Command line interface for working with profiles
"""

import os
from typing import List, Optional

import pydantic
import typer

import prefect.context
import prefect.settings
from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.root import app, is_interactive

help_message = """
    View and set Prefect profiles.
"""

config_app = PrefectTyper(name="config", help=help_message)
app.add_typer(config_app)


@config_app.command("set")
def set_(settings: List[str]):
    """
    Change the value for a setting by setting the value in the current profile.
    """
    parsed_settings = {}
    for item in settings:
        try:
            setting, value = item.split("=", maxsplit=1)
        except ValueError:
            exit_with_error(
                f"Failed to parse argument {item!r}. Use the format 'VAR=VAL'."
            )

        if setting not in prefect.settings.SETTING_VARIABLES:
            exit_with_error(f"Unknown setting name {setting!r}.")

        # Guard against changing settings that tweak config locations
        if setting in {"PREFECT_HOME", "PREFECT_PROFILES_PATH"}:
            exit_with_error(
                f"Setting {setting!r} cannot be changed with this command. "
                "Use an environment variable instead."
            )

        parsed_settings[setting] = value

    try:
        new_profile = prefect.settings.update_current_profile(parsed_settings)
    except pydantic.ValidationError as exc:
        for error in exc.errors():
            setting = error["loc"][0]
            message = error["msg"]
            app.console.print(f"Validation error for setting {setting!r}: {message}")
        exit_with_error("Invalid setting value.")

    for setting, value in parsed_settings.items():
        app.console.print(f"Set {setting!r} to {value!r}.")
        if setting in os.environ:
            app.console.print(
                f"[yellow]{setting} is also set by an environment variable which will "
                f"override your config value. Run `unset {setting}` to clear it."
            )

        if prefect.settings.SETTING_VARIABLES[setting].deprecated:
            app.console.print(
                f"[yellow]{prefect.settings.SETTING_VARIABLES[setting].deprecated_message}."
            )

    exit_with_success(f"Updated profile {new_profile.name!r}.")


@config_app.command()
def validate():
    """
    Read and validate the current profile.

    Deprecated settings will be automatically converted to new names unless both are
    set.
    """
    profiles = prefect.settings.load_profiles()
    profile = profiles[prefect.context.get_settings_context().profile.name]
    changed = profile.convert_deprecated_renamed_settings()
    for old, new in changed:
        app.console.print(f"Updated {old.name!r} to {new.name!r}.")

    for setting in profile.settings.keys():
        if setting.deprecated:
            app.console.print(f"Found deprecated setting {setting.name!r}.")

    profile.validate_settings()

    prefect.settings.save_profiles(profiles)
    exit_with_success("Configuration valid!")


@config_app.command()
def unset(settings: List[str], confirm: bool = typer.Option(False, "--yes", "-y")):
    """
    Restore the default value for a setting.

    Removes the setting from the current profile.
    """
    profiles = prefect.settings.load_profiles()
    profile = profiles[prefect.context.get_settings_context().profile.name]
    parsed = set()

    for setting in settings:
        if setting not in prefect.settings.SETTING_VARIABLES:
            exit_with_error(f"Unknown setting name {setting!r}.")
        # Cast to settings objects
        parsed.add(prefect.settings.SETTING_VARIABLES[setting])

    for setting in parsed:
        if setting not in profile.settings:
            exit_with_error(f"{setting.name!r} is not set in profile {profile.name!r}.")

    if (
        not confirm
        and is_interactive()
        and not typer.confirm(
            f"Are you sure you want to unset the following settings: {settings!r}?",
        )
    ):
        exit_with_error("Unset aborted.")

    profiles.update_profile(
        name=profile.name, settings={setting: None for setting in parsed}
    )

    for setting in settings:
        app.console.print(f"Unset {setting!r}.")

        if setting in os.environ:
            app.console.print(
                f"[yellow]{setting!r} is also set by an environment variable. "
                f"Use `unset {setting}` to clear it."
            )

    prefect.settings.save_profiles(profiles)
    exit_with_success(f"Updated profile {profile.name!r}.")


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
    show_secrets: Optional[bool] = typer.Option(
        False,
        "--show-secrets/--hide-secrets",
        help="Toggle display of secrets setting values.",
    ),
):
    """
    Display the current settings.
    """
    context = prefect.context.get_settings_context()

    # Get settings at each level, converted to a flat dictionary for easy comparison
    default_settings = prefect.settings.get_default_settings()
    env_settings = prefect.settings.get_settings_from_env()
    current_profile_settings = context.settings

    # Obfuscate secrets
    if not show_secrets:
        default_settings = default_settings.with_obfuscated_secrets()
        env_settings = env_settings.with_obfuscated_secrets()
        current_profile_settings = current_profile_settings.with_obfuscated_secrets()

    # Display the profile first
    app.console.print(f"PREFECT_PROFILE={context.profile.name!r}")

    settings_output = []

    # The combination of environment variables and profile settings that are in use
    profile_overrides = current_profile_settings.model_dump(exclude_unset=True)

    # Used to see which settings in current_profile_settings came from env vars
    env_overrides = env_settings.model_dump(exclude_unset=True)

    for key, value in profile_overrides.items():
        source = "env" if env_overrides.get(key) is not None else "profile"
        source_blurb = f" (from {source})" if show_sources else ""
        settings_output.append(f"{key}='{value}'{source_blurb}")

    if show_defaults:
        for key, value in default_settings.model_dump().items():
            if key not in profile_overrides:
                source_blurb = " (from defaults)" if show_sources else ""
                settings_output.append(f"{key}='{value}'{source_blurb}")

    app.console.print("\n".join(sorted(settings_output)))
