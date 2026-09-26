"""
Worker command — native cyclopts implementation.

Start and interact with workers.
"""

import asyncio
import json
import os
import signal
import stat
import subprocess
import sys
from enum import Enum
from pathlib import Path
from typing import Annotated
from uuid import uuid4

import cyclopts
import psutil
from filelock import FileLock, Timeout

import prefect.cli._app as _cli
from prefect.cli._utilities import (
    exit_with_error,
    with_cli_exception_handling,
)
from prefect.context import get_settings_context
from prefect.settings import PREFECT_HOME

WORKER_PID_FILE = Path(PREFECT_HOME.value()) / "worker.pid"
WORKER_LOG_FILE = Path(PREFECT_HOME.value()) / "worker.log"
WORKER_READY_ENV = "PREFECT__WORKER_READY_FILE"


def _worker_is_running(process: psutil.Process) -> bool:
    try:
        return process.is_running() and process.status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False


def _get_background_worker() -> tuple[psutil.Process, float, bool] | None:
    try:
        if os.name != "nt":
            info = WORKER_PID_FILE.lstat()
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) & 0o077
            ):
                return None
        identity = json.loads(WORKER_PID_FILE.read_text())
        process = psutil.Process(identity["pid"])
        if process.create_time() == identity["created"] and _worker_is_running(process):
            return process, identity["created"], identity.get("stopping", False)
    except (OSError, ValueError, KeyError, TypeError, psutil.Error):
        pass
    return None


def _write_background_worker(pid: int, created: float, stopping: bool = False) -> None:
    fd = os.open(WORKER_PID_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as pid_file:
        json.dump(
            {
                "pid": pid,
                "created": created,
                "stopping": stopping,
            },
            pid_file,
        )


def _worker_lock() -> FileLock:
    WORKER_PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    return FileLock(str(WORKER_PID_FILE) + ".lock", timeout=0)


worker_app: cyclopts.App = cyclopts.App(
    name="worker", help="Start and interact with workers."
)


class InstallPolicy(str, Enum):
    ALWAYS = "always"
    IF_NOT_PRESENT = "if-not-present"
    NEVER = "never"
    PROMPT = "prompt"


@worker_app.command()
@with_cli_exception_handling
async def start(
    *,
    worker_name: Annotated[
        str | None,
        cyclopts.Parameter(
            "--name", alias="-n", help="The name to give to the started worker."
        ),
    ] = None,
    work_pool_name: Annotated[
        str | None,
        cyclopts.Parameter(
            "--pool", alias="-p", help="The work pool the started worker should poll."
        ),
    ] = None,
    work_queues: Annotated[
        list[str] | None,
        cyclopts.Parameter(
            "--work-queue",
            alias="-q",
            help="Work queue names to pull from (repeatable).",
        ),
    ] = None,
    worker_type: Annotated[
        str | None,
        cyclopts.Parameter(
            "--type",
            alias="-t",
            help="The type of worker to start.",
        ),
    ] = None,
    prefetch_seconds: Annotated[
        int | None,
        cyclopts.Parameter(
            "--prefetch-seconds",
            help="Seconds to look ahead for scheduled flow runs. [from PREFECT_WORKER_PREFETCH_SECONDS]",
        ),
    ] = None,
    run_once: Annotated[
        bool,
        cyclopts.Parameter("--run-once", help="Only run worker polling once."),
    ] = False,
    limit: Annotated[
        int | None,
        cyclopts.Parameter(
            "--limit",
            alias="-l",
            help="Maximum concurrent flow runs.",
        ),
    ] = None,
    with_healthcheck: Annotated[
        bool,
        cyclopts.Parameter("--with-healthcheck", help="Start a healthcheck server."),
    ] = False,
    install_policy: Annotated[
        InstallPolicy,
        cyclopts.Parameter(
            "--install-policy",
            help="Install policy for worker packages.",
        ),
    ] = InstallPolicy.PROMPT,
    base_job_template: Annotated[
        Path | None,
        cyclopts.Parameter(
            "--base-job-template",
            help="Path to JSON file containing base job template.",
        ),
    ] = None,
    create_pool_if_not_found: Annotated[
        bool,
        cyclopts.Parameter(
            "--create-pool-if-not-found",
            help=(
                "Create the work pool if it does not exist. "
                "Set to false when the work pool is managed externally "
                "(e.g. via Terraform or another provisioning tool)."
            ),
        ),
    ] = True,
    background: Annotated[
        bool,
        cyclopts.Parameter("--background", alias="-b", help="Run in the background."),
    ] = False,
):
    """Start a worker process to poll a work pool for flow runs."""
    from prefect.cli._prompts import confirm
    from prefect.cli._worker_utils import (
        _check_work_pool_paused,
        _check_work_queues_paused,
        _find_package_for_worker_type,
        _install_package,
        _load_worker_class,
        _retrieve_worker_type_from_pool,
    )
    from prefect.settings import (
        PREFECT_API_URL,
        PREFECT_WORKER_HEARTBEAT_SECONDS,
        PREFECT_WORKER_PREFETCH_SECONDS,
    )
    from prefect.utilities.processutils import setup_signal_handlers_worker

    # Prompt for work pool name if not provided (matches typer's prompt=True)
    if work_pool_name is None:
        if _cli.is_interactive():
            from rich.prompt import Prompt

            work_pool_name = Prompt.ask("Work pool name", console=_cli.console)
        else:
            exit_with_error("Missing required option '--pool' / '-p'.")

    if background and PREFECT_API_URL.value() is None:
        exit_with_error(
            "Background workers require a configured Prefect API URL. Start a"
            " dedicated server with `prefect server start --background`, then set"
            " `PREFECT_API_URL`, or connect to Prefect Cloud."
        )

    # Resolve settings-backed defaults
    if prefetch_seconds is None:
        prefetch_seconds = PREFECT_WORKER_PREFETCH_SECONDS.value()

    is_paused = await _check_work_pool_paused(work_pool_name)
    if is_paused:
        _cli.console.print(
            (
                f"The work pool {work_pool_name!r} is currently paused. This worker"
                " will not execute any flow runs until the work pool is unpaused."
            ),
            style="yellow",
        )

    is_queues_paused = await _check_work_queues_paused(work_pool_name, work_queues)
    if is_queues_paused:
        queue_scope = (
            "All work queues" if not work_queues else "Specified work queue(s)"
        )
        _cli.console.print(
            (
                f"{queue_scope} in the work pool {work_pool_name!r} are currently"
                " paused. This worker will not execute any flow runs until the work"
                " queues are unpaused."
            ),
            style="yellow",
        )

    # Resolve worker type
    if worker_type is None:
        worker_type = await _retrieve_worker_type_from_pool(
            _cli.console, exit_with_error, work_pool_name
        )

    if worker_type == "prefect-agent":
        exit_with_error(
            "'prefect-agent' typed work pools work with Prefect Agents instead of"
            " Workers. Please use the 'prefect agent start' to start a Prefect Agent."
        )

    # Load or install worker class (matches typer's _get_worker_class flow)
    if install_policy == InstallPolicy.ALWAYS:
        package = await _find_package_for_worker_type(_cli.console, worker_type)
        if package:
            await _install_package(_cli.console, package, upgrade=True)

    worker_cls = _load_worker_class(worker_type)

    if worker_cls is None:
        package = await _find_package_for_worker_type(_cli.console, worker_type)
        if package:
            should_install = False
            if install_policy == InstallPolicy.IF_NOT_PRESENT:
                should_install = True
            elif install_policy == InstallPolicy.PROMPT and _cli.is_interactive():
                message = (
                    "Could not find the Prefect integration library for the"
                    f" {worker_type} worker in the current environment."
                    " Install the library now?"
                )
                should_install = confirm(message, default=True)

            if should_install:
                await _install_package(_cli.console, package)
                worker_cls = _load_worker_class(worker_type)

    if worker_cls is None:
        exit_with_error(
            "Unable to start worker. Please ensure you have the necessary dependencies"
            " installed to run your desired worker type."
        )

    if background:
        from prefect.cli._server_utils import _cleanup_pid_file

        command = [
            sys.executable,
            "-m",
            "prefect",
            "worker",
            "start",
            "--pool",
            work_pool_name,
            "--type",
            worker_type,
            "--prefetch-seconds",
            str(prefetch_seconds),
        ]
        if worker_name is not None:
            command.extend(["--name", worker_name])
        for work_queue in work_queues or []:
            command.extend(["--work-queue", work_queue])
        if run_once:
            command.append("--run-once")
        if limit is not None:
            command.extend(["--limit", str(limit)])
        if with_healthcheck:
            command.append("--with-healthcheck")
        command.extend(["--install-policy", InstallPolicy.NEVER.value])
        if base_job_template is not None:
            command.extend(["--base-job-template", str(base_job_template)])
        if not create_pool_if_not_found:
            command.append("--no-create-pool-if-not-found")

        # The CLI's --profile context can override environment settings. Pass
        # the effective values so the child uses the same API and credentials.
        env = os.environ.copy()
        env.update(
            get_settings_context().settings.to_environment_variables(exclude_unset=True)
        )
        env["PREFECT_PROFILE"] = get_settings_context().profile.name
        ready_file = WORKER_PID_FILE.with_name(f"worker-{uuid4().hex}.ready")
        env[WORKER_READY_ENV] = str(ready_file)

        WORKER_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            with _worker_lock():
                if WORKER_PID_FILE.exists():
                    if _get_background_worker() is not None:
                        exit_with_error(
                            "A worker is already running in the background. To stop it,"
                            " run `prefect worker stop`."
                        )
                    _cleanup_pid_file(WORKER_PID_FILE)

                log_fd = os.open(
                    WORKER_LOG_FILE, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600
                )
                with os.fdopen(log_fd, "a") as log_file:
                    process = subprocess.Popen(  # noqa: ASYNC220
                        command,
                        env=env,
                        stdout=log_file,
                        stderr=subprocess.STDOUT,
                        start_new_session=(os.name != "nt"),
                        creationflags=(
                            subprocess.CREATE_NEW_PROCESS_GROUP
                            if os.name == "nt"
                            else 0
                        ),
                    )
                try:
                    deadline = asyncio.get_running_loop().time() + 30
                    while not ready_file.exists():
                        returncode = process.poll()
                        if returncode is not None:
                            if returncode == 0:
                                _cli.console.print(
                                    "Background worker completed successfully."
                                )
                                return
                            exit_with_error(
                                f"Failed to start worker. See {WORKER_LOG_FILE}."
                            )
                        if asyncio.get_running_loop().time() >= deadline:
                            process.terminate()
                            exit_with_error(
                                f"Worker did not become ready. See {WORKER_LOG_FILE}."
                            )
                        await asyncio.sleep(0.1)
                    try:
                        _write_background_worker(
                            process.pid, psutil.Process(process.pid).create_time()
                        )
                    except psutil.NoSuchProcess:
                        if process.poll() == 0:
                            _cli.console.print(
                                "Background worker completed successfully."
                            )
                            return
                        exit_with_error(
                            f"Worker exited during startup. See {WORKER_LOG_FILE}."
                        )
                finally:
                    ready_file.unlink(missing_ok=True)
        except Timeout:
            exit_with_error("Another background worker command is in progress.")
        _cli.console.print(
            f"Worker is running in the background with process ID {process.pid}. "
            f"Logs: {WORKER_LOG_FILE}. Run `prefect worker stop` to stop it."
        )
        return

    worker_process_id = os.getpid()
    setup_signal_handlers_worker(
        worker_process_id, f"the {worker_type} worker", _cli.console.print
    )
    if os.name == "nt":
        signal.signal(signal.SIGBREAK, signal.default_int_handler)

    template_contents = None
    if base_job_template is not None:
        template_contents = json.loads(base_job_template.read_text())

    worker = worker_cls(
        name=worker_name,
        work_pool_name=work_pool_name,
        work_queues=work_queues,
        limit=limit,
        prefetch_seconds=prefetch_seconds,
        heartbeat_interval_seconds=int(PREFECT_WORKER_HEARTBEAT_SECONDS.value()),
        base_job_template=template_contents,
        create_pool_if_not_found=create_pool_if_not_found,
    )
    ready_file = os.environ.get(WORKER_READY_ENV)

    def print_worker_message(message: str) -> None:
        _cli.console.print(message)
        if ready_file and message == f"Worker {worker.name!r} started!":
            Path(ready_file).touch(mode=0o600)

    try:
        await worker.start(
            run_once=run_once,
            with_healthcheck=with_healthcheck,
            printer=print_worker_message,
        )
    except asyncio.CancelledError:
        _cli.console.print(f"Worker {worker.name!r} stopped!", style="yellow")


@worker_app.command()
async def stop() -> None:
    """Stop the worker started in the background."""
    from prefect.cli._server_utils import _cleanup_pid_file

    try:
        with _worker_lock():
            if not WORKER_PID_FILE.exists():
                _cli.console.print("No worker is running in the background.")
                return

            worker = _get_background_worker()
            if worker is None:
                _cleanup_pid_file(WORKER_PID_FILE)
                _cli.console.print("No worker is running in the background.")
                return

            process, created, stopping = worker
            if not stopping:
                try:
                    process.send_signal(
                        signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGTERM
                    )
                except psutil.NoSuchProcess:
                    _cleanup_pid_file(WORKER_PID_FILE)
                    _cli.console.print("Worker stopped.")
                    return
                _write_background_worker(process.pid, created, stopping=True)
    except Timeout:
        exit_with_error("Another background worker command is in progress.")

    for _ in range(5):
        if not _worker_is_running(process):
            break
        await asyncio.sleep(1)

    if _worker_is_running(process):
        _cli.console.print(
            "Worker is still shutting down. Run `prefect worker stop` again to check."
        )
        return

    try:
        with _worker_lock():
            if _get_background_worker() is None:
                _cleanup_pid_file(WORKER_PID_FILE)
    except Timeout:
        pass
    _cli.console.print("Worker stopped.")
