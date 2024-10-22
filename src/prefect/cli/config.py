"""
Command line interface for working with profiles
"""

import os
from typing import Any, Dict, List, Optional

import typer
from dotenv import dotenv_values
from typing_extensions import Literal

import prefect.context
import prefect.settings
from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.root import app, is_interactive
from prefect.exceptions import ProfileSettingsValidationError
from prefect.settings.legacy import _get_settings_fields, _get_valid_setting_names
from prefect.utilities.collections import listrepr

help_message = """
    View and set Prefect profiles.
"""
VALID_SETTING_NAMES = _get_valid_setting_names(prefect.settings.Settings)
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
def unset(setting_names: List[str], confirm: bool = typer.Option(False, "--yes", "-y")):
    """
    Restore the default value for a setting.

    Removes the setting from the current profile.
    """
    settings_context = prefect.context.get_settings_context()
    profiles = prefect.settings.load_profiles()
    profile = profiles[settings_context.profile.name]
    parsed = set()

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

    settings_output = []
    processed_settings = set()

    def _process_setting(
        setting: prefect.settings.Setting,
        value: str,
        source: Literal["env", "profile", "defaults", ".env file"],
    ):
        display_value = "********" if setting.is_secret and not show_secrets else value
        source_blurb = f" (from {source})" if show_sources else ""
        settings_output.append(f"{setting.name}='{display_value}'{source_blurb}")
        processed_settings.add(setting.name)

    def _collect_defaults(default_values: Dict[str, Any], current_path: List[str]):
        for key, value in default_values.items():
            if isinstance(value, dict):
                _collect_defaults(value, current_path + [key])
            else:
                setting = _get_settings_fields(prefect.settings.Settings)[
                    ".".join(current_path + [key])
                ]
                if setting.name in processed_settings:
                    continue
                _process_setting(setting, value, "defaults")

    # Process settings from the current profile
    for setting, value in current_profile_settings.items():
        value_and_source = (
            (value, "profile")
            if not (env_value := os.getenv(setting.name))
            else (env_value, "env")
        )
        _process_setting(setting, value_and_source[0], value_and_source[1])

    for setting_name in VALID_SETTING_NAMES:
        setting = _get_settings_fields(prefect.settings.Settings)[setting_name]
        if setting.name in processed_settings:
            continue
        if (env_value := os.getenv(setting.name)) is None:
            continue
        _process_setting(setting, env_value, "env")
    for key, value in dotenv_values().items():
        if key in VALID_SETTING_NAMES:
            setting = _get_settings_fields(prefect.settings.Settings)[key]
            if setting.name in processed_settings or value is None:
                continue
            _process_setting(setting, value, ".env file")
    if show_defaults:
        _collect_defaults(
            prefect.settings.Settings().model_dump(context=dump_context),
            current_path=[],
        )

    app.console.print("\n".join(sorted(settings_output)), soft_wrap=True)
