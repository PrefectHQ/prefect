"""
Base `prefect` command-line application
"""

import asyncio
import platform
import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as import_version
from typing import Any

import typer

import prefect
import prefect.context
import prefect.settings
from prefect.cli._types import PrefectTyper, SettingsOption
from prefect.cli._utilities import with_cli_exception_handling
from prefect.client.base import determine_server_type
from prefect.client.constants import SERVER_API_VERSION
from prefect.client.orchestration import ServerType
from prefect.logging.configuration import setup_logging
from prefect.settings import (
    PREFECT_CLI_WRAP_LINES,
    PREFECT_TEST_MODE,
)
from prefect.types._datetime import parse_datetime

app: PrefectTyper = PrefectTyper(add_completion=True, no_args_is_help=True)


def version_callback(value: bool) -> None:
    if value:
        print(prefect.__version__)
        raise typer.Exit()


def is_interactive() -> bool:
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
        help="Select a profile for this CLI run.",
        is_eager=True,
    ),
    prompt: bool = SettingsOption(
        prefect.settings.PREFECT_CLI_PROMPT,
        help="Force toggle prompts for this CLI run.",
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
    app.setup_console(soft_wrap=PREFECT_CLI_WRAP_LINES.value(), prompt=prompt)

    if not PREFECT_TEST_MODE:
        # When testing, this entrypoint can be called multiple times per process which
        # can cause logging configuration conflicts. Logging is set up in conftest
        # during tests.
        setup_logging()

    # When running on Windows we need to ensure that the correct event loop policy is
    # in place or we will not be able to spawn subprocesses. Sometimes this policy is
    # changed by other libraries, but here in our CLI we should have ownership of the
    # process and be able to safely force it to be the correct policy.
    # https://github.com/PrefectHQ/prefect/issues/8206
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


@app.command()
async def version(
    omit_integrations: bool = typer.Option(
        False, "--omit-integrations", help="Omit integration information"
    ),
):
    """Get the current Prefect version and integration information."""
    import sqlite3

    from prefect.server.utilities.database import get_dialect
    from prefect.settings import PREFECT_API_DATABASE_CONNECTION_URL

    if build_date_str := prefect.__version_info__.get("date", None):
        build_date = parse_datetime(build_date_str).strftime("%a, %b %d, %Y %I:%M %p")
    else:
        build_date = "unknown"

    version_info: dict[str, Any] = {
        "Version": prefect.__version__,
        "API version": SERVER_API_VERSION,
        "Python version": platform.python_version(),
        "Git commit": prefect.__version_info__["full-revisionid"][:8],
        "Built": build_date,
        "OS/Arch": f"{sys.platform}/{platform.machine()}",
        "Profile": prefect.context.get_settings_context().profile.name,
    }
    server_type = determine_server_type()

    version_info["Server type"] = server_type.lower()

    try:
        pydantic_version = import_version("pydantic")
    except PackageNotFoundError:
        pydantic_version = "Not installed"

    version_info["Pydantic version"] = pydantic_version

    if server_type == ServerType.EPHEMERAL.value:
        database = get_dialect(PREFECT_API_DATABASE_CONNECTION_URL.value()).name
        version_info["Server"] = {"Database": database}
        if database == "sqlite":
            version_info["Server"]["SQLite version"] = sqlite3.sqlite_version

    if not omit_integrations:
        integrations = get_prefect_integrations()
        if integrations:
            version_info["Integrations"] = integrations

    display(version_info)


def get_prefect_integrations() -> dict[str, str]:
    """Get information about installed Prefect integrations."""
    from importlib.metadata import distributions

    integrations: dict[str, str] = {}
    for dist in distributions():
        name = dist.metadata.get("Name")
        if name and name.startswith("prefect-"):
            author_email = dist.metadata.get("Author-email", "").strip()
            if author_email.endswith("@prefect.io>"):
                if (  # TODO: remove clause after updating `prefect-client` packaging config
                    name == "prefect-client" and dist.version == "0.0.0"
                ):
                    continue
                integrations[name] = dist.version

    return integrations


def display(object: dict[str, Any], nesting: int = 0) -> None:
    """Recursive display of a dictionary with nesting."""
    for key, value in object.items():
        key += ":"
        if isinstance(value, dict):
            app.console.print(" " * nesting + key)
            display(value, nesting + 2)
        else:
            prefix = " " * nesting
            app.console.print(f"{prefix}{key.ljust(20 - len(prefix))} {value}")
