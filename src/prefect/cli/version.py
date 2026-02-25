"""
Version command — native cyclopts implementation.

Displays detailed version and integration information.
"""

import platform
import sqlite3
import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as import_version
from typing import Annotated, Any

import cyclopts

import prefect
import prefect.cli._app as _cli
import prefect.context
from prefect.cli._utilities import with_cli_exception_handling


@with_cli_exception_handling
async def version(
    *,
    omit_integrations: Annotated[
        bool,
        cyclopts.Parameter("--omit-integrations", help="Omit integration information"),
    ] = False,
):
    """Get the current Prefect version and integration information."""
    from prefect.client.base import determine_server_type
    from prefect.client.constants import SERVER_API_VERSION
    from prefect.settings import get_current_settings
    from prefect.types._datetime import parse_datetime

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

    if connection_url_setting := get_current_settings().server.database.connection_url:
        import sqlalchemy as sa

        from prefect.server.database.dependencies import provide_database_interface
        from prefect.server.utilities.database import get_dialect

        connection_url = connection_url_setting.get_secret_value()
        database = get_dialect(connection_url).name
        version_info["Server"] = {"Database": database}
        if database == "sqlite":
            version_info["Server"]["SQLite version"] = sqlite3.sqlite_version
        elif database == "postgresql":
            try:
                db = provide_database_interface()
                async with db.session_context() as session:
                    result = await session.execute(sa.text("SHOW server_version"))
                    if postgres_version := result.scalar():
                        version_info["Server"]["PostgreSQL version"] = postgres_version
            except Exception:
                pass

    if not omit_integrations:
        integrations = _get_prefect_integrations()
        if integrations:
            version_info["Integrations"] = integrations

    _display(version_info)


def _get_prefect_integrations() -> dict[str, str]:
    """Get information about installed Prefect integrations."""
    from importlib.metadata import distributions

    integrations: dict[str, str] = {}
    for dist in distributions():
        name = dist.metadata.get("Name")
        if name and name.startswith("prefect-"):
            author_email = dist.metadata.get("Author-email", "").strip()
            if author_email.endswith("@prefect.io>"):
                if name == "prefect-client" and dist.version == "0.0.0":
                    continue
                integrations[name] = dist.version

    return integrations


def _display(object: dict[str, Any], nesting: int = 0) -> None:
    """Recursive display of a dictionary with nesting."""
    for key, value in object.items():
        key += ":"
        if isinstance(value, dict):
            _cli.console.print(" " * nesting + key)
            _display(value, nesting + 2)
        else:
            prefix = " " * nesting
            _cli.console.print(f"{prefix}{key.ljust(21 - len(prefix))} {value}")
