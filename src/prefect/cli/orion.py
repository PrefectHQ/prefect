"""
Command line interface for working with Orion
"""
import os
import subprocess
import textwrap
from functools import partial
from string import Template
from typing import Any, Sequence, Union

import anyio
import anyio.abc
import typer
from anyio.streams.text import TextReceiveStream

import prefect
from prefect.cli.base import app, console, exit_with_error, exit_with_success
from prefect.flow_runners import get_prefect_image_name
from prefect.logging import get_logger
from prefect.orion.database.alembic_commands import (
    alembic_downgrade,
    alembic_revision,
    alembic_stamp,
    alembic_upgrade,
)
from prefect.orion.database.dependencies import provide_database_interface
from prefect.utilities.asyncio import run_sync_in_worker_thread, sync_compatible

orion_app = typer.Typer(
    name="orion",
    help="Commands for interacting with backend services.",
)
database_app = typer.Typer(
    name="database", help="Commands for interacting with the database."
)
orion_app.add_typer(database_app)
app.add_typer(orion_app)

logger = get_logger(__name__)


def generate_welcome_blub(base_url):
    api_url = base_url + "/api"

    blurb = textwrap.dedent(
        f"""
         ___ ___ ___ ___ ___ ___ _____    ___  ___ ___ ___  _  _
        | _ \ _ \ __| __| __/ __|_   _|  / _ \| _ \_ _/ _ \| \| |
        |  _/   / _|| _|| _| (__  | |   | (_) |   /| | (_) | .` |
        |_| |_|_\___|_| |___\___| |_|    \___/|_|_\___\___/|_|\_|

        Configure Prefect to communicate with the server with:

            PREFECT_ORION_HOST={api_url}
        """
    )

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
    elif not prefect.settings.from_env().orion.ui.enabled:
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
    process = await anyio.open_process(command, stderr=subprocess.STDOUT, **kwargs)
    if task_status:
        task_status.started()

    try:
        async for text in TextReceiveStream(process.stdout):
            print(text, end="")  # Output is already new-line terminated
    except Exception:
        logger.debug("Ignoring exception in subprocess text stream", exc_info=True)
    except BaseException:
        with anyio.CancelScope(shield=True):
            process.terminate()
        raise


@orion_app.command()
@sync_compatible
async def start(
    host: str = prefect.settings.from_env().orion.api.host,
    port: int = prefect.settings.from_env().orion.api.port,
    log_level: str = prefect.settings.from_env().logging.server_level,
    services: bool = True,  # Note this differs from the default of `prefect.settings.from_env().orion.services.run_in_app`
    agent: bool = True,
    ui: bool = prefect.settings.from_env().orion.ui.enabled,
):
    """Start an Orion server"""
    # TODO - this logic should be abstracted in the interface
    # Run migrations - if configured for sqlite will create the db
    db = provide_database_interface()
    await db.create_db()

    server_env = os.environ.copy()
    server_env["PREFECT_ORION_SERVICES_RUN_IN_APP"] = str(services)
    server_env["PREFECT_ORION_SERVICES_UI"] = str(ui)

    base_url = f"http://{host}:{port}"

    agent_env = os.environ.copy()
    agent_env["PREFECT_ORION_HOST"] = base_url + "/api"

    async with anyio.create_task_group() as tg:
        console.print("Starting...")
        await tg.start(
            partial(
                open_process_and_stream_output,
                command=[
                    "uvicorn",
                    "prefect.orion.api.server:app",
                    "--host",
                    str(host),
                    "--port",
                    str(port),
                    "--log-level",
                    log_level.lower(),
                ],
                env=server_env,
            )
        )

        console.print(generate_welcome_blub(base_url))

        if agent:
            # The server may not be ready yet despite waiting for the process to begin
            await anyio.sleep(1)
            tg.start_soon(
                partial(
                    open_process_and_stream_output,
                    ["prefect", "agent", "start", "--hide-welcome"],
                    env=agent_env,
                )
            )
            console.print(
                "An agent has been started alongside the server. It will watch for "
                "scheduled flow runs."
            )
        else:
            console.print(
                "The agent has been disabled. Start an agent with `prefect agent start`."
            )

        console.print("\n")

    console.print("Orion stopped!")


@orion_app.command()
def kubernetes_manifest():
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
            "image_name": get_prefect_image_name(),
        }
    )
    print(manifest)


@database_app.command()
@sync_compatible
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
@sync_compatible
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
@sync_compatible
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
@sync_compatible
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
@sync_compatible
async def stamp(revision: str):
    """Stamp the revision table with the given revision; don’t run any migrations"""

    console.print("Stamping database with revision ...")
    await run_sync_in_worker_thread(alembic_stamp, revision=revision)
    exit_with_success("Stamping database with revision succeeded!")
