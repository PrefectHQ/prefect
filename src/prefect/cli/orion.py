"""
Command line interface for working with Orion
"""
import os
import subprocess
import sys
import textwrap
from functools import partial
from string import Template
from typing import Any, Sequence, Union

import anyio
import anyio.abc
import typer

import prefect
from prefect.cli.base import (
    PrefectTyper,
    SettingsOption,
    app,
    console,
    exit_with_error,
    exit_with_success,
)
from prefect.flow_runners import get_prefect_image_name
from prefect.logging import get_logger
from prefect.orion.database.alembic_commands import (
    alembic_downgrade,
    alembic_revision,
    alembic_stamp,
    alembic_upgrade,
)
from prefect.orion.database.dependencies import provide_database_interface
from prefect.settings import (
    PREFECT_LOGGING_SERVER_LEVEL,
    PREFECT_ORION_ANALYTICS_ENABLED,
    PREFECT_ORION_API_HOST,
    PREFECT_ORION_API_PORT,
    PREFECT_ORION_SERVICES_LATE_RUNS_ENABLED,
    PREFECT_ORION_SERVICES_SCHEDULER_ENABLED,
    PREFECT_ORION_UI_ENABLED,
)
from prefect.utilities.asyncio import run_sync_in_worker_thread

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


def generate_welcome_blub(base_url, ui_enabled: bool):
    blurb = textwrap.dedent(
        r"""
         ___ ___ ___ ___ ___ ___ _____    ___  ___ ___ ___  _  _
        | _ \ _ \ __| __| __/ __|_   _|  / _ \| _ \_ _/ _ \| \| |
        |  _/   / _|| _|| _| (__  | |   | (_) |   /| | (_) | .` |
        |_| |_|_\___|_| |___\___| |_|    \___/|_|_\___\___/|_|\_|

        Configure Prefect to communicate with the server with:

            prefect config set PREFECT_API_URL={api_url}
        """
    ).format(api_url=base_url + "/api")

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


async def open_process_and_stream_output(
    command: Union[str, Sequence[str]],
    task_status: anyio.abc.TaskStatus = None,
    **kwargs: Any,
) -> None:
    """
    Opens a subprocess and streams standard output and error

    Args:
        command: The command to open a subprocess with.
        task_status: Enables this coroutine function to be used with `task_group.start`
            The task will report itself as started once the process is started.
        **kwargs: Additional keyword arguments are passed to `anyio.open_process`.
    """
    process = await anyio.open_process(
        command, stderr=sys.stderr, stdout=sys.stdout, **kwargs
    )
    if task_status:
        task_status.started()

    try:
        await process.wait()
    finally:
        with anyio.CancelScope(shield=True):
            try:
                process.terminate()
            except Exception:
                pass  # Process may already be terminated

            await process.aclose()


@orion_app.command()
async def start(
    host: str = SettingsOption(PREFECT_ORION_API_HOST),
    port: int = SettingsOption(PREFECT_ORION_API_PORT),
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
        console.print("Starting...")
        await tg.start(
            partial(
                open_process_and_stream_output,
                command=[
                    "uvicorn",
                    "--factory",
                    "prefect.orion.api.server:create_app",
                    "--host",
                    str(host),
                    "--port",
                    str(port),
                ],
                env=server_env,
            )
        )

        console.print(generate_welcome_blub(base_url, ui_enabled=ui))
        console.print("\n")

    console.print("Orion stopped!")


@orion_app.command()
def kubernetes_manifest(
    image_tag: str = None,
    log_level: str = SettingsOption(PREFECT_LOGGING_SERVER_LEVEL),
):
    """
    Generates a Kubernetes manifest for deploying Orion to a cluster.

    Example:
        $ prefect orion kubernetes-manifest | kubectl apply -f -
    """

    template = Template(
        (prefect.__module_path__ / "cli" / "templates" / "kubernetes.yaml").read_text()
    )
    manifest = template.substitute(
        {
            "image_name": image_tag or get_prefect_image_name(),
            "log_level": log_level,
        }
    )
    print(manifest)


@database_app.command()
async def reset(yes: bool = typer.Option(False, "--yes", "-y")):
    """Drop and recreate all Orion database tables"""
    db = provide_database_interface()
    engine = await db.engine()
    if not yes:
        confirm = typer.confirm(
            f'Are you sure you want to reset the Orion database located at "{engine.url}"? This will drop and recreate all tables.'
        )
        if not confirm:
            exit_with_error("Database reset aborted")
    console.print("Resetting Orion database...")
    console.print("Dropping tables...")
    await db.drop_db()
    console.print("Creating tables...")
    await db.create_db()
    exit_with_success(f'Orion database "{engine.url}" reset!')


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
    if not yes:
        confirm = typer.confirm("Are you sure you want to upgrade the Orion database?")
        if not confirm:
            exit_with_error("Database upgrade aborted!")

    console.print("Running upgrade migrations ...")
    await run_sync_in_worker_thread(alembic_upgrade, revision=revision, dry_run=dry_run)
    console.print("Migrations succeeded!")
    exit_with_success("Orion database upgraded!")


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
    if not yes:
        confirm = typer.confirm(
            "Are you sure you want to downgrade the Orion database?"
        )
        if not confirm:
            exit_with_error("Database downgrade aborted!")

    console.print("Running downgrade migrations ...")
    await run_sync_in_worker_thread(
        alembic_downgrade, revision=revision, dry_run=dry_run
    )
    console.print("Migrations succeeded!")
    exit_with_success("Orion database downgraded!")


@database_app.command()
async def revision(message: str = None, autogenerate: bool = False):
    """Create a new migration for the Orion database"""

    console.print("Running migration file creation ...")
    await run_sync_in_worker_thread(
        alembic_revision,
        message=message,
        autogenerate=autogenerate,
    )
    exit_with_success("Creating new migration file succeeded!")


@database_app.command()
async def stamp(revision: str):
    """Stamp the revision table with the given revision; don’t run any migrations"""

    console.print("Stamping database with revision ...")
    await run_sync_in_worker_thread(alembic_stamp, revision=revision)
    exit_with_success("Stamping database with revision succeeded!")
