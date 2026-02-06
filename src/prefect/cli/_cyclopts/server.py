"""
Server command — native cyclopts implementation.

Start and manage the Prefect server.
"""

import asyncio
import inspect
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Annotated, Optional

import cyclopts
from rich.table import Table
from rich.text import Text

from prefect.cli._cyclopts._utilities import (
    exit_with_error,
    exit_with_success,
    run_async,
    with_cli_exception_handling,
)

server_app = cyclopts.App(
    name="server",
    help="Start a Prefect server instance and interact with the database.",
)
database_app = cyclopts.App(name="database", help="Interact with the database.")
services_app = cyclopts.App(name="services", help="Interact with server loop services.")
server_app.command(database_app)
server_app.command(services_app)


def _get_console():
    from prefect.cli._cyclopts import console

    return console


def _is_interactive():
    from prefect.cli._cyclopts import _is_interactive

    return _is_interactive()


@server_app.command()
@with_cli_exception_handling
def start(
    *,
    host: Annotated[
        str,
        cyclopts.Parameter("--host", help="Server host address."),
    ] = "127.0.0.1",
    port: Annotated[
        int,
        cyclopts.Parameter("--port", help="Server port."),
    ] = 4200,
    keep_alive_timeout: Annotated[
        int,
        cyclopts.Parameter("--keep-alive-timeout", help="Keep-alive timeout seconds."),
    ] = 5,
    log_level: Annotated[
        str,
        cyclopts.Parameter("--log-level", help="Server logging level."),
    ] = "WARNING",
    scheduler: Annotated[
        bool,
        cyclopts.Parameter(
            "--scheduler", negative="--no-scheduler", help="Enable scheduler."
        ),
    ] = True,
    analytics: Annotated[
        bool,
        cyclopts.Parameter(
            "--analytics-on", negative="--analytics-off", help="Toggle analytics."
        ),
    ] = True,
    late_runs: Annotated[
        bool,
        cyclopts.Parameter(
            "--late-runs", negative="--no-late-runs", help="Enable late runs."
        ),
    ] = True,
    ui: Annotated[
        bool,
        cyclopts.Parameter("--ui", negative="--no-ui", help="Enable the UI."),
    ] = True,
    no_services: Annotated[
        bool,
        cyclopts.Parameter("--no-services", help="Only run the webserver API and UI."),
    ] = False,
    background: Annotated[
        bool,
        cyclopts.Parameter("--background", alias="-b", help="Run in the background."),
    ] = False,
    workers: Annotated[
        int,
        cyclopts.Parameter("--workers", help="Number of worker processes."),
    ] = 1,
):
    """Start a Prefect server instance."""
    import socket

    from prefect.cli.server import (
        SERVER_PID_FILE_NAME,
        _format_host_for_url,
        _run_in_background,
        _run_in_foreground,
        _validate_multi_worker,
        generate_welcome_blurb,
        prestart_check,
    )
    from prefect.settings import PREFECT_HOME

    console = _get_console()
    base_url = f"http://{_format_host_for_url(host)}:{port}"

    if _is_interactive():
        try:
            prestart_check(base_url)
        except Exception:
            pass

    if workers > 1:
        no_services = True
    _validate_multi_worker(workers)

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

    try:
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

    if background:
        try:
            pid_file.touch(mode=0o600, exist_ok=False)
        except FileExistsError:
            exit_with_error(
                "A server is already running in the background. To stop it,"
                " run `prefect server stop`."
            )

    console.print(generate_welcome_blurb(base_url, ui_enabled=ui))
    console.print("\n")

    if workers > 1:
        console.print(
            f"Starting server with {workers} worker processes.\n", style="blue"
        )

    if background:
        _run_in_background(
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
            server_settings, host, port, keep_alive_timeout, no_services, workers
        )


@server_app.command()
@with_cli_exception_handling
@run_async
async def stop():
    """Stop a Prefect server instance running in the background."""
    from prefect.cli.server import SERVER_PID_FILE_NAME
    from prefect.settings import PREFECT_HOME

    console = _get_console()
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
        pid_file.unlink(missing_ok=True)
    console.print("Server stopped!")


# --- database subcommands ---


@database_app.command()
@with_cli_exception_handling
@run_async
async def reset(
    *,
    yes: Annotated[
        bool, cyclopts.Parameter("--yes", alias="-y", help="Skip confirmation.")
    ] = False,
):
    """Drop and recreate all Prefect database tables."""
    from prefect.server.database import provide_database_interface

    console = _get_console()
    db = provide_database_interface()
    engine = await db.engine()

    if not yes:
        from rich.prompt import Confirm

        if not Confirm.ask(
            "Are you sure you want to reset the Prefect database located "
            f'at "{engine.url!r}"? This will drop and recreate all tables.',
            console=console,
        ):
            exit_with_error("Database reset aborted")

    console.print("Downgrading database...")
    await db.drop_db()
    console.print("Upgrading database...")
    await db.create_db()
    exit_with_success(f'Prefect database "{engine.url!r}" reset!')


@database_app.command()
@with_cli_exception_handling
@run_async
async def upgrade(
    *,
    yes: Annotated[
        bool, cyclopts.Parameter("--yes", alias="-y", help="Skip confirmation.")
    ] = False,
    revision: Annotated[
        str,
        cyclopts.Parameter(
            "--revision", alias="-r", help="Alembic revision (default: head)."
        ),
    ] = "head",
    dry_run: Annotated[
        bool,
        cyclopts.Parameter("--dry-run", help="Show migrations without applying."),
    ] = False,
):
    """Upgrade the Prefect database."""
    from prefect.server.database import provide_database_interface
    from prefect.server.database.alembic_commands import alembic_upgrade
    from prefect.utilities.asyncutils import run_sync_in_worker_thread

    console = _get_console()
    db = provide_database_interface()
    engine = await db.engine()

    if not yes:
        from rich.prompt import Confirm

        if not Confirm.ask(
            f"Are you sure you want to upgrade the Prefect database at {engine.url!r}?",
            console=console,
        ):
            exit_with_error("Database upgrade aborted!")

    console.print("Running upgrade migrations ...")
    await run_sync_in_worker_thread(alembic_upgrade, revision=revision, dry_run=dry_run)
    console.print("Migrations succeeded!")
    exit_with_success(f"Prefect database at {engine.url!r} upgraded!")


@database_app.command()
@with_cli_exception_handling
@run_async
async def downgrade(
    *,
    yes: Annotated[
        bool, cyclopts.Parameter("--yes", alias="-y", help="Skip confirmation.")
    ] = False,
    revision: Annotated[
        str,
        cyclopts.Parameter(
            "--revision", alias="-r", help="Alembic revision (default: -1)."
        ),
    ] = "-1",
    dry_run: Annotated[
        bool,
        cyclopts.Parameter("--dry-run", help="Show migrations without applying."),
    ] = False,
):
    """Downgrade the Prefect database."""
    from prefect.server.database import provide_database_interface
    from prefect.server.database.alembic_commands import alembic_downgrade
    from prefect.utilities.asyncutils import run_sync_in_worker_thread

    console = _get_console()
    db = provide_database_interface()
    engine = await db.engine()

    if not yes:
        from rich.prompt import Confirm

        if not Confirm.ask(
            "Are you sure you want to downgrade the Prefect "
            f"database at {engine.url!r}?",
            console=console,
        ):
            exit_with_error("Database downgrade aborted!")

    console.print("Running downgrade migrations ...")
    await run_sync_in_worker_thread(
        alembic_downgrade, revision=revision, dry_run=dry_run
    )
    console.print("Migrations succeeded!")
    exit_with_success(f"Prefect database at {engine.url!r} downgraded!")


@database_app.command()
@with_cli_exception_handling
@run_async
async def revision(
    *,
    message: Annotated[
        Optional[str],
        cyclopts.Parameter("--message", alias="-m", help="Migration message."),
    ] = None,
    autogenerate: Annotated[
        bool,
        cyclopts.Parameter("--autogenerate", help="Auto-generate from models."),
    ] = False,
):
    """Create a new migration for the Prefect database."""
    from prefect.server.database.alembic_commands import alembic_revision
    from prefect.utilities.asyncutils import run_sync_in_worker_thread

    console = _get_console()
    console.print("Running migration file creation ...")
    await run_sync_in_worker_thread(
        alembic_revision, message=message, autogenerate=autogenerate
    )
    exit_with_success("Creating new migration file succeeded!")


@database_app.command()
@with_cli_exception_handling
@run_async
async def stamp(revision: str):
    """Stamp the revision table with the given revision; don't run any migrations."""
    from prefect.server.database.alembic_commands import alembic_stamp
    from prefect.utilities.asyncutils import run_sync_in_worker_thread

    console = _get_console()
    console.print("Stamping database with revision ...")
    await run_sync_in_worker_thread(alembic_stamp, revision=revision)
    exit_with_success("Stamping database with revision succeeded!")


# --- services subcommands ---


@services_app.command(name="ls")
@with_cli_exception_handling
def list_services():
    """List all available services and their status."""
    from prefect.server.services.base import Service

    console = _get_console()
    table = Table(title="Available Services", expand=True)
    table.add_column("Name", no_wrap=True)
    table.add_column("Enabled?", no_wrap=True)
    table.add_column("Description", style="cyan", no_wrap=False)

    for svc in Service.all_services():
        name = svc.__name__
        setting_text = Text(f"\u2713 {svc.environment_variable_name()}", style="green")
        if not svc.enabled():
            setting_text = Text(f"x {svc.environment_variable_name()}", style="gray50")
        doc = inspect.getdoc(svc) or ""
        description = doc.split("\n", 1)[0].strip()
        table.add_row(name, setting_text, description)

    console.print(table)


@services_app.command(name="start")
@with_cli_exception_handling
def start_services(
    *,
    background: Annotated[
        bool,
        cyclopts.Parameter(
            "--background", alias="-b", help="Run the services in the background."
        ),
    ] = False,
):
    """Start all enabled Prefect services in one process."""
    from prefect.cli.server import (
        SERVICES_PID_FILE,
        _cleanup_pid_file,
        _is_process_running,
        _read_pid_file,
        _run_all_services,
        _write_pid_file,
    )
    from prefect.server.services.base import Service

    console = _get_console()
    SERVICES_PID_FILE.parent.mkdir(parents=True, exist_ok=True)

    if SERVICES_PID_FILE.exists():
        pid = _read_pid_file(SERVICES_PID_FILE)
        if pid is not None and _is_process_running(pid):
            console.print(
                "\n[yellow]Services are already running in the background.[/]"
                "\n[blue]Use[/] [yellow]`prefect server services stop`[/] [blue]to stop them.[/]"
            )
            raise SystemExit(1)
        else:
            _cleanup_pid_file(SERVICES_PID_FILE)

    if not Service.enabled_services():
        console.print("[red]No services are enabled![/]")
        raise SystemExit(1)

    if not background:
        console.print("\n[blue]Starting services... Press CTRL+C to stop[/]\n")
        try:
            asyncio.run(_run_all_services())
        except KeyboardInterrupt:
            pass
        console.print("\n[green]All services stopped.[/]")
        return

    process = subprocess.Popen(
        ["prefect", "server", "services", "manager"],
        env=os.environ.copy(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=(os.name != "nt"),
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
    )

    if process.poll() is not None:
        console.print("[red]Failed to start services in the background![/]")
        raise SystemExit(1)

    _write_pid_file(SERVICES_PID_FILE, process.pid)
    console.print(
        "\n[green]Services are running in the background.[/]"
        "\n[blue]Use[/] [yellow]`prefect server services stop`[/] [blue]to stop them.[/]"
    )


@services_app.command(name="stop")
@with_cli_exception_handling
@run_async
async def stop_services():
    """Stop any background Prefect services that were started."""
    from prefect.cli.server import (
        SERVICES_PID_FILE,
        _cleanup_pid_file,
        _is_process_running,
        _read_pid_file,
    )

    console = _get_console()

    if not SERVICES_PID_FILE.exists():
        console.print("No services are running in the background.")
        raise SystemExit(0)

    if (pid := _read_pid_file(SERVICES_PID_FILE)) is None:
        _cleanup_pid_file(SERVICES_PID_FILE)
        console.print("No valid PID file found.")
        raise SystemExit(0)

    if not _is_process_running(pid):
        console.print("[yellow]Services were not running[/]")
        _cleanup_pid_file(SERVICES_PID_FILE)
        return

    console.print("\n[yellow]Shutting down...[/]")
    try:
        if os.name == "nt":
            os.kill(pid, signal.CTRL_C_EVENT)
        else:
            os.kill(pid, signal.SIGTERM)
    except (ProcessLookupError, OSError):
        pass

    for _ in range(5):
        if not _is_process_running(pid):
            console.print("[dim]\u2713 Services stopped[/]")
            break
        await asyncio.sleep(1)

    _cleanup_pid_file(SERVICES_PID_FILE)
    console.print("\n[green]All services stopped.[/]")


# Hidden manager command (used by --background)
@services_app.command(name="manager")
@with_cli_exception_handling
def run_manager_process():
    """Internal entrypoint for background services."""
    from prefect.cli.server import _run_all_services
    from prefect.logging import get_logger
    from prefect.server.services.base import Service

    logger = get_logger(__name__)

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
