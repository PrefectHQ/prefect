"""Shared server utilities used by both typer and cyclopts CLI implementations."""

from __future__ import annotations

import ipaddress
import os
import shlex
import subprocess
import sys
import textwrap
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Callable

import uvicorn

import prefect
import prefect.settings
from prefect.cli._cloud_utils import prompt_select_from_list
from prefect.cli._prompts import prompt
from prefect.logging import get_logger
from prefect.settings import (
    PREFECT_API_URL,
    PREFECT_HOME,
    PREFECT_SERVER_API_BASE_PATH,
    Profile,
    get_current_settings,
    load_current_profile,
    load_profiles,
    save_profiles,
    update_current_profile,
)
from prefect.settings.context import temporary_settings

if TYPE_CHECKING:
    from rich.console import Console

logger = get_logger(__name__)

SERVER_PID_FILE_NAME = "server.pid"
SERVICES_PID_FILE = Path(PREFECT_HOME.value()) / "services.pid"


def _format_host_for_url(host: str) -> str:
    """Format a host for use in a URL, adding brackets for IPv6 addresses."""
    try:
        ip = ipaddress.ip_address(host)
        if ip.version == 6:
            return f"[{host}]"
    except ValueError:
        pass  # not an IP address (e.g., hostname)
    return host


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


def prestart_check(console: "Console", base_url: str) -> None:
    """Check if PREFECT_API_URL is set in the current profile. If not, prompt the user to set it.

    Args:
        console: Rich console for output
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
            console.print(
                f"Switched to profile {profiles_with_matching_url[0]!r}",
                style="green",
            )
            return
        elif len(profiles_with_matching_url) > 1:
            console.print(
                "Your current profile doesn't have `PREFECT_API_URL` set to the address"
                " of the server that's running. Some of your other profiles do."
            )
            selected_profile = prompt_select_from_list(
                console,
                "Which profile would you like to switch to?",
                sorted(
                    [profile for profile in profiles_with_matching_url],
                ),
            )
            profiles.set_active(selected_profile)
            save_profiles(profiles)
            console.print(f"Switched to profile {selected_profile!r}", style="green")
            return

        console.print(
            "The `PREFECT_API_URL` setting for your current profile doesn't match the"
            " address of the server that's running. You need to set it to communicate"
            " with the server.",
            style="yellow",
        )

        choice = prompt_select_from_list(
            console,
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
                    console.print(
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

            console.print(f"Switched to new profile {profile_name!r}", style="green")
        elif choice == "set":
            api_url = prompt(
                "Enter the `PREFECT_API_URL` value", default="http://127.0.0.1:4200/api"
            )
            update_current_profile({PREFECT_API_URL: api_url})
            console.print(
                f"Set `PREFECT_API_URL` to {api_url!r} in the current profile {current_profile.name!r}",
                style="green",
            )


def _validate_multi_worker(workers: int, exit_fn: Callable[[str], object]) -> None:
    """Validate configuration for multi-worker mode.

    Args:
        workers: Number of worker processes.
        exit_fn: Called with an error message when validation fails (e.g.
            ``exit_with_error``).
    """
    from prefect.server.utilities.database import get_dialect

    if workers == 1:
        return

    if workers < 1:
        exit_fn("Number of workers must be >= 1")

    settings = get_current_settings()

    try:
        dialect = get_dialect(
            settings.server.database.connection_url.get_secret_value()
        )
    except Exception as e:
        exit_fn(f"Unable to validate database configuration: {e}")

    if dialect.name != "postgresql":
        exit_fn(
            "Multi-worker mode (--workers > 1) is not supported with SQLite database."
        )

    try:
        messaging_cache = settings.server.events.messaging_cache
        messaging_broker = settings.server.events.messaging_broker
        causal_ordering = settings.server.events.causal_ordering
        lease_storage = settings.server.concurrency.lease_storage
    except Exception as e:
        exit_fn(f"Unable to validate messaging configuration: {e}")

    if (
        messaging_cache == "prefect.server.utilities.messaging.memory"
        or messaging_broker == "prefect.server.utilities.messaging.memory"
        or causal_ordering == "prefect.server.events.ordering.memory"
        or lease_storage == "prefect.server.concurrency.lease_storage.memory"
    ):
        error_message = textwrap.dedent(
            """
            Multi-worker mode (--workers > 1) requires Redis for messaging and lease storage.

            Please configure the following settings to use Redis:

                prefect config set PREFECT_MESSAGING_BROKER="prefect_redis.messaging"
                prefect config set PREFECT_MESSAGING_CACHE="prefect_redis.messaging"
                prefect config set PREFECT_SERVER_EVENTS_CAUSAL_ORDERING="prefect_redis.ordering"
                prefect config set PREFECT_SERVER_CONCURRENCY_LEASE_STORAGE="prefect_redis.lease_storage"

            You'll also need to configure your Redis connection:

                export PREFECT_REDIS_MESSAGING_HOST="your-redis-host"
                export PREFECT_REDIS_MESSAGING_PORT="6379"
                export PREFECT_REDIS_MESSAGING_DB="0"

            For complete setup instructions, see:
            https://docs.prefect.io/v3/how-to-guides/self-hosted/server-cli#multi-worker-api-server
            https://docs.prefect.io/v3/advanced/self-hosted#redis-setup
            """
        ).strip()
        exit_fn(error_message)


def _run_in_background(
    console: "Console",
    pid_file: Path,
    server_settings: dict[str, str],
    host: str,
    port: int,
    keep_alive_timeout: int,
    no_services: bool,
    workers: int,
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
        "--workers",
        str(workers),
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

    console.print(
        "The Prefect server is running in the background. Run `prefect"
        " server stop` to stop it."
    )


def _run_in_foreground(
    console: "Console",
    server_settings: dict[str, str],
    host: str,
    port: int,
    keep_alive_timeout: int,
    no_services: bool,
    workers: int,
) -> None:
    from prefect.server.api.server import create_app

    try:
        with temporary_settings(
            {getattr(prefect.settings, k): v for k, v in server_settings.items()}
        ):
            if workers == 1:
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

            else:
                os.environ["PREFECT__SERVER_FINAL"] = "1"
                os.environ["PREFECT__SERVER_WEBSERVER_ONLY"] = "1"

                uvicorn.run(
                    app="prefect.server.api.server:create_app",
                    factory=True,
                    host=host,
                    port=port,
                    timeout_keep_alive=keep_alive_timeout,
                    log_level=server_settings.get(
                        "PREFECT_SERVER_LOGGING_LEVEL", "info"
                    ).lower(),
                    workers=workers,
                )

    finally:
        console.print("Server stopped!")


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


async def _run_all_services() -> None:
    """Run Service-based services and docket-based perpetual services."""
    from docket import Docket

    from prefect.server.api.background_workers import background_worker
    from prefect.server.services.base import Service
    from prefect.settings.context import get_current_settings

    docket_url = get_current_settings().server.docket.url

    async with Docket(
        name="prefect", url=docket_url, execution_ttl=timedelta(0)
    ) as docket:
        async with background_worker(docket, ephemeral=False, webserver_only=False):
            # Run Service-based services (will block until shutdown)
            await Service.run_services()
