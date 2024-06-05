"""
Command line interface for working with Prefect
"""

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
from prefect.logging import get_logger
from prefect.settings import (
    PREFECT_API_SERVICES_LATE_RUNS_ENABLED,
    PREFECT_API_SERVICES_SCHEDULER_ENABLED,
    PREFECT_LOGGING_SERVER_LEVEL,
    PREFECT_SERVER_ANALYTICS_ENABLED,
    PREFECT_SERVER_API_HOST,
    PREFECT_SERVER_API_KEEPALIVE_TIMEOUT,
    PREFECT_SERVER_API_PORT,
    PREFECT_UI_ENABLED,
)
from prefect.utilities.asyncutils import run_sync_in_worker_thread
from prefect.utilities.processutils import (
    get_sys_executable,
    run_process,
    setup_signal_handlers_server,
)

server_app = PrefectTyper(
    name="server",
    help="Start a Prefect server instance and interact with the database",
)
database_app = PrefectTyper(name="database", help="Interact with the database.")
server_app.add_typer(database_app)
app.add_typer(server_app)

logger = get_logger(__name__)


def generate_welcome_blurb(base_url, ui_enabled: bool):
    blurb = textwrap.dedent(
        r"""
         ___ ___ ___ ___ ___ ___ _____ 
        | _ \ _ \ __| __| __/ __|_   _| 
        |  _/   / _|| _|| _| (__  | |  
        |_| |_|_\___|_| |___\___| |_|  

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
        The dashboard is disabled. Set `PREFECT_UI_ENABLED=1` to re-enable it.
        """
    )

    if not os.path.exists(prefect.__ui_static_path__):
        blurb += dashboard_not_built
    elif not ui_enabled:
        blurb += dashboard_disabled
    else:
        blurb += visit_dashboard

    return blurb


@server_app.command()
async def start(
    host: str = SettingsOption(PREFECT_SERVER_API_HOST),
    port: int = SettingsOption(PREFECT_SERVER_API_PORT),
    keep_alive_timeout: int = SettingsOption(PREFECT_SERVER_API_KEEPALIVE_TIMEOUT),
    log_level: str = SettingsOption(PREFECT_LOGGING_SERVER_LEVEL),
    scheduler: bool = SettingsOption(PREFECT_API_SERVICES_SCHEDULER_ENABLED),
    analytics: bool = SettingsOption(
        PREFECT_SERVER_ANALYTICS_ENABLED, "--analytics-on/--analytics-off"
    ),
    late_runs: bool = SettingsOption(PREFECT_API_SERVICES_LATE_RUNS_ENABLED),
    ui: bool = SettingsOption(PREFECT_UI_ENABLED),
):
    """Start a Prefect server instance"""

    server_env = os.environ.copy()
    server_env["PREFECT_API_SERVICES_SCHEDULER_ENABLED"] = str(scheduler)
    server_env["PREFECT_SERVER_ANALYTICS_ENABLED"] = str(analytics)
    server_env["PREFECT_API_SERVICES_LATE_RUNS_ENABLED"] = str(late_runs)
    server_env["PREFECT_API_SERVICES_UI"] = str(ui)
    server_env["PREFECT_LOGGING_SERVER_LEVEL"] = log_level

    base_url = f"http://{host}:{port}"

    async with anyio.create_task_group() as tg:
        app.console.print(generate_welcome_blurb(base_url, ui_enabled=ui))
        app.console.print("\n")

        server_process_id = await tg.start(
            partial(
                run_process,
                command=[
                    get_sys_executable(),
                    "-m",
                    "uvicorn",
                    "--app-dir",
                    # quote wrapping needed for windows paths with spaces
                    f'"{prefect.__module_path__.parent}"',
                    "--factory",
                    "prefect.server.api.server:create_app",
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
        # cleanly stop the uvicorn server. Failing to do that may cause a
        # large amount of anyio error traces on the terminal, because the
        # SIGINT is handled by Typer/Click in this process (the parent process)
        # and will start shutting down subprocesses:
        # https://github.com/PrefectHQ/server/issues/2475

        setup_signal_handlers_server(
            server_process_id, "the Prefect server", app.console.print
        )

    app.console.print("Server stopped!")


@database_app.command()
async def reset(yes: bool = typer.Option(False, "--yes", "-y")):
    """Drop and recreate all Prefect database tables"""
    from prefect.server.database.dependencies import provide_database_interface

    db = provide_database_interface()
    engine = await db.engine()
    if not yes:
        confirm = typer.confirm(
            "Are you sure you want to reset the Prefect database located "
            f'at "{engine.url!r}"? This will drop and recreate all tables.'
        )
        if not confirm:
            exit_with_error("Database reset aborted")
    app.console.print("Downgrading database...")
    await db.drop_db()
    app.console.print("Upgrading database...")
    await db.create_db()
    exit_with_success(f'Prefect database "{engine.url!r}" reset!')


@database_app.command()
async def upgrade(
    yes: bool = typer.Option(False, "--yes", "-y"),
    revision: str = typer.Option(
        "head",
        "-r",
        help=(
            "The revision to pass to `alembic upgrade`. If not provided, runs all"
            " migrations."
        ),
    ),
    dry_run: bool = typer.Option(
        False,
        help=(
            "Flag to show what migrations would be made without applying them. Will"
            " emit sql statements to stdout."
        ),
    ),
):
    """Upgrade the Prefect database"""
    from prefect.server.database.alembic_commands import alembic_upgrade
    from prefect.server.database.dependencies import provide_database_interface

    db = provide_database_interface()
    engine = await db.engine()

    if not yes:
        confirm = typer.confirm(
            f"Are you sure you want to upgrade the Prefect database at {engine.url!r}?"
        )
        if not confirm:
            exit_with_error("Database upgrade aborted!")

    app.console.print("Running upgrade migrations ...")
    await run_sync_in_worker_thread(alembic_upgrade, revision=revision, dry_run=dry_run)
    app.console.print("Migrations succeeded!")
    exit_with_success(f"Prefect database at {engine.url!r} upgraded!")


@database_app.command()
async def downgrade(
    yes: bool = typer.Option(False, "--yes", "-y"),
    revision: str = typer.Option(
        "-1",
        "-r",
        help=(
            "The revision to pass to `alembic downgrade`. If not provided, "
            "downgrades to the most recent revision. Use 'base' to run all "
            "migrations."
        ),
    ),
    dry_run: bool = typer.Option(
        False,
        help=(
            "Flag to show what migrations would be made without applying them. Will"
            " emit sql statements to stdout."
        ),
    ),
):
    """Downgrade the Prefect database"""
    from prefect.server.database.alembic_commands import alembic_downgrade
    from prefect.server.database.dependencies import provide_database_interface

    db = provide_database_interface()

    engine = await db.engine()

    if not yes:
        confirm = typer.confirm(
            "Are you sure you want to downgrade the Prefect "
            f"database at {engine.url!r}?"
        )
        if not confirm:
            exit_with_error("Database downgrade aborted!")

    app.console.print("Running downgrade migrations ...")
    await run_sync_in_worker_thread(
        alembic_downgrade, revision=revision, dry_run=dry_run
    )
    app.console.print("Migrations succeeded!")
    exit_with_success(f"Prefect database at {engine.url!r} downgraded!")


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
    """Create a new migration for the Prefect database"""
    from prefect.server.database.alembic_commands import alembic_revision

    app.console.print("Running migration file creation ...")
    await run_sync_in_worker_thread(
        alembic_revision,
        message=message,
        autogenerate=autogenerate,
    )
    exit_with_success("Creating new migration file succeeded!")


@database_app.command()
async def stamp(revision: str):
    """Stamp the revision table with the given revision; don't run any migrations"""
    from prefect.server.database.alembic_commands import alembic_stamp

    app.console.print("Stamping database with revision ...")
    await run_sync_in_worker_thread(alembic_stamp, revision=revision)
    exit_with_success("Stamping database with revision succeeded!")
