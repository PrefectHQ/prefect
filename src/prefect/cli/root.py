"""
Base `prefect` command-line application
"""
import platform
import sys
from typing import Optional

import pendulum
import rich.console
import typer
import typer.core

import prefect
import prefect.context
import prefect.settings
from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import with_cli_exception_handling
from prefect.logging.configuration import setup_logging
from prefect.settings import (
    PREFECT_CLI_COLORS,
    PREFECT_CLI_WRAP_LINES,
    PREFECT_TEST_MODE,
)

app = PrefectTyper(add_completion=False, no_args_is_help=True)


def version_callback(value: bool):
    if value:
        print(prefect.__version__)
        raise typer.Exit()


def is_interactive():
    return app.console.is_interactive


@app.callback()
@with_cli_exception_handling
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        # A callback is necessary for Typer to call this without looking for additional
        # commands and erroring when excluded
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
        try:
            ctx.with_resource(settings_ctx)
        except KeyError:
            print(f"Unknown profile {profile!r}.")
            exit(1)

    # Configure the output console after loading the profile

    app.console = rich.console.Console(
        highlight=False,
        color_system="auto" if PREFECT_CLI_COLORS else None,
        # `soft_wrap` disables wrapping when `True`
        soft_wrap=not PREFECT_CLI_WRAP_LINES.value(),
    )

    if not PREFECT_TEST_MODE:
        # When testing, this entrypoint can be called multiple times per process which
        # can cause logging configuration conflicts. Logging is set up in conftest
        # during tests.
        setup_logging()


@app.command()
async def version():
    """Get the current Prefect version."""
    import sqlite3

    from prefect.orion.api.server import ORION_API_VERSION
    from prefect.orion.utilities.database import get_dialect
    from prefect.settings import (
        PREFECT_API_URL,
        PREFECT_CLOUD_API_URL,
        PREFECT_ORION_DATABASE_CONNECTION_URL,
    )

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
        version_info["Server type"] = (
            "ephemeral"
            if is_ephemeral
            else (
                "cloud"
                if PREFECT_API_URL.value().startswith(PREFECT_CLOUD_API_URL.value())
                else "hosted"
            )
        )

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
