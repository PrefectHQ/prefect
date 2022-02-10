"""
Base `prefect` command-line application and utilities
"""
import functools
import os
from contextlib import nullcontext

import rich.console
import typer
from rich.pretty import Pretty, pretty_repr

import prefect
import prefect.context
import prefect.settings
from prefect.utilities.asyncio import is_async_fn, sync_compatible
from prefect.utilities.collections import dict_to_flatdict, flatdict_to_dict


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
    ),
    profile: str = typer.Option(
        None, "--profile", "-p", help="Select a profile for this this CLI run."
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
                prefect.context.load_profile(name)
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


@app.command()
def diagnostics(show_defaults: bool = False, hide_source: bool = False):
    """Display diagnostic information for support purposes"""
    profile = prefect.context.get_profile_context()

    # Get settings at each level, converted to a flat dictionary for easy comparison
    default_settings = dict_to_flatdict(prefect.settings.defaults().dict())
    env_settings = dict_to_flatdict(prefect.settings.from_env().dict())
    current_settings = dict_to_flatdict(profile.settings.dict())

    console.print(f"Profile: {profile.name}")

    # Collect differences from defaults set in the env and the profile
    env_overrides = {
        "PREFECT_" + "_".join(key).upper(): val
        for key, val in env_settings.items()
        if val != default_settings[key]
    }

    current_overrides = {
        "PREFECT_" + "_".join(key).upper(): val
        for key, val in current_settings.items()
        if val != default_settings[key]
    }

    console.print("Settings:")
    for key, value in sorted(current_overrides.items()):
        source = "env" if value == env_overrides.get(key) else "profile"
        source_blurb = f" (from {source})" if not hide_source else ""
        print(f"  {key}='{value}'{source_blurb}")

    if show_defaults:
        for key, value in sorted(default_settings.items()):
            key = "PREFECT_" + "_".join(key).upper()
            source_blurb = f" (from defaults)" if not hide_source else ""
            print(f"  {key}='{value}'{source_blurb}")


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
