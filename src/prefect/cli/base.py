"""
Base `prefect` command-line application and utilities
"""
import functools
import os
import platform
import sys
import traceback
from contextlib import contextmanager
from typing import Optional, TypeVar

import pendulum
import rich.console
import typer
import typer.core
from click.exceptions import ClickException

import prefect
import prefect.context
import prefect.settings
from prefect.exceptions import MissingProfileError
from prefect.settings import PREFECT_TEST_MODE, Setting
from prefect.utilities.asyncio import is_async_fn, sync_compatible

T = TypeVar("T")


def SettingsOption(setting: Setting, *args, **kwargs) -> typer.Option:
    """Custom `typer.Option` factory to load the default value from settings"""

    return typer.Option(
        # The default is dynamically retrieved
        setting.value,
        *args,
        # Typer shows "(dynamic)" by default. We'd like to actually show the value
        # that would be used if the parameter is not specified and a reference if the
        # source is from the environment or profile, but typer does not support this
        # yet. See https://github.com/tiangolo/typer/issues/354
        show_default=f"from {setting.name}",
        **kwargs,
    )


def SettingsArgument(setting: Setting, *args, **kwargs) -> typer.Argument:
    """Custom `typer.Argument` factory to load the default value from settings"""

    # See comments in `SettingsOption`
    return typer.Argument(
        setting.value,
        *args,
        show_default=f"from {setting.name}",
        **kwargs,
    )


def with_cli_exception_handling(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (typer.Exit, typer.Abort, ClickException):
            raise  # Do not capture click or typer exceptions
        except MissingProfileError as exc:
            exit_with_error(exc)
        except Exception:
            if PREFECT_TEST_MODE.value():
                raise  # Reraise exceptions during test mode
            traceback.print_exc()
            exit_with_error("An exception occurred.")

    return wrapper


class PrefectTyper(typer.Typer):
    """
    Wraps commands created by `Typer` to support async functions and handle errors.
    """

    def add_typer(
        self,
        typer_instance: "PrefectTyper",
        *args,
        no_args_is_help: bool = True,
        **kwargs,
    ) -> None:
        """
        This will cause help to be default command for all sub apps unless specifically stated otherwise, opposite of before.
        """
        return super().add_typer(
            typer_instance, *args, no_args_is_help=no_args_is_help, **kwargs
        )

    def command(self, *args, **kwargs):
        command_decorator = super().command(*args, **kwargs)

        def wrapper(fn):
            if is_async_fn(fn):
                fn = sync_compatible(fn)
            fn = with_cli_exception_handling(fn)
            return command_decorator(fn)

        return wrapper


app = PrefectTyper(add_completion=False, no_args_is_help=True)
app.console = rich.console.Console(highlight=False)


def version_callback(value: bool):
    if value:
        import prefect

        app.console.print(prefect.__version__)
        raise typer.Exit()


@app.callback()
@with_cli_exception_handling
def main(
    ctx: typer.Context,
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
    if profile and not prefect.context.get_settings_context().profile.name == profile:
        # Generally, the profile should entered by `enter_root_settings_context`.
        # In the cases where it is not (i.e. CLI testing), we will enter it here.
        settings_ctx = prefect.context.use_profile(
            profile, override_environment_variables=True
        )
        ctx.with_resource(settings_ctx)


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
        "Profile": prefect.context.get_settings_context().profile.name,
    }

    is_ephemeral: Optional[bool] = None
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
                app.console.print(key)
                return display(value, nesting + 2)
            prefix = " " * nesting
            app.console.print(f"{prefix}{key.ljust(20 - len(prefix))} {value}")

    display(version_info)


def exit_with_error(message, code=1, **kwargs):
    """
    Utility to print a stylized error message and exit with a non-zero code
    """
    kwargs.setdefault("style", "red")
    app.console.print(message, **kwargs)
    raise typer.Exit(code)


def exit_with_success(message, **kwargs):
    """
    Utility to print a stylized success message and exit with a zero code
    """
    kwargs.setdefault("style", "green")
    app.console.print(message, **kwargs)
    raise typer.Exit(0)
