"""
Command line interface for working with Prefect
"""

import logging
import os
import shlex
import socket
import sys
import textwrap

import anyio
import anyio.abc
import typer

import prefect
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
from prefect.utilities.asyncutils import run_sync_in_worker_thread
from prefect.utilities.processutils import (
    consume_process_output,
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

PID_FILE = "server.pid"


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
async def start(
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

    server_env = os.environ.copy()
    server_env["PREFECT_API_SERVICES_SCHEDULER_ENABLED"] = str(scheduler)
    server_env["PREFECT_SERVER_ANALYTICS_ENABLED"] = str(analytics)
    server_env["PREFECT_API_SERVICES_LATE_RUNS_ENABLED"] = str(late_runs)
    server_env["PREFECT_API_SERVICES_UI"] = str(ui)
    server_env["PREFECT_UI_ENABLED"] = str(ui)
    server_env["PREFECT_SERVER_LOGGING_LEVEL"] = log_level

    pid_file = anyio.Path(PREFECT_HOME.value() / PID_FILE)
    # check if port is already in use
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host, port))
    except socket.error:
        if await pid_file.exists():
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
            await pid_file.touch(mode=0o600, exist_ok=False)
        except FileExistsError:
            exit_with_error(
                "A server is already running in the background. To stop it,"
                " run `prefect server stop`."
            )

    app.console.print(generate_welcome_blurb(base_url, ui_enabled=ui))
    app.console.print("\n")

    try:
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
        process = await anyio.open_process(
            command=command,
            env=server_env,
        )

        process_id = process.pid
        if background:
            await pid_file.write_text(str(process_id))

            app.console.print(
                "The Prefect server is running in the background. Run `prefect"
                " server stop` to stop it."
            )
            return

        async with process:
            # Explicitly handle the interrupt signal here, as it will allow us to
            # cleanly stop the uvicorn server. Failing to do that may cause a
            # large amount of anyio error traces on the terminal, because the
            # SIGINT is handled by Typer/Click in this process (the parent process)
            # and will start shutting down subprocesses:
            # https://github.com/PrefectHQ/server/issues/2475

            setup_signal_handlers_server(
                process_id, "the Prefect server", app.console.print
            )

            await consume_process_output(process, sys.stdout, sys.stderr)

    except anyio.EndOfStream:
        logging.error("Subprocess stream ended unexpectedly")
    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")

    app.console.print("Server stopped!")


@server_app.command()
async def stop():
    """Stop a Prefect server instance running in the background"""
    pid_file = anyio.Path(PREFECT_HOME.value() / PID_FILE)
    if not await pid_file.exists():
        exit_with_success("No server running in the background.")
    pid = int(await pid_file.read_text())
    try:
        os.kill(pid, 15)
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
