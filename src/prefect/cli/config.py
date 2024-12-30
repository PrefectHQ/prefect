"""
Command line interface for working with profiles
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Union, cast

import toml
import typer
from dotenv import dotenv_values
from typing_extensions import Literal

import prefect.context
import prefect.settings
from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.root import app, is_interactive
from prefect.exceptions import ProfileSettingsValidationError
from prefect.settings.legacy import (
    Setting,
    _get_settings_fields,  # type: ignore[reportPrivateUsage] Private util that needs to live next to Setting class
    _get_valid_setting_names,  # type: ignore[reportPrivateUsage] Private util that needs to live next to Setting class
)
from prefect.utilities.annotations import NotSet
from prefect.utilities.collections import listrepr

help_message = """
    View and set Prefect profiles.
"""
VALID_SETTING_NAMES = _get_valid_setting_names(prefect.settings.Settings)
config_app: PrefectTyper = PrefectTyper(name="config", help=help_message)
app.add_typer(config_app)


@config_app.command("set")
def set_(settings: list[str]):
    """
    Change the value for a setting by setting the value in the current profile.
    """
    parsed_settings: dict[Union[str, Setting], Any] = {}
    for item in settings:
        try:
            setting, value = item.split("=", maxsplit=1)
        except ValueError:
            exit_with_error(
                f"Failed to parse argument {item!r}. Use the format 'VAR=VAL'."
            )

        if setting not in VALID_SETTING_NAMES:
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
    except ProfileSettingsValidationError as exc:
        help_message = ""
        for setting, problem in exc.errors:
            for error in problem.errors():
                help_message += f"[bold red]Validation error(s) for setting[/bold red] [blue]{setting.name}[/blue]\n\n - {error['msg']}\n\n"
        exit_with_error(help_message)

    for setting, value in parsed_settings.items():
        app.console.print(f"Set {setting!r} to {value!r}.")
        if setting in os.environ:
            app.console.print(
                f"[yellow]{setting} is also set by an environment variable which will "
                f"override your config value. Run `unset {setting}` to clear it."
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

    profile.validate_settings()

    prefect.settings.save_profiles(profiles)
    exit_with_success("Configuration valid!")


@config_app.command()
def unset(setting_names: list[str], confirm: bool = typer.Option(False, "--yes", "-y")):
    """
    Restore the default value for a setting.

    Removes the setting from the current profile.
    """
    settings_context = prefect.context.get_settings_context()
    profiles = prefect.settings.load_profiles()
    profile = profiles[settings_context.profile.name]
    parsed: set[Setting] = set()

    for setting_name in setting_names:
        if setting_name not in VALID_SETTING_NAMES:
            exit_with_error(f"Unknown setting name {setting_name!r}.")
        # Cast to settings objects
        parsed.add(_get_settings_fields(prefect.settings.Settings)[setting_name])

    for setting in parsed:
        if setting not in profile.settings:
            exit_with_error(f"{setting.name!r} is not set in profile {profile.name!r}.")

    if (
        not confirm
        and is_interactive()
        and not typer.confirm(
            f"Are you sure you want to unset the following setting(s): {listrepr(setting_names)}?",
        )
    ):
        exit_with_error("Unset aborted.")

    profiles.update_profile(
        name=profile.name, settings={setting_name: None for setting_name in parsed}
    )

    for setting_name in setting_names:
        app.console.print(f"Unset {setting_name!r}.")

        if setting_name in os.environ:
            app.console.print(
                f"[yellow]{setting_name!r} is also set by an environment variable. "
                f"Use `unset {setting_name}` to clear it."
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
    show_defaults: bool = typer.Option(
        False, "--show-defaults/--hide-defaults", help=(show_defaults_help)
    ),
    show_sources: bool = typer.Option(
        True,
        "--show-sources/--hide-sources",
        help=(show_sources_help),
    ),
    show_secrets: bool = typer.Option(
        False,
        "--show-secrets/--hide-secrets",
        help="Toggle display of secrets setting values.",
    ),
):
    """
    Display the current settings.
    """
    if show_secrets:
        dump_context = dict(include_secrets=True)
    else:
        dump_context = {}

    context = prefect.context.get_settings_context()
    current_profile_settings = context.profile.settings

    if ui_url := prefect.settings.PREFECT_UI_URL.value():
        app.console.print(
            f"🚀 you are connected to:\n[green]{ui_url}[/green]", soft_wrap=True
        )

    # Display the profile first
    app.console.print(f"[bold][blue]PREFECT_PROFILE={context.profile.name!r}[/bold]")

    settings_output: list[str] = []
    processed_settings: set[str] = set()

    def _process_setting(
        setting: prefect.settings.Setting,
        value: str,
        source: Literal[
            "env", "profile", "defaults", ".env file", "prefect.toml", "pyproject.toml"
        ],
    ):
        display_value = "********" if setting.is_secret and not show_secrets else value
        source_blurb = f" (from {source})" if show_sources else ""
        settings_output.append(f"{setting.name}='{display_value}'{source_blurb}")
        processed_settings.add(setting.name)

    def _collect_defaults(default_values: dict[str, Any], current_path: list[str]):
        for key, value in default_values.items():
            if isinstance(value, dict):
                _collect_defaults(cast(dict[str, Any], value), current_path + [key])
            else:
                setting = _get_settings_fields(prefect.settings.Settings)[
                    ".".join(current_path + [key])
                ]
                if setting.name in processed_settings:
                    continue
                _process_setting(setting, value, "defaults")

    def _process_toml_settings(
        settings: dict[str, Any],
        base_path: list[str],
        source: Literal["prefect.toml", "pyproject.toml"],
    ):
        for key, value in settings.items():
            if isinstance(value, dict):
                _process_toml_settings(
                    cast(dict[str, Any], value), base_path + [key], source
                )
            else:
                setting = _get_settings_fields(prefect.settings.Settings).get(
                    ".".join(base_path + [key]), NotSet
                )
                if setting is NotSet:
                    continue
                elif (
                    isinstance(setting, Setting) and setting.name in processed_settings
                ):
                    continue
                elif isinstance(setting, Setting):
                    _process_setting(setting, value, source)

    # Process settings from environment variables
    for setting_name in VALID_SETTING_NAMES:
        setting = _get_settings_fields(prefect.settings.Settings)[setting_name]
        if setting.name in processed_settings:
            continue
        if (env_value := os.getenv(setting.name)) is None:
            continue
        _process_setting(setting, env_value, "env")

    # Process settings from .env file
    for key, value in dotenv_values(".env").items():
        if key in VALID_SETTING_NAMES:
            setting = _get_settings_fields(prefect.settings.Settings)[key]
            if setting.name in processed_settings or value is None:
                continue
            _process_setting(setting, value, ".env file")

    # Process settings from prefect.toml
    if Path("prefect.toml").exists():
        toml_settings = toml.load(Path("prefect.toml"))
        _process_toml_settings(toml_settings, base_path=[], source="prefect.toml")

    # Process settings from pyproject.toml
    if Path("pyproject.toml").exists():
        pyproject_settings = toml.load(Path("pyproject.toml"))
        pyproject_settings = pyproject_settings.get("tool", {}).get("prefect", {})
        _process_toml_settings(
            pyproject_settings, base_path=[], source="pyproject.toml"
        )

    # Process settings from the current profile
    for setting, value in current_profile_settings.items():
        if setting.name not in processed_settings:
            _process_setting(setting, value, "profile")

    if show_defaults:
        _collect_defaults(
            prefect.settings.Settings().model_dump(context=dump_context),
            current_path=[],
        )

    app.console.print("\n".join(sorted(settings_output)), soft_wrap=True)
