"""
Base `prefect` command-line application and utilities
"""
import functools
import os
from contextlib import nullcontext
from functools import partial
from typing import TypeVar

import rich.console
import typer
import typer.core

import prefect
import prefect.context
import prefect.settings
from prefect.utilities.asyncio import is_async_fn, sync_compatible

T = TypeVar("T")


def SettingsOption(variable: str) -> typer.Option:
    """Custom `typer.Option` factory to load the default value from settings"""

    return typer.Option(
        # The default is dynamically retrieved
        default=partial(enter_profile_from_option(prefect.settings.get), variable),
        # Typer shows "(dynamic)" by default. We'd like to actually show the value
        # that would be used if the parameter is not specified and a reference if the
        # source is from the environment or profile, but typer does not support this
        # yet. See https://github.com/tiangolo/typer/issues/354
        show_default=f"from {variable}",
    )


def SettingsArgument(variable: str) -> typer.Argument:
    """Custom `typer.Argument` factory to load the default value from settings"""

    # See comments in `SettingsOption`
    return typer.Argument(
        default=partial(enter_profile_from_option(prefect.settings.get), variable),
        show_default=f"from {variable}",
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
        name = os.environ.get("PREFECT_PROFILE", None)

        # Exit early if the profile is set but not valid
        if name is not None:
            try:
                prefect.settings.load_profile(name)
            except ValueError:
                exit_with_error(f"Profile {name!r} not found.")
                raise ValueError()

        context = (
            prefect.context.profile(name, override_existing_variables=True)
            if name
            else nullcontext()
        )
        with context:
            return fn(*args, **kwargs)

    return with_profile_from_option


@app.command()
def version():
    """Get the current Prefect version."""
    # TODO: expand this to a much richer display of version and system information
    console.print(prefect.__version__)


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
