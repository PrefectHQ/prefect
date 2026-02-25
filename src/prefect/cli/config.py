"""
Config command — native cyclopts implementation.

Manages Prefect settings and profiles.
"""

import os
from pathlib import Path
from typing import Annotated, Any, Literal, Union, cast

import cyclopts
from dotenv import dotenv_values

import prefect.cli._app as _cli
import prefect.context
import prefect.settings
from prefect._internal.compatibility.backports import tomllib
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.exceptions import ProfileSettingsValidationError
from prefect.settings import Settings
from prefect.settings.legacy import (
    Setting,
    _get_settings_fields,
    _get_valid_setting_names,
)
from prefect.utilities.annotations import NotSet
from prefect.utilities.collections import listrepr

config_app: cyclopts.App = cyclopts.App(
    name="config", help="View and set Prefect settings."
)


@config_app.command(name="set")
def set_(
    settings: Annotated[
        list[str], cyclopts.Parameter(help="Settings in VAR=VAL format")
    ],
) -> None:
    """
    Change the value for a setting by setting the value in the current profile.
    """
    valid_setting_names = _get_valid_setting_names(Settings)
    parsed_settings: dict[Union[str, Setting], Any] = {}

    for item in settings:
        try:
            setting, value = item.split("=", maxsplit=1)
        except ValueError:
            exit_with_error(
                f"Failed to parse argument {item!r}. Use the format 'VAR=VAL'."
            )

        if setting not in valid_setting_names:
            exit_with_error(f"Unknown setting name {setting!r}.")

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
                help_message += (
                    f"[bold red]Validation error(s) for setting[/bold red] "
                    f"[blue]{setting.name}[/blue]\n\n - {error['msg']}\n\n"
                )
        exit_with_error(help_message)

    for setting, value in parsed_settings.items():
        _cli.console.print(f"Set {setting!r} to {value!r}.")
        if setting in os.environ:
            _cli.console.print(
                f"[yellow]{setting} is also set by an environment variable which will "
                f"override your config value. Run `unset {setting}` to clear it."
            )

    exit_with_success(f"Updated profile {new_profile.name!r}.")


@config_app.command()
def validate() -> None:
    """
    Read and validate the current profile.

    Deprecated settings will be automatically converted to new names.
    """
    profiles = prefect.settings.load_profiles()
    profile = profiles[prefect.context.get_settings_context().profile.name]

    profile.validate_settings()

    prefect.settings.save_profiles(profiles)
    exit_with_success("Configuration valid!")


@config_app.command()
def unset(
    setting_names: Annotated[
        list[str], cyclopts.Parameter(help="Setting names to unset")
    ],
    *,
    yes: Annotated[
        bool, cyclopts.Parameter("--yes", alias="-y", help="Skip confirmation")
    ] = False,
) -> None:
    """
    Restore the default value for a setting.

    Removes the setting from the current profile.
    """
    valid_setting_names = _get_valid_setting_names(Settings)
    settings_context = prefect.context.get_settings_context()
    profiles = prefect.settings.load_profiles()
    profile = profiles[settings_context.profile.name]
    parsed: set[Setting] = set()

    for setting_name in setting_names:
        if setting_name not in valid_setting_names:
            exit_with_error(f"Unknown setting name {setting_name!r}.")
        parsed.add(_get_settings_fields(Settings)[setting_name])

    for setting in parsed:
        if setting not in profile.settings:
            exit_with_error(f"{setting.name!r} is not set in profile {profile.name!r}.")

    if not yes and _cli.is_interactive():
        from rich.prompt import Confirm

        if not Confirm.ask(
            f"Are you sure you want to unset the following setting(s): "
            f"{listrepr(setting_names)}?",
            console=_cli.console,
        ):
            exit_with_error("Unset aborted.")

    profiles.update_profile(
        name=profile.name, settings={setting_name: None for setting_name in parsed}
    )

    for setting_name in setting_names:
        _cli.console.print(f"Unset {setting_name!r}.")
        if setting_name in os.environ:
            _cli.console.print(
                f"[yellow]{setting_name!r} is also set by an environment variable. "
                f"Use `unset {setting_name}` to clear it."
            )

    prefect.settings.save_profiles(profiles)
    exit_with_success(f"Updated profile {profile.name!r}.")


@config_app.command()
def view(
    *,
    show_defaults: Annotated[
        bool,
        cyclopts.Parameter(
            "--show-defaults",
            negative="--hide-defaults",
            help="Show default values",
        ),
    ] = False,
    show_sources: Annotated[
        bool,
        cyclopts.Parameter(
            "--show-sources",
            negative="--hide-sources",
            help="Show value sources",
        ),
    ] = True,
    show_secrets: Annotated[
        bool,
        cyclopts.Parameter(
            "--show-secrets",
            negative="--hide-secrets",
            help="Show secret values",
        ),
    ] = False,
) -> None:
    """
    Display the current settings.
    """
    valid_setting_names = _get_valid_setting_names(Settings)

    if show_secrets:
        dump_context = dict(include_secrets=True)
    else:
        dump_context = {}

    context = prefect.context.get_settings_context()
    current_profile_settings = context.profile.settings

    if ui_url := prefect.settings.PREFECT_UI_URL.value():
        _cli.console.print(
            f"\N{ROCKET} you are connected to:\n[green]{ui_url}[/green]",
            soft_wrap=True,
        )

    _cli.console.print(
        f"[bold blue]PREFECT_PROFILE={context.profile.name!r}[/bold blue]"
    )

    settings_output: list[str] = []
    processed_settings: set[str] = set()

    def _process_setting(
        setting: Setting,
        value: str,
        source: Literal[
            "env",
            "profile",
            "defaults",
            ".env file",
            "prefect.toml",
            "pyproject.toml",
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
                setting = _get_settings_fields(Settings).get(
                    ".".join(current_path + [key])
                )
                if setting is None or setting.name in processed_settings:
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
                setting = _get_settings_fields(Settings).get(
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

    # Environment variables
    for setting_name in valid_setting_names:
        setting = _get_settings_fields(Settings)[setting_name]
        if setting.name in processed_settings:
            continue
        if (env_value := os.getenv(setting.name)) is None:
            continue
        _process_setting(setting, env_value, "env")

    # .env file
    for key, value in dotenv_values(".env").items():
        if key in valid_setting_names:
            setting = _get_settings_fields(Settings)[key]
            if setting.name in processed_settings or value is None:
                continue
            _process_setting(setting, value, ".env file")

    # prefect.toml
    if Path("prefect.toml").exists():
        toml_settings = tomllib.loads(Path("prefect.toml").read_text(encoding="utf-8"))
        _process_toml_settings(toml_settings, base_path=[], source="prefect.toml")

    # pyproject.toml
    if Path("pyproject.toml").exists():
        pyproject_settings = tomllib.loads(
            Path("pyproject.toml").read_text(encoding="utf-8")
        )
        pyproject_settings = pyproject_settings.get("tool", {}).get("prefect", {})
        _process_toml_settings(
            pyproject_settings, base_path=[], source="pyproject.toml"
        )

    # Profile settings
    for setting, value in current_profile_settings.items():
        if setting.name not in processed_settings:
            _process_setting(setting, value, "profile")

    if show_defaults:
        _collect_defaults(
            Settings().model_dump(context=dump_context),
            current_path=[],
        )

    _cli.console.print("\n".join(sorted(settings_output)), soft_wrap=True)
