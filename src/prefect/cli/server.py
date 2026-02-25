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
import time
from pathlib import Path
from typing import Annotated, Optional

import cyclopts
from rich.table import Table
from rich.text import Text

import prefect.cli._app as _cli
from prefect.cli._utilities import (
    exit_with_error,
    exit_with_success,
    with_cli_exception_handling,
)

server_app: cyclopts.App = cyclopts.App(
    name="server",
    help="Start a Prefect server instance and interact with the database.",
)
database_app: cyclopts.App = cyclopts.App(
    name="database", help="Interact with the database."
)
services_app: cyclopts.App = cyclopts.App(
    name="services", help="Interact with server loop services."
)

_monotonic = time.monotonic
server_app.command(database_app)
server_app.command(services_app)


@server_app.command()
@with_cli_exception_handling
def start(
    *,
    host: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--host", help="Server host address. [from PREFECT_SERVER_API_HOST]"
        ),
    ] = None,
    port: Annotated[
        Optional[int],
        cyclopts.Parameter(
            "--port", help="Server port. [from PREFECT_SERVER_API_PORT]"
        ),
    ] = None,
    keep_alive_timeout: Annotated[
        Optional[int],
        cyclopts.Parameter(
            "--keep-alive-timeout",
            help="Keep-alive timeout seconds. [from PREFECT_SERVER_API_KEEPALIVE_TIMEOUT]",
        ),
    ] = None,
    log_level: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--log-level",
            help="Server logging level. [from PREFECT_SERVER_LOGGING_LEVEL]",
        ),
    ] = None,
    scheduler: Annotated[
        Optional[bool],
        cyclopts.Parameter(
            "--scheduler",
            help="Enable scheduler. [from PREFECT_API_SERVICES_SCHEDULER_ENABLED]",
        ),
    ] = None,
    analytics: Annotated[
        bool,
        cyclopts.Parameter(
            "--analytics-on",
            negative="--analytics-off",
            help="Toggle analytics. [from PREFECT_SERVER_ANALYTICS_ENABLED]",
        ),
    ] = True,
    late_runs: Annotated[
        Optional[bool],
        cyclopts.Parameter(
            "--late-runs",
            help="Enable late runs. [from PREFECT_API_SERVICES_LATE_RUNS_ENABLED]",
        ),
    ] = None,
    ui: Annotated[
        Optional[bool],
        cyclopts.Parameter("--ui", help="Enable the UI. [from PREFECT_UI_ENABLED]"),
    ] = None,
    no_services: Annotated[
        bool,
        cyclopts.Parameter(
            "--no-services", negative="", help="Only run the webserver API and UI."
        ),
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

    from prefect.cli._server_utils import (
        SERVER_PID_FILE_NAME,
        _format_host_for_url,
        _run_in_background,
        _run_in_foreground,
        _validate_multi_worker,
        generate_welcome_blurb,
        prestart_check,
    )
    from prefect.settings import (
        PREFECT_API_SERVICES_LATE_RUNS_ENABLED,
        PREFECT_API_SERVICES_SCHEDULER_ENABLED,
        PREFECT_HOME,
        PREFECT_SERVER_API_HOST,
        PREFECT_SERVER_API_KEEPALIVE_TIMEOUT,
        PREFECT_SERVER_API_PORT,
        PREFECT_SERVER_LOGGING_LEVEL,
        PREFECT_UI_ENABLED,
    )

    # Resolve settings-backed defaults
    if host is None:
        host = PREFECT_SERVER_API_HOST.value()
    if port is None:
        port = PREFECT_SERVER_API_PORT.value()
    if keep_alive_timeout is None:
        keep_alive_timeout = PREFECT_SERVER_API_KEEPALIVE_TIMEOUT.value()
    if log_level is None:
        log_level = PREFECT_SERVER_LOGGING_LEVEL.value()
    if scheduler is None:
        scheduler = PREFECT_API_SERVICES_SCHEDULER_ENABLED.value()
    if late_runs is None:
        late_runs = PREFECT_API_SERVICES_LATE_RUNS_ENABLED.value()
    if ui is None:
        ui = PREFECT_UI_ENABLED.value()

    base_url = f"http://{_format_host_for_url(host)}:{port}"

    if _cli.is_interactive():
        try:
            prestart_check(_cli.console, base_url)
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

    _cli.console.print(generate_welcome_blurb(base_url, ui_enabled=ui))
    _cli.console.print("\n")

    if workers > 1:
        _cli.console.print(
            f"Starting server with {workers} worker processes.\n", style="blue"
        )

    if background:
        _run_in_background(
            _cli.console,
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
            _cli.console,
            server_settings,
            host,
            port,
            keep_alive_timeout,
            no_services,
            workers,
        )


@server_app.command()
@with_cli_exception_handling
async def status(
    *,
    wait: Annotated[
        bool,
        cyclopts.Parameter(
            "--wait",
            help="Wait for the server to become available before returning.",
        ),
    ] = False,
    timeout: Annotated[
        int,
        cyclopts.Parameter(
            "--timeout",
            alias="-t",
            help=(
                "Maximum number of seconds to wait when using --wait. "
                "A value of 0 means wait indefinitely."
            ),
        ),
    ] = 0,
    output: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--output",
            alias="-o",
            help="Specify an output format. Currently supports: json",
        ),
    ] = None,
):
    """Check the status of the Prefect server."""
    import json as json_mod

    from prefect.client.orchestration import get_client
    from prefect.settings import get_current_settings

    if output is not None and output.lower() != "json":
        exit_with_error("Only 'json' output format is supported.")

    is_json = output is not None

    api_url = get_current_settings().api.url
    if api_url is None:
        exit_with_error(
            "No API URL configured. Set PREFECT_API_URL to the address of your server."
        )

    if not is_json:
        _cli.console.print(f"Connecting to server at {api_url}...")

    start_time = _monotonic()

    async with get_client() as client:
        while True:
            healthcheck_exc = await client.api_healthcheck()

            elapsed = _monotonic() - start_time
            deadline_exceeded = wait and timeout > 0 and elapsed >= timeout

            if deadline_exceeded and healthcheck_exc is not None:
                result: dict[str, object] = {
                    "status": "timed_out",
                    "api_url": api_url,
                    "timeout": timeout,
                    "error": str(healthcheck_exc),
                }
                if is_json:
                    _cli.console.print(json_mod.dumps(result, indent=2))
                    raise SystemExit(1)
                exit_with_error(
                    f"Timed out after {timeout} seconds waiting for server "
                    f"at {api_url}."
                )

            if healthcheck_exc is None:
                try:
                    server_version = await client.api_version()
                except Exception:
                    server_version = None

                result = {
                    "status": "available",
                    "api_url": api_url,
                }
                if server_version is not None:
                    result["server_version"] = server_version

                if is_json:
                    _cli.console.print(json_mod.dumps(result, indent=2))
                else:
                    _cli.console.print("Server is available.")
                    _cli.console.print(f"  API URL: {api_url}")
                    if server_version is not None:
                        _cli.console.print(f"  Server version: {server_version}")
                return

            if not wait:
                result = {
                    "status": "unavailable",
                    "api_url": api_url,
                    "error": str(healthcheck_exc),
                }
                if is_json:
                    _cli.console.print(json_mod.dumps(result, indent=2))
                    raise SystemExit(1)
                exit_with_error(
                    f"Server is not available at {api_url}. Error: {healthcheck_exc}"
                )

            await asyncio.sleep(1)


@server_app.command()
@with_cli_exception_handling
async def stop():
    """Stop a Prefect server instance running in the background."""
    from prefect.cli._server_utils import SERVER_PID_FILE_NAME
    from prefect.settings import PREFECT_HOME

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
    _cli.console.print("Server stopped!")


# --- database subcommands ---


@database_app.command()
@with_cli_exception_handling
async def reset(
    *,
    yes: Annotated[
        bool, cyclopts.Parameter("--yes", alias="-y", help="Skip confirmation.")
    ] = False,
):
    """Drop and recreate all Prefect database tables."""
    from prefect.server.database import provide_database_interface

    db = provide_database_interface()
    engine = await db.engine()

    if not yes:
        from rich.prompt import Confirm

        if not Confirm.ask(
            "Are you sure you want to reset the Prefect database located "
            f'at "{engine.url!r}"? This will drop and recreate all tables.',
            console=_cli.console,
        ):
            exit_with_error("Database reset aborted")

    _cli.console.print("Downgrading database...")
    await db.drop_db()
    _cli.console.print("Upgrading database...")
    await db.create_db()
    exit_with_success(f'Prefect database "{engine.url!r}" reset!')


@database_app.command()
@with_cli_exception_handling
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

    db = provide_database_interface()
    engine = await db.engine()

    if not yes:
        from rich.prompt import Confirm

        if not Confirm.ask(
            f"Are you sure you want to upgrade the Prefect database at {engine.url!r}?",
            console=_cli.console,
        ):
            exit_with_error("Database upgrade aborted!")

    _cli.console.print("Running upgrade migrations ...")
    await run_sync_in_worker_thread(alembic_upgrade, revision=revision, dry_run=dry_run)
    _cli.console.print("Migrations succeeded!")
    exit_with_success(f"Prefect database at {engine.url!r} upgraded!")


@database_app.command()
@with_cli_exception_handling
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

    db = provide_database_interface()
    engine = await db.engine()

    if not yes:
        from rich.prompt import Confirm

        if not Confirm.ask(
            "Are you sure you want to downgrade the Prefect "
            f"database at {engine.url!r}?",
            console=_cli.console,
        ):
            exit_with_error("Database downgrade aborted!")

    _cli.console.print("Running downgrade migrations ...")
    await run_sync_in_worker_thread(
        alembic_downgrade, revision=revision, dry_run=dry_run
    )
    _cli.console.print("Migrations succeeded!")
    exit_with_success(f"Prefect database at {engine.url!r} downgraded!")


@database_app.command()
@with_cli_exception_handling
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

    _cli.console.print("Running migration file creation ...")
    await run_sync_in_worker_thread(
        alembic_revision, message=message, autogenerate=autogenerate
    )
    exit_with_success("Creating new migration file succeeded!")


@database_app.command()
@with_cli_exception_handling
async def stamp(revision: str):
    """Stamp the revision table with the given revision; don't run any migrations."""
    from prefect.server.database.alembic_commands import alembic_stamp
    from prefect.utilities.asyncutils import run_sync_in_worker_thread

    _cli.console.print("Stamping database with revision ...")
    await run_sync_in_worker_thread(alembic_stamp, revision=revision)
    exit_with_success("Stamping database with revision succeeded!")


# --- services subcommands ---


@services_app.command(name="ls", alias="list")
@with_cli_exception_handling
def list_services():
    """List all available services and their status."""
    from prefect.server.services.base import Service

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

    _cli.console.print(table)


@services_app.command(name="start", alias="enable")
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
    from prefect.cli._server_utils import (
        SERVICES_PID_FILE,
        _cleanup_pid_file,
        _is_process_running,
        _read_pid_file,
        _run_all_services,
        _write_pid_file,
    )
    from prefect.server.services.base import Service

    SERVICES_PID_FILE.parent.mkdir(parents=True, exist_ok=True)

    if SERVICES_PID_FILE.exists():
        pid = _read_pid_file(SERVICES_PID_FILE)
        if pid is not None and _is_process_running(pid):
            _cli.console.print(
                "\n[yellow]Services are already running in the background.[/]"
                "\n[blue]Use[/] [yellow]`prefect server services stop`[/] [blue]to stop them.[/]"
            )
            raise SystemExit(1)
        else:
            _cleanup_pid_file(SERVICES_PID_FILE)

    if not Service.enabled_services():
        _cli.console.print("[red]No services are enabled![/]")
        raise SystemExit(1)

    if not background:
        _cli.console.print("\n[blue]Starting services... Press CTRL+C to stop[/]\n")
        try:
            asyncio.run(_run_all_services())
        except KeyboardInterrupt:
            pass
        _cli.console.print("\n[green]All services stopped.[/]")
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
        _cli.console.print("[red]Failed to start services in the background![/]")
        raise SystemExit(1)

    _write_pid_file(SERVICES_PID_FILE, process.pid)
    _cli.console.print(
        "\n[green]Services are running in the background.[/]"
        "\n[blue]Use[/] [yellow]`prefect server services stop`[/] [blue]to stop them.[/]"
    )


@services_app.command(name="stop", alias="disable")
@with_cli_exception_handling
async def stop_services():
    """Stop any background Prefect services that were started."""
    from prefect.cli._server_utils import (
        SERVICES_PID_FILE,
        _cleanup_pid_file,
        _is_process_running,
        _read_pid_file,
    )

    if not SERVICES_PID_FILE.exists():
        _cli.console.print("No services are running in the background.")
        raise SystemExit(0)

    if (pid := _read_pid_file(SERVICES_PID_FILE)) is None:
        _cleanup_pid_file(SERVICES_PID_FILE)
        _cli.console.print("No valid PID file found.")
        raise SystemExit(0)

    if not _is_process_running(pid):
        _cli.console.print("[yellow]Services were not running[/]")
        _cleanup_pid_file(SERVICES_PID_FILE)
        return

    _cli.console.print("\n[yellow]Shutting down...[/]")
    try:
        if os.name == "nt":
            os.kill(pid, signal.CTRL_C_EVENT)
        else:
            os.kill(pid, signal.SIGTERM)
    except (ProcessLookupError, OSError):
        pass

    for _ in range(5):
        if not _is_process_running(pid):
            _cli.console.print("[dim]\u2713 Services stopped[/]")
            break
        await asyncio.sleep(1)

    _cleanup_pid_file(SERVICES_PID_FILE)
    _cli.console.print("\n[green]All services stopped.[/]")


# Hidden manager command (used by --background)
_manager_app = cyclopts.App(
    name="manager", help="Internal entrypoint for background services.", show=False
)
services_app.command(_manager_app)


@_manager_app.default
@with_cli_exception_handling
def run_manager_process():
    """Internal entrypoint for background services."""
    from prefect.cli._server_utils import _run_all_services
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
