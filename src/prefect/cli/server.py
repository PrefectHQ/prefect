"""
Command line interface for working with the Prefect API and server.
"""

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
from typing import Any

import anyio
import anyio.abc
import typer
import uvicorn
from rich.table import Table

import prefect
import prefect.settings
from prefect.cli._prompts import prompt
from prefect.cli._types import PrefectTyper, SettingsOption
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.cloud import prompt_select_from_list
from prefect.cli.root import app, is_interactive
from prefect.logging import get_logger
from prefect.settings import (
    PREFECT_API_SERVICES_LATE_RUNS_ENABLED,
    PREFECT_API_SERVICES_SCHEDULER_ENABLED,
    PREFECT_API_URL,
    PREFECT_HOME,
    PREFECT_SERVER_ANALYTICS_ENABLED,
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

server_app = PrefectTyper(
    name="server",
    help="Start a Prefect server instance and interact with the database",
)
database_app = PrefectTyper(name="database", help="Interact with the database.")
services_app = PrefectTyper(name="services", help="Interact with the services.")
server_app.add_typer(database_app)
server_app.add_typer(services_app)
app.add_typer(server_app)

logger = get_logger(__name__)

PID_FILE = "server.pid"


def generate_welcome_blurb(base_url: str, ui_enabled: bool):
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


def prestart_check(base_url: str):
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

    pid_file = Path(PREFECT_HOME.value() / PID_FILE)
    # check if port is already in use
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host, port))
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
        _run_in_foreground(
            pid_file, server_settings, host, port, keep_alive_timeout, no_services
        )


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
    pid_file: Path,
    server_settings: dict[str, str],
    host: str,
    port: int,
    keep_alive_timeout: int,
    no_services: bool,
) -> None:
    from prefect.server.api.server import create_app

    with temporary_settings(
        {getattr(prefect.settings, k): v for k, v in server_settings.items()}
    ):
        uvicorn.run(
            app=create_app(final=True, webserver_only=no_services),
            app_dir=str(prefect.__module_path__.parent),
            host=host,
            port=port,
            timeout_keep_alive=keep_alive_timeout,
        )


@server_app.command()
async def stop():
    """Stop a Prefect server instance running in the background"""
    pid_file = anyio.Path(PREFECT_HOME.value() / PID_FILE)
    if not await pid_file.exists():
        exit_with_success("No server running in the background.")
    pid = int(await pid_file.read_text())
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        exit_with_success(
            "The server process is not running. Cleaning up stale PID file."
        )
    finally:
        # The file probably exists, but use `missing_ok` to avoid an
        # error if the file was deleted by another actor
        await pid_file.unlink(missing_ok=True)
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


def _discover_services() -> (
    tuple[
        list[type[prefect.server.services.loop_service.LoopService]],
        dict[str, prefect.settings.Setting],
    ]
):
    """Discover all available services and their settings"""

    from prefect.server.events.services import triggers
    from prefect.server.services import (
        cancellation_cleanup,
        flow_run_notifications,
        foreman,
        late_runs,
        loop_service,
        pause_expirations,
        scheduler,
        task_run_recorder,
        telemetry,
    )

    # Map of service names to their settings
    service_settings = {
        "Telemetry": prefect.settings.PREFECT_SERVER_ANALYTICS_ENABLED,
        "TaskRunRecorder": prefect.settings.PREFECT_API_SERVICES_TASK_RUN_RECORDER_ENABLED,
        "EventPersister": prefect.settings.PREFECT_API_SERVICES_EVENT_PERSISTER_ENABLED,
        "Distributor": prefect.settings.PREFECT_API_EVENTS_STREAM_OUT_ENABLED,
        "Scheduler": prefect.settings.PREFECT_API_SERVICES_SCHEDULER_ENABLED,
        "RecentDeploymentsScheduler": prefect.settings.PREFECT_API_SERVICES_SCHEDULER_ENABLED,
        "MarkLateRuns": prefect.settings.PREFECT_API_SERVICES_LATE_RUNS_ENABLED,
        "FailExpiredPauses": prefect.settings.PREFECT_API_SERVICES_PAUSE_EXPIRATIONS_ENABLED,
        "CancellationCleanup": prefect.settings.PREFECT_API_SERVICES_CANCELLATION_CLEANUP_ENABLED,
        "FlowRunNotifications": prefect.settings.PREFECT_API_SERVICES_FLOW_RUN_NOTIFICATIONS_ENABLED,
        "Foreman": prefect.settings.PREFECT_API_SERVICES_FOREMAN_ENABLED,
        "ReactiveTriggers": prefect.settings.PREFECT_API_SERVICES_TRIGGERS_ENABLED,
        "ProactiveTriggers": prefect.settings.PREFECT_API_SERVICES_TRIGGERS_ENABLED,
        "Actions": prefect.settings.PREFECT_API_SERVICES_TRIGGERS_ENABLED,
    }

    # Find all service classes by inspecting modules
    service_modules = [
        cancellation_cleanup,
        flow_run_notifications,
        foreman,
        late_runs,
        pause_expirations,
        scheduler,
        task_run_recorder,
        telemetry,
        triggers,
    ]

    discovered_services: list[type[loop_service.LoopService]] = []
    for module in service_modules:
        for _, obj in inspect.getmembers(module):
            if (
                inspect.isclass(obj)
                and issubclass(obj, loop_service.LoopService)
                and obj != loop_service.LoopService
            ):
                discovered_services.append(obj)

    return discovered_services, service_settings


def _get_service_map(
    discovered_services: list[type[prefect.server.services.loop_service.LoopService]],
    service_settings: dict[str, prefect.settings.Setting],
) -> dict[str, Any]:
    """Create a map of service names to their classes and settings"""
    return {
        service_class.__name__: (
            service_class,
            service_settings.get(service_class.__name__, False),
        )
        for service_class in discovered_services
    }


@services_app.command(aliases=["ls", "list"])
async def list_services():
    """List all services"""
    import inspect

    discovered_services, service_settings = _discover_services()
    service_map = _get_service_map(discovered_services, service_settings)

    # Get currently running services
    running_services = _check_for_running_services()

    table = Table(
        title="Available Services",
        expand=True,
    )
    table.add_column("Name", style="blue", no_wrap=True)
    table.add_column("Status", style="green", no_wrap=True)
    table.add_column("Description", style="cyan", no_wrap=False)

    for name, (service_class, setting) in sorted(service_map.items()):
        enabled = setting.value()
        running = name.lower() in running_services

        if running:
            status = "Running"
            status_style = "green"
        elif enabled:
            status = "Enabled"
            status_style = "yellow"
        else:
            status = "Disabled"
            status_style = "red"

        description = ""
        if doc := inspect.getdoc(service_class):
            description = doc.split("\n")[0].strip()
            if len(description) > 60:
                description = description[:57] + "..."

        table.add_row(name, status, description, style=status_style)

    app.console.print(table)


@services_app.command(aliases=["stop"])
async def stop_services():
    """Stop all background services"""
    pid_dir = Path(PREFECT_HOME.value() / "services")
    if not pid_dir.exists():
        exit_with_success("No services are running in the background.")

    if not (pid_files := list(pid_dir.glob("*.pid"))):
        exit_with_success("No services are running in the background.")

    app.console.print("\n[yellow]Shutting down...[/]")
    for pid_file in pid_files:
        service_name = pid_file.stem.title()  # Display in title case
        try:
            pid = int(pid_file.read_text())
            try:
                os.kill(pid, signal.SIGTERM)
                app.console.print(f"[dim]✓ {service_name}[/]")
            except ProcessLookupError:
                app.console.print(
                    f"[yellow]Process for {service_name} was not running[/]"
                )
        except (ValueError, OSError) as e:
            app.console.print(f"[red]✗ {service_name}: {str(e)}[/]")
        finally:
            pid_file.unlink(missing_ok=True)

    try:
        pid_dir.rmdir()
    except OSError:
        pass

    app.console.print("\n[green]All services stopped.[/]")


def _check_for_running_services() -> list[str]:
    """Check for any running services and return their names. Also cleans up stale PID files."""
    pid_dir = Path(PREFECT_HOME.value() / "services")
    if not pid_dir.exists():
        return []

    running_services: list[str] = []
    for pid_file in pid_dir.glob("*.pid"):
        try:
            pid = int(pid_file.read_text())
            os.kill(pid, 0)
            # Store lowercase for matching, but title case for display
            running_services.append(pid_file.stem)
        except (ProcessLookupError, ValueError, OSError):
            # Process doesn't exist or invalid PID, clean up stale file
            pid_file.unlink(missing_ok=True)

    return running_services


@services_app.command(aliases=["start"])
async def start_services(
    background: bool = typer.Option(
        False, "--background", "-b", help="Run the services in the background"
    ),
):
    """Start all enabled Prefect services"""
    if running_services := _check_for_running_services():
        app.console.print(
            "\n[yellow]Services are already running in the background:[/]"
        )
        for service in running_services:
            app.console.print(f"[dim]• {service}[/]")
        app.console.print(
            "\n[blue]Use[/] [yellow]`prefect server services stop`[/] [blue]to stop them first.[/]"
        )
        return

    discovered_services, service_settings = _discover_services()
    service_map = _get_service_map(discovered_services, service_settings)

    service_instances: list[prefect.server.services.loop_service.LoopService] = []
    for _, (service_class, setting) in service_map.items():
        if setting.value():
            service_instances.append(service_class())

    if not service_instances:
        exit_with_error("No services are enabled!")

    if background:
        pid_dir = Path(PREFECT_HOME.value() / "services")
        pid_dir.mkdir(parents=True, exist_ok=True)

        processes: list[subprocess.Popen[Any]] = []
        for service in service_instances:
            module_name = service.__class__.__module__.split(".")[-1]
            command = [
                sys.executable,
                "-m",
                f"prefect.server.services.{module_name}",
            ]

            process = subprocess.Popen(
                command,
                env={**os.environ},
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            processes.append(process)

            pid_file = pid_dir / f"{service.name.lower()}.pid"
            pid_file.write_text(str(process.pid))

            try:
                if process.poll() is not None:
                    app.console.print(f"[red]✗ {service.name}: Failed to start[/]")
                    stderr = process.stderr.read().decode() if process.stderr else ""
                    if stderr:
                        app.console.print(f"[red]{stderr}[/]")
                    continue
            except Exception as e:
                app.console.print(f"[red]✗ {service.name}: {str(e)}[/]")
                continue

            app.console.print(f"[dim]✓ {service.name}[/]")

        app.console.print(
            "\n[green]Services are running in the background.[/]"
            "\n[blue]Use[/] [yellow]`prefect server services list`[/] [blue]to check their status.[/]"
            "\n[blue]Use[/] [yellow]`prefect server services stop`[/] [blue]to stop them.[/]"
        )
    else:
        app.console.print("\n[blue]Starting services... Press CTRL+C to stop[/]\n")

        service_tasks: list[
            tuple[asyncio.Task[None], prefect.server.services.loop_service.LoopService]
        ] = []

        for service in service_instances:
            task = asyncio.create_task(service.start())
            service_tasks.append((task, service))
            app.console.print(f"[dim]✓ {service.name}[/]")

        app.console.print()  # Add blank line after startup
        shutdown_event = asyncio.Event()

        def handle_signal(signum: int, frame: Any):
            app.console.print("\n[yellow]Shutting down...[/]")
            for task, _ in service_tasks:
                task.cancel()
            asyncio.get_event_loop().call_soon_threadsafe(shutdown_event.set)

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        try:
            await asyncio.gather(*(task for task, _ in service_tasks))
        except asyncio.CancelledError:
            await shutdown_event.wait()
            results = await asyncio.gather(
                *(task for task, _ in service_tasks), return_exceptions=True
            )
            for (_, service), result in zip(service_tasks, results):
                if isinstance(result, asyncio.CancelledError):
                    app.console.print(f"[dim]Stopped {service.name}[/]")
                elif isinstance(result, Exception):
                    app.console.print(f"[red]Failed {service.name}: {result}[/]")
                else:
                    app.console.print(f"[dim]Stopped {service.name}[/]")
        finally:
            app.console.print("\n[green]All services stopped.[/]")
