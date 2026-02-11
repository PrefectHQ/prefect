"""
Command line interface for working with the Prefect API and server.
"""

from __future__ import annotations

import asyncio
import inspect
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import typer
from rich.table import Table
from rich.text import Text

from prefect.cli._server_utils import (
    SERVER_PID_FILE_NAME,
    SERVICES_PID_FILE,
    _cleanup_pid_file,
    _format_host_for_url,
    _is_process_running,
    _read_pid_file,
    _run_all_services,
    _run_in_background,
    _run_in_foreground,
    _validate_multi_worker,
    _write_pid_file,
    generate_welcome_blurb,
    prestart_check,
)
from prefect.cli._types import PrefectTyper, SettingsOption
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.root import app, is_interactive
from prefect.logging import get_logger
from prefect.settings import (
    PREFECT_API_SERVICES_LATE_RUNS_ENABLED,
    PREFECT_API_SERVICES_SCHEDULER_ENABLED,
    PREFECT_HOME,
    PREFECT_SERVER_ANALYTICS_ENABLED,
    PREFECT_SERVER_API_HOST,
    PREFECT_SERVER_API_KEEPALIVE_TIMEOUT,
    PREFECT_SERVER_API_PORT,
    PREFECT_SERVER_LOGGING_LEVEL,
    PREFECT_UI_ENABLED,
)
from prefect.utilities.asyncutils import run_sync_in_worker_thread

if TYPE_CHECKING:
    import logging

server_app: PrefectTyper = PrefectTyper(
    name="server",
    help="Start a Prefect server instance and interact with the database",
)
database_app: PrefectTyper = PrefectTyper(
    name="database", help="Interact with the database."
)
services_app: PrefectTyper = PrefectTyper(
    name="services", help="Interact with server loop services."
)
server_app.add_typer(database_app)
server_app.add_typer(services_app)
app.add_typer(server_app)

logger: "logging.Logger" = get_logger(__name__)


@server_app.command()
def start(
    host: str = SettingsOption(PREFECT_SERVER_API_HOST),
    port: int = SettingsOption(PREFECT_SERVER_API_PORT),
    keep_alive_timeout: int = SettingsOption(PREFECT_SERVER_API_KEEPALIVE_TIMEOUT),
    log_level: str = SettingsOption(PREFECT_SERVER_LOGGING_LEVEL),
    scheduler: bool = SettingsOption(PREFECT_API_SERVICES_SCHEDULER_ENABLED),
    analytics: bool = SettingsOption(
        PREFECT_SERVER_ANALYTICS_ENABLED, "--analytics-on/--analytics-off"
    ),
    late_runs: bool = SettingsOption(PREFECT_API_SERVICES_LATE_RUNS_ENABLED),
    ui: bool = SettingsOption(PREFECT_UI_ENABLED),
    no_services: bool = typer.Option(
        False, "--no-services", help="Only run the webserver API and UI"
    ),
    background: bool = typer.Option(
        False, "--background", "-b", help="Run the server in the background"
    ),
    workers: int = typer.Option(
        1,
        "--workers",
        help="Number of worker processes to run. Only runs the webserver API and UI",
    ),
):
    """
    Start a Prefect server instance
    """
    import socket

    base_url = f"http://{_format_host_for_url(host)}:{port}"
    if is_interactive():
        try:
            prestart_check(app.console, base_url)
        except Exception:
            pass

    if workers > 1:
        no_services = True
    _validate_multi_worker(workers, exit_with_error)

    server_settings = {
        "PREFECT_API_SERVICES_SCHEDULER_ENABLED": str(scheduler),
        "PREFECT_SERVER_ANALYTICS_ENABLED": str(analytics),
        "PREFECT_API_SERVICES_LATE_RUNS_ENABLED": str(late_runs),
        "PREFECT_UI_ENABLED": str(ui),
        "PREFECT_SERVER_LOGGING_LEVEL": log_level,
    }

    if no_services:
        server_settings["PREFECT_SERVER_ANALYTICS_ENABLED"] = "False"

    pid_file = Path(PREFECT_HOME.value()) / SERVER_PID_FILE_NAME
    # check if port is already in use
    try:
        # use getaddrinfo to support both IPv4 and IPv6 addresses
        info = socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
        family, socktype, proto, canonname, sockaddr = info[0]
        with socket.socket(family, socktype, proto) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(sockaddr)
    except socket.gaierror:
        exit_with_error(
            f"Invalid host '{host}'. Please specify a valid hostname or IP address."
        )
    except socket.error:
        if pid_file.exists():
            exit_with_error(
                f"A background server process is already running on port {port}. "
                "Run `prefect server stop` to stop it or specify a different port "
                "with the `--port` flag."
            )
        exit_with_error(
            f"Port {port} is already in use. Please specify a different port with the "
            "`--port` flag."
        )

    # check if server is already running in the background
    if background:
        try:
            pid_file.touch(mode=0o600, exist_ok=False)
        except FileExistsError:
            exit_with_error(
                "A server is already running in the background. To stop it,"
                " run `prefect server stop`."
            )

    app.console.print(generate_welcome_blurb(base_url, ui_enabled=ui))
    app.console.print("\n")

    if workers > 1:
        app.console.print(
            f"Starting server with {workers} worker processes.\n", style="blue"
        )

    if background:
        _run_in_background(
            app.console,
            pid_file,
            server_settings,
            host,
            port,
            keep_alive_timeout,
            no_services,
            workers,
        )
    else:
        _run_in_foreground(
            app.console,
            server_settings,
            host,
            port,
            keep_alive_timeout,
            no_services,
            workers,
        )


@server_app.command()
async def stop():
    """Stop a Prefect server instance running in the background"""
    pid_file = Path(PREFECT_HOME.value()) / SERVER_PID_FILE_NAME
    if not pid_file.exists():
        exit_with_success("No server running in the background.")
    pid = int(pid_file.read_text())
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        exit_with_success(
            "The server process is not running. Cleaning up stale PID file."
        )
    finally:
        # The file probably exists, but use `missing_ok` to avoid an
        # error if the file was deleted by another actor
        pid_file.unlink(missing_ok=True)
    app.console.print("Server stopped!")


@database_app.command()
async def reset(yes: bool = typer.Option(False, "--yes", "-y")):
    """Drop and recreate all Prefect database tables"""
    from prefect.server.database import provide_database_interface

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
    from prefect.server.database import provide_database_interface
    from prefect.server.database.alembic_commands import alembic_upgrade

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
    from prefect.server.database import provide_database_interface
    from prefect.server.database.alembic_commands import alembic_downgrade

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


# this is a hidden command used by the `prefect server services start --background` command
@services_app.command(hidden=True, name="manager")
def run_manager_process():
    """
    This is an internal entrypoint used by `prefect server services start --background`.
    Users do not call this directly.

    We do everything in sync so that the child won't exit until the user kills it.
    """
    from prefect.server.services.base import Service

    if not Service.enabled_services():
        logger.error("No services are enabled! Exiting manager.")
        sys.exit(1)

    logger.debug("Manager process started. Starting services...")
    try:
        asyncio.run(_run_all_services())
    except KeyboardInterrupt:
        pass
    finally:
        logger.debug("Manager process has exited.")


# public, user-facing `prefect server services` commands
@services_app.command(aliases=["ls"])
def list_services():
    """List all available services and their status."""
    from prefect.server.services.base import Service

    table = Table(title="Available Services", expand=True)
    table.add_column("Name", no_wrap=True)
    table.add_column("Enabled?", no_wrap=True)
    table.add_column("Description", style="cyan", no_wrap=False)

    for svc in Service.all_services():
        name = svc.__name__

        setting_text = Text(f"✓ {svc.environment_variable_name()}", style="green")
        if not svc.enabled():
            setting_text = Text(f"x {svc.environment_variable_name()}", style="gray50")

        doc = inspect.getdoc(svc) or ""
        description = doc.split("\n", 1)[0].strip()

        table.add_row(name, setting_text, description)

    app.console.print(table)


@services_app.command(aliases=["start"])
def start_services(
    background: bool = typer.Option(
        False, "--background", "-b", help="Run the services in the background"
    ),
):
    """Start all enabled Prefect services in one process."""
    from prefect.server.services.base import Service

    SERVICES_PID_FILE.parent.mkdir(parents=True, exist_ok=True)

    if SERVICES_PID_FILE.exists():
        pid = _read_pid_file(SERVICES_PID_FILE)
        if pid is not None and _is_process_running(pid):
            app.console.print(
                "\n[yellow]Services are already running in the background.[/]"
                "\n[blue]Use[/] [yellow]`prefect server services stop`[/] [blue]to stop them.[/]"
            )
            raise typer.Exit(code=1)
        else:
            # Stale or invalid file
            _cleanup_pid_file(SERVICES_PID_FILE)

    if not Service.enabled_services():
        app.console.print("[red]No services are enabled![/]")
        raise typer.Exit(code=1)

    if not background:
        app.console.print("\n[blue]Starting services... Press CTRL+C to stop[/]\n")
        try:
            asyncio.run(_run_all_services())
        except KeyboardInterrupt:
            pass
        app.console.print("\n[green]All services stopped.[/]")
        return

    process = subprocess.Popen(
        [
            "prefect",
            "server",
            "services",
            "manager",
        ],
        env=os.environ.copy(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=(False if os.name == "nt" else True),  # POSIX-only
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
    )

    if process.poll() is not None:
        app.console.print("[red]Failed to start services in the background![/]")
        raise typer.Exit(code=1)

    _write_pid_file(SERVICES_PID_FILE, process.pid)
    app.console.print(
        "\n[green]Services are running in the background.[/]"
        "\n[blue]Use[/] [yellow]`prefect server services stop`[/] [blue]to stop them.[/]"
    )


@services_app.command(aliases=["stop"])
async def stop_services():
    """Stop any background Prefect services that were started."""

    if not SERVICES_PID_FILE.exists():
        app.console.print("No services are running in the background.")
        raise typer.Exit()

    if (pid := _read_pid_file(SERVICES_PID_FILE)) is None:
        _cleanup_pid_file(SERVICES_PID_FILE)
        app.console.print("No valid PID file found.")
        raise typer.Exit()

    if not _is_process_running(pid):
        app.console.print("[yellow]Services were not running[/]")
        _cleanup_pid_file(SERVICES_PID_FILE)
        return

    app.console.print("\n[yellow]Shutting down...[/]")
    try:
        if os.name == "nt":
            # On Windows, send Ctrl+C to the process group
            os.kill(pid, signal.CTRL_C_EVENT)
        else:
            # On Unix, send SIGTERM
            os.kill(pid, signal.SIGTERM)
    except (ProcessLookupError, OSError):
        pass

    for _ in range(5):
        if not _is_process_running(pid):
            app.console.print("[dim]✓ Services stopped[/]")
            break
        await asyncio.sleep(1)

    _cleanup_pid_file(SERVICES_PID_FILE)
    app.console.print("\n[green]All services stopped.[/]")
