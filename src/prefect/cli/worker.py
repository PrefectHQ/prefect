import asyncio
import json
import os
from enum import Enum
from typing import List, Optional, Type

import typer

from prefect._internal.installation import ainstall_packages
from prefect._internal.integrations import KNOWN_EXTRAS_FOR_PACKAGES
from prefect.cli._prompts import confirm
from prefect.cli._types import PrefectTyper, SettingsOption
from prefect.cli._utilities import exit_with_error
from prefect.cli.root import app, is_interactive
from prefect.client.collections import get_collections_metadata_client
from prefect.client.orchestration import get_client
from prefect.client.schemas.filters import WorkQueueFilter, WorkQueueFilterName
from prefect.exceptions import ObjectNotFound
from prefect.plugins import load_prefect_collections
from prefect.settings import (
    PREFECT_WORKER_HEARTBEAT_SECONDS,
    PREFECT_WORKER_PREFETCH_SECONDS,
)
from prefect.utilities.dispatch import lookup_type
from prefect.utilities.processutils import (
    setup_signal_handlers_worker,
)
from prefect.workers.base import BaseWorker

worker_app: PrefectTyper = PrefectTyper(
    name="worker", help="Start and interact with workers."
)
app.add_typer(worker_app)


class InstallPolicy(str, Enum):
    ALWAYS = "always"
    IF_NOT_PRESENT = "if-not-present"
    NEVER = "never"
    PROMPT = "prompt"


@worker_app.command()
async def start(
    worker_name: str = typer.Option(
        None,
        "-n",
        "--name",
        help=(
            "The name to give to the started worker. If not provided, a unique name"
            " will be generated."
        ),
    ),
    work_pool_name: str = typer.Option(
        ...,
        "-p",
        "--pool",
        help="The work pool the started worker should poll.",
        prompt=True,
    ),
    work_queues: List[str] = typer.Option(
        None,
        "-q",
        "--work-queue",
        help=(
            "One or more work queue names for the worker to pull from. If not provided,"
            " the worker will pull from all work queues in the work pool."
        ),
    ),
    worker_type: Optional[str] = typer.Option(
        None,
        "-t",
        "--type",
        help=(
            "The type of worker to start. If not provided, the worker type will be"
            " inferred from the work pool."
        ),
    ),
    prefetch_seconds: int = SettingsOption(
        PREFECT_WORKER_PREFETCH_SECONDS,
        help="Number of seconds to look into the future for scheduled flow runs.",
    ),
    run_once: bool = typer.Option(
        False, help="Only run worker polling once. By default, the worker runs forever."
    ),
    limit: int = typer.Option(
        None,
        "-l",
        "--limit",
        help="Maximum number of flow runs to start simultaneously.",
    ),
    with_healthcheck: bool = typer.Option(
        False, help="Start a healthcheck server for the worker."
    ),
    install_policy: InstallPolicy = typer.Option(
        InstallPolicy.PROMPT.value,
        "--install-policy",
        help="Install policy to use workers from Prefect integration packages.",
        case_sensitive=False,
    ),
    base_job_template: typer.FileText = typer.Option(
        None,
        "--base-job-template",
        help=(
            "The path to a JSON file containing the base job template to use. If"
            " unspecified, Prefect will use the default base job template for the given"
            " worker type. If the work pool already exists, this will be ignored."
        ),
    ),
):
    """
    Start a worker process to poll a work pool for flow runs.
    """

    is_paused = await _check_work_pool_paused(work_pool_name)
    if is_paused:
        app.console.print(
            (
                f"The work pool {work_pool_name!r} is currently paused. This worker"
                " will not execute any flow runs until the work pool is unpaused."
            ),
            style="yellow",
        )

    is_queues_paused = await _check_work_queues_paused(
        work_pool_name,
        work_queues,
    )
    if is_queues_paused:
        queue_scope = (
            "All work queues" if not work_queues else "Specified work queue(s)"
        )
        app.console.print(
            (
                f"{queue_scope} in the work pool {work_pool_name!r} are currently"
                " paused. This worker will not execute any flow runs until the work"
                " queues are unpaused."
            ),
            style="yellow",
        )
    worker_cls = await _get_worker_class(worker_type, work_pool_name, install_policy)

    if worker_cls is None:
        exit_with_error(
            "Unable to start worker. Please ensure you have the necessary dependencies"
            " installed to run your desired worker type."
        )

    worker_process_id = os.getpid()
    setup_signal_handlers_worker(
        worker_process_id, f"the {worker_type} worker", app.console.print
    )

    template_contents = None
    if base_job_template is not None:
        template_contents = json.load(fp=base_job_template)

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
            printer=app.console.print,
        )
    except asyncio.CancelledError:
        app.console.print(f"Worker {worker.name!r} stopped!", style="yellow")


async def _check_work_pool_paused(work_pool_name: str) -> bool:
    try:
        async with get_client() as client:
            work_pool = await client.read_work_pool(work_pool_name=work_pool_name)
            return work_pool.is_paused
    except ObjectNotFound:
        return False


async def _check_work_queues_paused(
    work_pool_name: str, work_queues: Optional[List[str]]
) -> bool:
    """
    Check if all work queues in the work pool are paused. If work queues are specified,
    only those work queues are checked.

    Args:
        - work_pool_name (str): the name of the work pool to check
        - work_queues (Optional[List[str]]): the names of the work queues to check

    Returns:
        - bool: True if work queues are paused, False otherwise
    """
    try:
        work_queues_filter = (
            WorkQueueFilter(name=WorkQueueFilterName(any_=work_queues))
            if work_queues
            else None
        )
        async with get_client() as client:
            wqs = await client.read_work_queues(
                work_pool_name=work_pool_name, work_queue_filter=work_queues_filter
            )
            return all(queue.is_paused for queue in wqs) if wqs else False
    except ObjectNotFound:
        return False


async def _retrieve_worker_type_from_pool(work_pool_name: Optional[str] = None) -> str:
    try:
        async with get_client() as client:
            work_pool = await client.read_work_pool(work_pool_name=work_pool_name)

        worker_type = work_pool.type
        app.console.print(
            f"Discovered type {worker_type!r} for work pool {work_pool.name!r}."
        )

        if work_pool.is_push_pool or work_pool.is_managed_pool:
            exit_with_error(
                "Workers are not required for push work pools. "
                "See https://docs.prefect.io/latest/deploy/infrastructure-examples/serverless "
                "for more details."
            )

    except ObjectNotFound:
        app.console.print(
            (
                f"Work pool {work_pool_name!r} does not exist and no worker type was"
                " provided. Starting a process worker..."
            ),
            style="yellow",
        )
        worker_type = "process"
    return worker_type


def _load_worker_class(worker_type: str) -> Optional[Type[BaseWorker]]:
    try:
        load_prefect_collections()
        return lookup_type(BaseWorker, worker_type)
    except KeyError:
        return None


async def _install_package(
    package: str, upgrade: bool = False
) -> Optional[Type[BaseWorker]]:
    app.console.print(f"Installing {package}...")
    install_package = KNOWN_EXTRAS_FOR_PACKAGES.get(package, package)
    await ainstall_packages([install_package], stream_output=True, upgrade=upgrade)


async def _find_package_for_worker_type(worker_type: str) -> Optional[str]:
    async with get_collections_metadata_client() as client:
        worker_metadata = await client.read_worker_metadata()

    worker_types_with_packages = {
        worker_type: package_name
        for package_name, worker_dict in worker_metadata.items()
        for worker_type in worker_dict
        if worker_type != "prefect-agent"
    }
    try:
        return worker_types_with_packages[worker_type]
    except KeyError:
        app.console.print(
            f"Could not find a package for worker type {worker_type!r}.",
            style="yellow",
        )
        return None


async def _get_worker_class(
    worker_type: Optional[str] = None,
    work_pool_name: Optional[str] = None,
    install_policy: InstallPolicy = InstallPolicy.PROMPT,
) -> Optional[Type[BaseWorker]]:
    if worker_type is None and work_pool_name is None:
        raise ValueError("Must provide either worker_type or work_pool_name.")

    if worker_type is None:
        worker_type = await _retrieve_worker_type_from_pool(work_pool_name)

    if worker_type == "prefect-agent":
        exit_with_error(
            "'prefect-agent' typed work pools work with Prefect Agents instead of"
            " Workers. Please use the 'prefect agent start' to start a Prefect Agent."
        )

    if install_policy == InstallPolicy.ALWAYS:
        package = await _find_package_for_worker_type(worker_type)
        if package:
            await _install_package(package, upgrade=True)
            worker_cls = _load_worker_class(worker_type)

    worker_cls = _load_worker_class(worker_type)

    if worker_cls is None:
        package = await _find_package_for_worker_type(worker_type)
        # Check if the package exists
        if package:
            # Prompt to install if the package is not present
            if install_policy == InstallPolicy.IF_NOT_PRESENT:
                should_install = True

            # Confirm with the user for installation in an interactive session
            elif install_policy == InstallPolicy.PROMPT and is_interactive():
                message = (
                    "Could not find the Prefect integration library for the"
                    f" {worker_type} worker in the current environment."
                    " Install the library now?"
                )
                should_install = confirm(message, default=True)

            # If none of the conditions met, don't install the package
            else:
                should_install = False

            # If should_install is True, install the package
            if should_install:
                await _install_package(package)
                worker_cls = _load_worker_class(worker_type)

    return worker_cls
