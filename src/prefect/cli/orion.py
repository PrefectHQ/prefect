"""
Command line interface for working with Orion
"""
import contextlib
import os
import textwrap
from functools import partial

import anyio
import anyio.abc
import typer

import prefect
from prefect.cli._types import PrefectTyper, SettingsOption
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.root import app
from prefect.client import get_client
from prefect.logging import get_logger
from prefect.orion.database.alembic_commands import (
    alembic_downgrade,
    alembic_revision,
    alembic_stamp,
    alembic_upgrade,
)
from prefect.orion.database.dependencies import provide_database_interface
from prefect.settings import (
    PREFECT_API_URL,
    PREFECT_LOGGING_SERVER_LEVEL,
    PREFECT_ORION_ANALYTICS_ENABLED,
    PREFECT_ORION_API_HOST,
    PREFECT_ORION_API_KEEPALIVE_TIMEOUT,
    PREFECT_ORION_API_PORT,
    PREFECT_ORION_SERVICES_LATE_RUNS_ENABLED,
    PREFECT_ORION_SERVICES_SCHEDULER_ENABLED,
    PREFECT_ORION_UI_ENABLED,
)
from prefect.utilities.asyncutils import run_sync_in_worker_thread
from prefect.utilities.processutils import kill_on_interrupt, run_process

orion_app = PrefectTyper(
    name="orion",
    help="Commands for interacting with backend services.",
)
database_app = PrefectTyper(
    name="database", help="Commands for interacting with the database."
)
orion_app.add_typer(database_app)
app.add_typer(orion_app)

logger = get_logger(__name__)


def generate_welcome_blurb(base_url, ui_enabled: bool):
    blurb = textwrap.dedent(
        r"""
         ___ ___ ___ ___ ___ ___ _____    ___  ___ ___ ___  _  _
        | _ \ _ \ __| __| __/ __|_   _|  / _ \| _ \_ _/ _ \| \| |
        |  _/   / _|| _|| _| (__  | |   | (_) |   /| | (_) | .` |
        |_| |_|_\___|_| |___\___| |_|    \___/|_|_\___\___/|_|\_|

        Configure Prefect to communicate with the server with:

            prefect config set PREFECT_API_URL={api_url}

        View the API reference documentation at {docs_url}
        """
    ).format(api_url=base_url + "/api", docs_url=base_url + "/docs")

    visit_dashboard = textwrap.dedent(
        f"""
        Check out the dashboard at {base_url}
        """
    )

    dashboard_not_built = textwrap.dedent(
        """
        The dashboard is not built. It looks like you're on a development version.
        See `prefect dev` for development commands.
        """
    )

    dashboard_disabled = textwrap.dedent(
        """
        The dashboard is disabled. Set `PREFECT_ORION_UI_ENABLED=1` to reenable it.
        """
    )

    if not os.path.exists(prefect.__ui_static_path__):
        blurb += dashboard_not_built
    elif not ui_enabled:
        blurb += dashboard_disabled
    else:
        blurb += visit_dashboard

    return blurb


@orion_app.command()
async def start(
    host: str = SettingsOption(PREFECT_ORION_API_HOST),
    port: int = SettingsOption(PREFECT_ORION_API_PORT),
    keep_alive_timeout: int = SettingsOption(PREFECT_ORION_API_KEEPALIVE_TIMEOUT),
    log_level: str = SettingsOption(PREFECT_LOGGING_SERVER_LEVEL),
    scheduler: bool = SettingsOption(PREFECT_ORION_SERVICES_SCHEDULER_ENABLED),
    analytics: bool = SettingsOption(
        PREFECT_ORION_ANALYTICS_ENABLED, "--analytics-on/--analytics-off"
    ),
    late_runs: bool = SettingsOption(PREFECT_ORION_SERVICES_LATE_RUNS_ENABLED),
    ui: bool = SettingsOption(PREFECT_ORION_UI_ENABLED),
):
    """Start an Orion server"""

    server_env = os.environ.copy()
    server_env["PREFECT_ORION_SERVICES_SCHEDULER_ENABLED"] = str(scheduler)
    server_env["PREFECT_ORION_ANALYTICS_ENABLED"] = str(analytics)
    server_env["PREFECT_ORION_SERVICES_LATE_RUNS_ENABLED"] = str(late_runs)
    server_env["PREFECT_ORION_SERVICES_UI"] = str(ui)
    server_env["PREFECT_LOGGING_SERVER_LEVEL"] = log_level

    base_url = f"http://{host}:{port}"

    async with anyio.create_task_group() as tg:
        app.console.print(generate_welcome_blurb(base_url, ui_enabled=ui))
        app.console.print("\n")

        orion_process_id = await tg.start(
            partial(
                run_process,
                command=[
                    "uvicorn",
                    "--app-dir",
                    # quote wrapping needed for windows paths with spaces
                    f'"{prefect.__module_path__.parent}"',
                    "--factory",
                    "prefect.orion.api.server:create_app",
                    "--host",
                    str(host),
                    "--port",
                    str(port),
                    "--timeout-keep-alive",
                    str(keep_alive_timeout),
                ],
                env=server_env,
                stream_output=True,
            )
        )

        # Explicitly handle the interrupt signal here, as it will allow us to
        # cleanly stop the Orion uvicorn server. Failing to do that may cause a
        # large amount of anyio error traces on the terminal, because the
        # SIGINT is handled by Typer/Click in this process (the parent process)
        # and will start shutting down subprocesses:
        # https://github.com/PrefectHQ/orion/issues/2475

        kill_on_interrupt(orion_process_id, "Orion", app.console.print)

    app.console.print("Orion stopped!")


@orion_app.command()
async def status(
    wait: bool = typer.Option(
        False,
        "--wait",
        help="When the wait command is specified, the health check loop runs until successful or an optional timeout value is exceeded. Otherwise the check is run only once.",
    ),
    timeout: int = typer.Option(
        None,
        "--timeout",
        help="Optional timeout value in seconds. Must be used with the wait argument",
    ),
    api: str = SettingsOption(PREFECT_API_URL),
):
    """Verify Connection status with Orion API"""

    if not api:
        exit_with_success(
            "PREFECT_API_URL not set for the currently active profile. To check the status of an Orion instance or Cloud API connection, the PREFECT_API_URL must be specified for the selected profile."
        )

    app.console.print(f"Attempting connection to server API URL: {api}")

    sleep_time = 1  # Initial sleep time when polling
    async with get_client() as client:
        with (
            anyio.move_on_after(timeout) if timeout else contextlib.nullcontext()
        ) as timeout_scope:
            while True:
                response = await client.api_healthcheck()
                if not response:
                    break
                else:
                    if not wait:
                        exit_with_error(
                            f"Server connection failed with exception: '{response}'"
                        )

                    app.console.print(f"{response} retrying in {sleep_time}s")
                    await anyio.sleep(sleep_time)
                    sleep_time = sleep_time * 2  # Exponential backoff

        if timeout and timeout_scope.cancel_called:
            exit_with_error(f"Server did not respond within timeout of {timeout}s.")
        else:
            exit_with_success("Server is healthy!")


@database_app.command()
async def reset(yes: bool = typer.Option(False, "--yes", "-y")):
    """Drop and recreate all Orion database tables"""
    db = provide_database_interface()
    engine = await db.engine()
    if not yes:
        confirm = typer.confirm(
            "Are you sure you want to reset the Orion database located "
            f'at "{engine.url!r}"? This will drop and recreate all tables.'
        )
        if not confirm:
            exit_with_error("Database reset aborted")
    app.console.print("Downgrading database...")
    await db.drop_db()
    app.console.print("Upgrading database...")
    await db.create_db()
    exit_with_success(f'Orion database "{engine.url!r}" reset!')


@database_app.command()
async def upgrade(
    yes: bool = typer.Option(False, "--yes", "-y"),
    revision: str = typer.Option(
        "head",
        "-r",
        help="The revision to pass to `alembic upgrade`. If not provided, runs all migrations.",
    ),
    dry_run: bool = typer.Option(
        False,
        help="Flag to show what migrations would be made without applying them. Will emit sql statements to stdout.",
    ),
):
    """Upgrade the Orion database"""
    db = provide_database_interface()
    engine = await db.engine()

    if not yes:
        confirm = typer.confirm(
            "Are you sure you want to upgrade the " f"Orion database at {engine.url!r}?"
        )
        if not confirm:
            exit_with_error("Database upgrade aborted!")

    app.console.print("Running upgrade migrations ...")
    await run_sync_in_worker_thread(alembic_upgrade, revision=revision, dry_run=dry_run)
    app.console.print("Migrations succeeded!")
    exit_with_success(f"Orion database at {engine.url!r} upgraded!")


@database_app.command()
async def downgrade(
    yes: bool = typer.Option(False, "--yes", "-y"),
    revision: str = typer.Option(
        "base",
        "-r",
        help="The revision to pass to `alembic downgrade`. If not provided, runs all migrations.",
    ),
    dry_run: bool = typer.Option(
        False,
        help="Flag to show what migrations would be made without applying them. Will emit sql statements to stdout.",
    ),
):
    """Downgrade the Orion database"""
    db = provide_database_interface()
    engine = await db.engine()

    if not yes:
        confirm = typer.confirm(
            "Are you sure you want to downgrade the Orion "
            f"database at {engine.url!r}?"
        )
        if not confirm:
            exit_with_error("Database downgrade aborted!")

    app.console.print("Running downgrade migrations ...")
    await run_sync_in_worker_thread(
        alembic_downgrade, revision=revision, dry_run=dry_run
    )
    app.console.print("Migrations succeeded!")
    exit_with_success(f"Orion database at {engine.url!r} downgraded!")


@database_app.command()
async def revision(
    message: str = typer.Option(
        None,
        "--message",
        "-m",
        help="A message to describe the migration.",
    ),
    autogenerate: bool = False,
):
    """Create a new migration for the Orion database"""

    app.console.print("Running migration file creation ...")
    await run_sync_in_worker_thread(
        alembic_revision,
        message=message,
        autogenerate=autogenerate,
    )
    exit_with_success("Creating new migration file succeeded!")


@database_app.command()
async def stamp(revision: str):
    """Stamp the revision table with the given revision; don’t run any migrations"""

    app.console.print("Stamping database with revision ...")
    await run_sync_in_worker_thread(alembic_stamp, revision=revision)
    exit_with_success("Stamping database with revision succeeded!")
