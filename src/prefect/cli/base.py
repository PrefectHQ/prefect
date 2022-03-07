"""
Base `prefect` command-line application and utilities
"""
import functools
import os
import platform
import sys
from typing import TypeVar

import pendulum
import rich.console
import typer
import typer.core

import prefect
import prefect.context
from prefect.settings import Setting
from prefect.utilities.asyncio import is_async_fn, sync_compatible

T = TypeVar("T")


def SettingsOption(setting: Setting, *args, **kwargs) -> typer.Option:
    """Custom `typer.Option` factory to load the default value from settings"""

    return typer.Option(
        # The default is dynamically retrieved
        enter_profile_from_option(setting.value),
        *args,
        # Typer shows "(dynamic)" by default. We'd like to actually show the value
        # that would be used if the parameter is not specified and a reference if the
        # source is from the environment or profile, but typer does not support this
        # yet. See https://github.com/tiangolo/typer/issues/354
        show_default=f"from {setting.name}",
        **kwargs,
    )


def SettingsArgument(setting: Setting) -> typer.Argument:
    """Custom `typer.Argument` factory to load the default value from settings"""

    # See comments in `SettingsOption`
    return typer.Argument(
        default=enter_profile_from_option(setting.value),
        show_default=f"from {setting.name}",
    )


class PrefectTyper(typer.Typer):
    """
    Wraps commands created by `Typer` to support async functions and to enter the
    profile given by the global `--profile` option.
    """

    def command(self, *args, **kwargs):
        command_decorator = super().command(*args, **kwargs)

        def wrapper(fn):
            if is_async_fn(fn):
                fn = sync_compatible(fn)
            fn = enter_profile_from_option(fn)
            return command_decorator(fn)

        return wrapper


app = PrefectTyper(add_completion=False, no_args_is_help=True)
console = rich.console.Console(highlight=False)


def version_callback(value: bool):
    if value:
        import prefect

        console.print(prefect.__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        help="Display the current version.",
        is_eager=True,
    ),
    profile: str = typer.Option(
        None,
        "--profile",
        "-p",
        help="Select a profile for this this CLI run.",
        is_eager=True,
    ),
):
    if profile is not None:
        os.environ["PREFECT_PROFILE"] = profile


def enter_profile_from_option(fn):
    @functools.wraps(fn)
    def with_profile_from_option(*args, **kwargs):
        name = os.environ.get("PREFECT_PROFILE", "default")

        # Exit early if the profile is set but not valid
        try:
            prefect.settings.load_profile(name)
        except ValueError:
            exit_with_error(f"Profile {name!r} not found.")

        context = prefect.context.profile(
            name, override_existing_variables=name != "default", initialize=True
        )
        with context:
            return fn(*args, **kwargs)

    return with_profile_from_option


@app.command()
async def version():
    """Get the current Prefect version."""
    import sqlite3

    from prefect.orion.api.server import ORION_API_VERSION
    from prefect.orion.utilities.database import get_dialect
    from prefect.settings import PREFECT_ORION_DATABASE_CONNECTION_URL

    version_info = {
        "Version": prefect.__version__,
        "API version": ORION_API_VERSION,
        "Python version": platform.python_version(),
        "Git commit": prefect.__version_info__["full-revisionid"][:8],
        "Built": pendulum.parse(
            prefect.__version_info__["date"]
        ).to_day_datetime_string(),
        "OS/Arch": f"{sys.platform}/{platform.machine()}",
        "Profile": prefect.context.get_profile_context().name,
    }

    try:
        async with prefect.get_client() as client:
            is_ephemeral = client._ephemeral_app is not None
    except Exception as exc:
        version_info["Server type"] = "<client error>"
    else:
        version_info["Server type"] = "ephemeral" if is_ephemeral else "hosted"

    # TODO: Consider adding an API route to retrieve this information?
    if is_ephemeral:
        database = get_dialect(PREFECT_ORION_DATABASE_CONNECTION_URL.value()).name
        version_info["Server"] = {"Database": database}
        if database == "sqlite":
            version_info["Server"]["SQLite version"] = sqlite3.sqlite_version

    def display(object: dict, nesting: int = 0):
        # Recursive display of a dictionary with nesting
        for key, value in object.items():
            key += ":"
            if isinstance(value, dict):
                console.print(key)
                return display(value, nesting + 2)
            prefix = " " * nesting
            console.print(f"{prefix}{key.ljust(20 - len(prefix))} {value}")

    display(version_info)


def exit_with_error(message, code=1, **kwargs):
    """
    Utility to print a stylized error message and exit with a non-zero code
    """
    kwargs.setdefault("style", "red")
    console.print(message, **kwargs)
    raise typer.Exit(code)


def exit_with_success(message, **kwargs):
    """
    Utility to print a stylized success message and exit with a zero code
    """
    kwargs.setdefault("style", "green")
    console.print(message, **kwargs)
    raise typer.Exit(0)
