"""
Command line interface for working with Orion
"""
import os
import subprocess
from functools import partial
from typing import Union, Sequence, Any

import anyio
import anyio.abc
import typer
from anyio.streams.text import TextReceiveStream

from prefect import settings
from prefect.cli.base import app, console, exit_with_error, exit_with_success
from prefect.orion.database.dependencies import provide_database_interface
from prefect.orion.database.alembic import (
    alembic_upgrade,
    alembic_downgrade,
    alembic_revision,
)
from prefect.utilities.asyncio import sync_compatible, run_sync_in_worker_thread

orion_app = typer.Typer(name="orion")
database_app = typer.Typer(name="database")
orion_app.add_typer(database_app)
app.add_typer(orion_app)


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
    async with await anyio.open_process(
        command, stderr=subprocess.STDOUT, **kwargs
    ) as process:
        if task_status is not None:
            task_status.started()

        try:
            async for text in TextReceiveStream(process.stdout):
                print(text, end="")  # Output is already new-line terminated
        except BaseException:
            process.terminate()
            raise


@orion_app.command()
@sync_compatible
async def start(
    host: str = settings.orion.api.host,
    port: int = settings.orion.api.port,
    log_level: str = settings.logging.default_level,
    services: bool = True,  # Note this differs from the default of `settings.orion.services.run_in_app`
    agent: bool = True,
    ui: bool = settings.orion.ui.enabled,
):
    """Start an Orion server"""
    # TODO - this logic should be abstracted in the interface
    # create the sqlite database if it doesnt already exist
    db = provide_database_interface()
    await db.engine()

    server_env = os.environ.copy()
    server_env["PREFECT_ORION_SERVICES_RUN_IN_APP"] = str(services)
    server_env["PREFECT_ORION_SERVICES_UI"] = str(ui)

    agent_env = os.environ.copy()
    agent_env["PREFECT_ORION_HOST"] = f"http://{host}:{port}/api/"

    async with anyio.create_task_group() as tg:
        console.print("Starting Orion API server...")
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

        if agent:
            # The server may not be ready yet despite waiting for the process to begin
            await anyio.sleep(1)
            console.print("Starting agent...")
            tg.start_soon(
                partial(
                    open_process_and_stream_output,
                    ["prefect", "agent", "start"],
                    env=agent_env,
                )
            )

    console.print("Orion stopped!")


@orion_app.command()
@sync_compatible
async def reset_db(yes: bool = typer.Option(False, "--yes", "-y")):
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
    n: str = typer.Option(None, "-n", help="The argument passed to alembic upgrade"),
):
    """Upgrade the Orion database"""
    if not yes:
        confirm = typer.confirm("Are you sure you want to upgrade the Orion database?")
        if not confirm:
            exit_with_error("Database upgrade aborted")

    db = provide_database_interface()

    console.print("Running upgrade migrations ...")
    await db.orm.run_migration_upgrade(n)
    console.print("Migrations succeeded!")
    exit_with_success(f"Orion database upgraded!")


@database_app.command()
@sync_compatible
async def downgrade(
    yes: bool = typer.Option(False, "--yes", "-y"),
    n: str = typer.Option(None, "-n", help="The argument passed to alembic upgrade"),
):
    """Downgrade the Orion database"""
    if not yes:
        confirm = typer.confirm(
            "Are you sure you want to downgrade the Orion database?"
        )
        if not confirm:
            exit_with_error("Database downgrade aborted")

    db = provide_database_interface()

    console.print("Running downgrade migrations ...")
    await db.orm.run_migration_downgrade(n)
    console.print("Migrations succeeded!")
    exit_with_success(f"Orion database downgraded!")


@database_app.command()
@sync_compatible
async def revision(message: str = None, autogenerate: bool = False):
    """Create a new migration for the Orion database"""

    db = provide_database_interface()

    console.print("Running migration file creation ...")
    await db.orm.run_migration_revision(message=message, autogenerate=autogenerate)
    exit_with_success(f"Creating new migration file succeeded!")
