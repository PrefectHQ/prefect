"""
Worker command — native cyclopts implementation.

Start and interact with workers.
"""

import asyncio
import json
import os
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

import cyclopts

from prefect.cli._cyclopts._utilities import (
    exit_with_error,
    run_async,
    with_cli_exception_handling,
)

worker_app = cyclopts.App(name="worker", help="Start and interact with workers.")


def _get_console():
    from prefect.cli._cyclopts import console

    return console


def _is_interactive():
    from prefect.cli._cyclopts import _is_interactive

    return _is_interactive()


class InstallPolicy(str, Enum):
    ALWAYS = "always"
    IF_NOT_PRESENT = "if-not-present"
    NEVER = "never"
    PROMPT = "prompt"


@worker_app.command()
@with_cli_exception_handling
@run_async
async def start(
    *,
    worker_name: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--name", alias="-n", help="The name to give to the started worker."
        ),
    ] = None,
    work_pool_name: Annotated[
        str,
        cyclopts.Parameter(
            "--pool", alias="-p", help="The work pool the started worker should poll."
        ),
    ],
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
        int,
        cyclopts.Parameter(
            "--prefetch-seconds",
            help="Seconds to look ahead for scheduled flow runs.",
        ),
    ] = 10,
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
):
    """Start a worker process to poll a work pool for flow runs."""
    from prefect.cli._prompts import confirm
    from prefect.cli.worker import (
        _check_work_pool_paused,
        _check_work_queues_paused,
        _find_package_for_worker_type,
        _install_package,
        _load_worker_class,
        _retrieve_worker_type_from_pool,
    )
    from prefect.settings import PREFECT_WORKER_HEARTBEAT_SECONDS
    from prefect.utilities.processutils import setup_signal_handlers_worker

    console = _get_console()

    is_paused = await _check_work_pool_paused(work_pool_name)
    if is_paused:
        console.print(
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
        console.print(
            (
                f"{queue_scope} in the work pool {work_pool_name!r} are currently"
                " paused. This worker will not execute any flow runs until the work"
                " queues are unpaused."
            ),
            style="yellow",
        )

    # Resolve worker type
    if worker_type is None:
        worker_type = await _retrieve_worker_type_from_pool(work_pool_name)

    if worker_type == "prefect-agent":
        exit_with_error(
            "'prefect-agent' typed work pools work with Prefect Agents instead of"
            " Workers. Please use the 'prefect agent start' to start a Prefect Agent."
        )

    # Load or install worker class
    worker_cls = _load_worker_class(worker_type)

    if worker_cls is None and install_policy == InstallPolicy.ALWAYS:
        package = await _find_package_for_worker_type(worker_type)
        if package:
            await _install_package(package, upgrade=True)
            worker_cls = _load_worker_class(worker_type)

    if worker_cls is None:
        package = await _find_package_for_worker_type(worker_type)
        if package:
            should_install = False
            if install_policy == InstallPolicy.IF_NOT_PRESENT:
                should_install = True
            elif install_policy == InstallPolicy.PROMPT and _is_interactive():
                message = (
                    "Could not find the Prefect integration library for the"
                    f" {worker_type} worker in the current environment."
                    " Install the library now?"
                )
                should_install = confirm(message, default=True)

            if should_install:
                await _install_package(package)
                worker_cls = _load_worker_class(worker_type)

    if worker_cls is None:
        exit_with_error(
            "Unable to start worker. Please ensure you have the necessary dependencies"
            " installed to run your desired worker type."
        )

    worker_process_id = os.getpid()
    setup_signal_handlers_worker(
        worker_process_id, f"the {worker_type} worker", console.print
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
    )
    try:
        await worker.start(
            run_once=run_once,
            with_healthcheck=with_healthcheck,
            printer=console.print,
        )
    except asyncio.CancelledError:
        console.print(f"Worker {worker.name!r} stopped!", style="yellow")
