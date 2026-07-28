"""
Worker command — native cyclopts implementation.

Start and interact with workers.
"""

import asyncio
import json
import os
import signal
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

import cyclopts

import prefect.cli._app as _cli
from prefect.cli._utilities import (
    exit_with_error,
    exit_with_success,
    with_cli_exception_handling,
)

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
        Optional[str],
        cyclopts.Parameter(
            "--name", alias="-n", help="The name to give to the started worker."
        ),
    ] = None,
    work_pool_name: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--pool", alias="-p", help="The work pool the started worker should poll."
        ),
    ] = None,
    work_queues: Annotated[
        Optional[list[str]],
        cyclopts.Parameter(
            "--work-queue",
            alias="-q",
            help="Work queue names to pull from (repeatable).",
        ),
    ] = None,
    worker_type: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--type",
            alias="-t",
            help="The type of worker to start.",
        ),
    ] = None,
    prefetch_seconds: Annotated[
        Optional[int],
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
        Optional[int],
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
        Optional[Path],
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
        cyclopts.Parameter(
            "--background", alias="-b", help="Run the worker in the background."
        ),
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

    # Only background after validation passes, so a misconfigured worker fails here
    # instead of reporting success (matches `prefect server start`).
    if background:
        from uuid import uuid4

        import prefect.context
        from prefect.cli._server_utils import _cleanup_pid_file, _read_pid_file
        from prefect.cli._worker_utils import (
            WORKER_PID_DIR_NAME,
            _run_worker_in_background,
            _verify_worker_process,
            _worker_marker_path,
        )
        from prefect.settings import PREFECT_HOME
        from prefect.utilities.slugify import slugify

        # Resolve a concrete name up front so multiple background workers can be
        # tracked and stopped individually. A worker otherwise generates its name
        # inside the child process, which the launching CLI cannot see.
        resolved_name = worker_name or f"{worker_type}-{uuid4().hex[:8]}"
        slug = slugify(resolved_name)
        workers_dir = Path(PREFECT_HOME.value()) / WORKER_PID_DIR_NAME
        workers_dir.mkdir(parents=True, exist_ok=True)
        pid_file = workers_dir / f"{slug}.pid"

        # Reserve the name atomically before spawning. `touch(exist_ok=False)`
        # either creates the file or raises, so two concurrent background starts
        # for the same name cannot both pass a check-then-write and orphan one of
        # the spawned workers.
        try:
            pid_file.touch(mode=0o600, exist_ok=False)
        except FileExistsError:
            existing_pid = _read_pid_file(pid_file)
            if existing_pid is not None and _verify_worker_process(
                pid_file, existing_pid
            ):
                exit_with_error(
                    f"A background worker named {slug!r} is already running. To stop"
                    f" it, run `prefect worker stop {slug}`."
                )
            # Reclaim a stale or corrupt PID file left by a previous worker, then
            # retry the atomic reservation once. `_cleanup_pid_file` also removes
            # the workers directory once it is empty, so it must be recreated
            # before the retry.
            _cleanup_pid_file(pid_file)
            _worker_marker_path(pid_file).unlink(missing_ok=True)
            workers_dir.mkdir(parents=True, exist_ok=True)
            try:
                pid_file.touch(mode=0o600, exist_ok=False)
            except FileExistsError:
                exit_with_error(
                    f"A background worker named {slug!r} just started. To stop it,"
                    f" run `prefect worker stop {slug}`."
                )

        # Forward the active profile so the detached worker polls the same API the
        # parent validated against, rather than whatever profile is active on disk
        # by the time the child process starts.
        profile_name = prefect.context.get_settings_context().profile.name

        _run_worker_in_background(
            _cli.console,
            pid_file,
            work_pool_name=work_pool_name,
            worker_name=resolved_name,
            work_queues=work_queues,
            worker_type=worker_type,
            limit=limit,
            prefetch_seconds=prefetch_seconds,
            run_once=run_once,
            with_healthcheck=with_healthcheck,
            install_policy=install_policy.value,
            base_job_template=base_job_template,
            create_pool_if_not_found=create_pool_if_not_found,
            profile_name=profile_name,
        )
        return

    worker_process_id = os.getpid()
    setup_signal_handlers_worker(
        worker_process_id, f"the {worker_type} worker", _cli.console.print
    )

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
    try:
        await worker.start(
            run_once=run_once,
            with_healthcheck=with_healthcheck,
            printer=_cli.console.print,
        )
    except asyncio.CancelledError:
        _cli.console.print(f"Worker {worker.name!r} stopped!", style="yellow")


@worker_app.command()
@with_cli_exception_handling
async def stop(
    name: Annotated[
        Optional[str],
        cyclopts.Parameter(help="The name of the background worker to stop."),
    ] = None,
    *,
    all: Annotated[
        bool,
        cyclopts.Parameter("--all", help="Stop all background workers."),
    ] = False,
):
    """Stop one or more Prefect workers running in the background.

    Examples:
        ```bash
        $ prefect worker stop my-worker
        $ prefect worker stop --all
        ```
    """
    from prefect.cli._server_utils import _cleanup_pid_file, _read_pid_file
    from prefect.cli._worker_utils import (
        WORKER_PID_DIR_NAME,
        _verify_worker_process,
        _worker_marker_path,
    )
    from prefect.settings import PREFECT_HOME
    from prefect.utilities.slugify import slugify

    if all and name is not None:
        exit_with_error("Cannot provide a worker name when stopping all workers.")

    workers_dir = Path(PREFECT_HOME.value()) / WORKER_PID_DIR_NAME
    pid_files = sorted(workers_dir.glob("*.pid")) if workers_dir.is_dir() else []

    def _forget(pid_file: Path) -> None:
        _cleanup_pid_file(pid_file)
        _worker_marker_path(pid_file).unlink(missing_ok=True)

    # Normalize before deciding what to stop: a stale or corrupt entry should not
    # count toward "multiple workers are running" ambiguity, so clean those up
    # first and make every decision below based on live workers only.
    live_files: list[Path] = []
    for pid_file in pid_files:
        slug = pid_file.stem
        pid = _read_pid_file(pid_file)
        if pid is None:
            _forget(pid_file)
            _cli.console.print(
                f"Worker {slug!r} PID file was empty or invalid. Cleaning up stale"
                " PID file."
            )
        elif not _verify_worker_process(pid_file, pid):
            _forget(pid_file)
            _cli.console.print(
                f"Worker {slug!r} is not running. Cleaning up stale PID file."
            )
        else:
            live_files.append(pid_file)

    if not live_files:
        exit_with_success("No worker running in the background.")

    if all:
        targets = live_files
    elif name is not None:
        target = workers_dir / f"{slugify(name)}.pid"
        if target not in live_files:
            known = ", ".join(pid_file.stem for pid_file in live_files)
            exit_with_error(
                f"No background worker named {name!r} is running. Running workers:"
                f" {known}."
            )
        targets = [target]
    elif len(live_files) == 1:
        targets = live_files
    else:
        known = ", ".join(pid_file.stem for pid_file in live_files)
        exit_with_error(
            f"Multiple workers are running in the background: {known}. Provide a"
            " worker name or use `--all`."
        )

    for pid_file in targets:
        slug = pid_file.stem
        pid = _read_pid_file(pid_file)
        if pid is None or not _verify_worker_process(pid_file, pid):
            # The worker exited on its own since normalization above.
            _forget(pid_file)
            _cli.console.print(
                f"Worker {slug!r} is not running. Cleaning up stale PID file."
            )
            continue

        try:
            if os.name == "nt":
                os.kill(pid, signal.CTRL_BREAK_EVENT)
            else:
                os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, OSError):
            pass

        # A worker treats the first termination signal as a graceful shutdown
        # request and may keep running until in-flight runs finish, so wait for
        # it to actually exit before reporting success and dropping its PID
        # file. Otherwise a same-named worker could be started while the old one
        # is still alive, and `stop` would have reported an outcome that hasn't
        # happened yet.
        for _ in range(5):
            if not _verify_worker_process(pid_file, pid):
                break
            await asyncio.sleep(1)

        if _verify_worker_process(pid_file, pid):
            _cli.console.print(
                f"Worker {slug!r} is still shutting down. Run `prefect worker stop"
                f" {slug}` again if it does not stop shortly."
            )
            continue

        _forget(pid_file)
        _cli.console.print(f"Worker {slug!r} stopped!")
