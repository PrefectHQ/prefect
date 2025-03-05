"""
Command line interface for working with the Prefect API and server.
"""

from __future__ import annotations

import asyncio
import inspect
import os
import shlex
import signal
import socket
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import TYPE_CHECKING

import typer
import uvicorn
from rich.table import Table
from rich.text import Text

import prefect
import prefect.settings
from prefect.cli._prompts import prompt
from prefect.cli._types import PrefectTyper, SettingsOption
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.cloud import prompt_select_from_list
from prefect.cli.root import app, is_interactive
from prefect.logging import get_logger
from prefect.server.services.base import Service
from prefect.settings import (
    PREFECT_API_SERVICES_LATE_RUNS_ENABLED,
    PREFECT_API_SERVICES_SCHEDULER_ENABLED,
    PREFECT_API_URL,
    PREFECT_HOME,
    PREFECT_SERVER_ANALYTICS_ENABLED,
    PREFECT_SERVER_API_BASE_PATH,
    PREFECT_SERVER_API_HOST,
    PREFECT_SERVER_API_KEEPALIVE_TIMEOUT,
    PREFECT_SERVER_API_PORT,
    PREFECT_SERVER_LOGGING_LEVEL,
    PREFECT_UI_ENABLED,
    Profile,
    load_current_profile,
    load_profiles,
    save_profiles,
    update_current_profile,
)
from prefect.settings.context import temporary_settings
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

SERVER_PID_FILE_NAME = "server.pid"
SERVICES_PID_FILE = Path(PREFECT_HOME.value()) / "services.pid"


def generate_welcome_blurb(base_url: str, ui_enabled: bool) -> str:
    if PREFECT_SERVER_API_BASE_PATH:
        suffix = PREFECT_SERVER_API_BASE_PATH.value()
    else:
        suffix = "/api"

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
    ).format(api_url=base_url + suffix, docs_url=base_url + "/docs")

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


def prestart_check(base_url: str) -> None:
    """
    Check if `PREFECT_API_URL` is set in the current profile. If not, prompt the user to set it.

    Args:
        base_url: The base URL the server will be running on
    """
    api_url = f"{base_url}/api"
    current_profile = load_current_profile()
    profiles = load_profiles()
    if current_profile and PREFECT_API_URL not in current_profile.settings:
        profiles_with_matching_url = [
            name
            for name, profile in profiles.items()
            if profile.settings.get(PREFECT_API_URL) == api_url
        ]
        if len(profiles_with_matching_url) == 1:
            profiles.set_active(profiles_with_matching_url[0])
            save_profiles(profiles)
            app.console.print(
                f"Switched to profile {profiles_with_matching_url[0]!r}",
                style="green",
            )
            return
        elif len(profiles_with_matching_url) > 1:
            app.console.print(
                "Your current profile doesn't have `PREFECT_API_URL` set to the address"
                " of the server that's running. Some of your other profiles do."
            )
            selected_profile = prompt_select_from_list(
                app.console,
                "Which profile would you like to switch to?",
                sorted(
                    [profile for profile in profiles_with_matching_url],
                ),
            )
            profiles.set_active(selected_profile)
            save_profiles(profiles)
            app.console.print(
                f"Switched to profile {selected_profile!r}", style="green"
            )
            return

        app.console.print(
            "The `PREFECT_API_URL` setting for your current profile doesn't match the"
            " address of the server that's running. You need to set it to communicate"
            " with the server.",
            style="yellow",
        )

        choice = prompt_select_from_list(
            app.console,
            "How would you like to proceed?",
            [
                (
                    "create",
                    "Create a new profile with `PREFECT_API_URL` set and switch to it",
                ),
                (
                    "set",
                    f"Set `PREFECT_API_URL` in the current profile: {current_profile.name!r}",
                ),
            ],
        )

        if choice == "create":
            while True:
                profile_name = prompt("Enter a new profile name")
                if profile_name in profiles:
                    app.console.print(
                        f"Profile {profile_name!r} already exists. Please choose a different name.",
                        style="red",
                    )
                else:
                    break

            profiles.add_profile(
                Profile(
                    name=profile_name, settings={PREFECT_API_URL: f"{base_url}/api"}
                )
            )
            profiles.set_active(profile_name)
            save_profiles(profiles)

            app.console.print(
                f"Switched to new profile {profile_name!r}", style="green"
            )
        elif choice == "set":
            api_url = prompt(
                "Enter the `PREFECT_API_URL` value", default="http://127.0.0.1:4200/api"
            )
            update_current_profile({PREFECT_API_URL: api_url})
            app.console.print(
                f"Set `PREFECT_API_URL` to {api_url!r} in the current profile {current_profile.name!r}",
                style="green",
            )


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
):
    """
    Start a Prefect server instance
    """
    base_url = f"http://{host}:{port}"
    if is_interactive():
        try:
            prestart_check(base_url)
        except Exception:
            pass

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
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
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

    if background:
        _run_in_background(
            pid_file, server_settings, host, port, keep_alive_timeout, no_services
        )
    else:
        _run_in_foreground(server_settings, host, port, keep_alive_timeout, no_services)


def _run_in_background(
    pid_file: Path,
    server_settings: dict[str, str],
    host: str,
    port: int,
    keep_alive_timeout: int,
    no_services: bool,
) -> None:
    command = [
        sys.executable,
        "-m",
        "uvicorn",
        "--app-dir",
        str(prefect.__module_path__.parent),
        "--factory",
        "prefect.server.api.server:create_app",
        "--host",
        str(host),
        "--port",
        str(port),
        "--timeout-keep-alive",
        str(keep_alive_timeout),
    ]
    logger.debug("Opening server process with command: %s", shlex.join(command))

    env = {**os.environ, **server_settings, "PREFECT__SERVER_FINAL": "1"}
    if no_services:
        env["PREFECT__SERVER_WEBSERVER_ONLY"] = "1"

    process = subprocess.Popen(
        command,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    process_id = process.pid
    pid_file.write_text(str(process_id))

    app.console.print(
        "The Prefect server is running in the background. Run `prefect"
        " server stop` to stop it."
    )


def _run_in_foreground(
    server_settings: dict[str, str],
    host: str,
    port: int,
    keep_alive_timeout: int,
    no_services: bool,
) -> None:
    from prefect.server.api.server import create_app

    try:
        with temporary_settings(
            {getattr(prefect.settings, k): v for k, v in server_settings.items()}
        ):
            uvicorn.run(
                app=create_app(final=True, webserver_only=no_services),
                app_dir=str(prefect.__module_path__.parent),
                host=host,
                port=port,
                timeout_keep_alive=keep_alive_timeout,
                log_level=server_settings.get(
                    "PREFECT_SERVER_LOGGING_LEVEL", "info"
                ).lower(),
            )
    finally:
        app.console.print("Server stopped!")


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


def _is_process_running(pid: int) -> bool:
    """Check if a process is running by attempting to send signal 0."""
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, OSError):
        return False


def _read_pid_file(path: Path) -> int | None:
    """Read and validate a PID from a file."""
    try:
        return int(path.read_text())
    except (ValueError, OSError, FileNotFoundError):
        return None


def _write_pid_file(path: Path, pid: int) -> None:
    """Write a PID to a file, creating parent directories if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(pid))


def _cleanup_pid_file(path: Path) -> None:
    """Remove PID file and try to cleanup empty parent directory."""
    path.unlink(missing_ok=True)
    try:
        path.parent.rmdir()
    except OSError:
        pass


# this is a hidden command used by the `prefect server services start --background` command
@services_app.command(hidden=True, name="manager")
def run_manager_process():
    """
    This is an internal entrypoint used by `prefect server services start --background`.
    Users do not call this directly.

    We do everything in sync so that the child won't exit until the user kills it.
    """
    if not Service.enabled_services():
        logger.error("No services are enabled! Exiting manager.")
        sys.exit(1)

    logger.debug("Manager process started. Starting services...")
    try:
        asyncio.run(Service.run_services())
    except KeyboardInterrupt:
        pass
    finally:
        logger.debug("Manager process has exited.")


# public, user-facing `prefect server services` commands
@services_app.command(aliases=["ls"])
def list_services():
    """List all available services and their status."""
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
            asyncio.run(Service.run_services())
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
