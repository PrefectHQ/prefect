from functools import partial
from typing import List, Optional, Type

import os
import sys
import anyio
import threading
import typer

from prefect.cli._types import PrefectTyper, SettingsOption
from prefect.cli._utilities import exit_with_error
from prefect.cli.root import app, is_interactive
from prefect.client.orchestration import get_client
from prefect.exceptions import ObjectNotFound
from prefect.settings import (
    PREFECT_WORKER_HEARTBEAT_SECONDS,
    PREFECT_WORKER_PREFETCH_SECONDS,
    PREFECT_WORKER_QUERY_SECONDS,
)
from prefect.utilities.dispatch import lookup_type
from prefect.utilities.processutils import run_process, setup_signal_handlers_worker
from prefect.utilities.services import critical_service_loop
from prefect.workers.base import BaseWorker
from prefect.workers.server import start_healthcheck_server
from prefect.plugins import load_prefect_collections

from prefect.client.collections import get_collections_metadata_client
from prefect.cli._prompts import confirm


worker_app = PrefectTyper(
    name="worker", help="Commands for starting and interacting with workers."
)
app.add_typer(worker_app)


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
    auto_install: bool = typer.Option(
        False,
        "-i",
        "--auto-install",
        help=(
            "Automatically install the necessary worker type if it is not available in"
            " the current environment."
        ),
    ),
):
    """
    Start a worker process to poll a work pool for flow runs.
    """
    worker_cls = await _get_worker_class(worker_type, work_pool_name, auto_install)
    if worker_cls is None:
        exit_with_error(
            "Unable to start worker. Please ensure you have the necessary dependencies"
            " installed to run your desired worker type."
        )

    worker_process_id = os.getpid()
    setup_signal_handlers_worker(
        worker_process_id, f"the {worker_type} worker", app.console.print
    )

    async with worker_cls(
        name=worker_name,
        work_pool_name=work_pool_name,
        work_queues=work_queues,
        limit=limit,
        prefetch_seconds=prefetch_seconds,
    ) as worker:
        app.console.print(f"Worker {worker.name!r} started!", style="green")
        async with anyio.create_task_group() as tg:
            # wait for an initial heartbeat to configure the worker
            await worker.sync_with_backend()
            # schedule the scheduled flow run polling loop
            tg.start_soon(
                partial(
                    critical_service_loop,
                    workload=worker.get_and_submit_flow_runs,
                    interval=PREFECT_WORKER_QUERY_SECONDS.value(),
                    run_once=run_once,
                    printer=app.console.print,
                    jitter_range=0.3,
                )
            )
            # schedule the sync loop
            tg.start_soon(
                partial(
                    critical_service_loop,
                    workload=worker.sync_with_backend,
                    interval=PREFECT_WORKER_HEARTBEAT_SECONDS.value(),
                    run_once=run_once,
                    printer=app.console.print,
                    jitter_range=0.3,
                )
            )
            tg.start_soon(
                partial(
                    critical_service_loop,
                    workload=worker.check_for_cancelled_flow_runs,
                    interval=PREFECT_WORKER_QUERY_SECONDS.value() * 2,
                    run_once=run_once,
                    printer=app.console.print,
                    jitter_range=0.3,
                )
            )

            started_event = await worker._emit_worker_started_event()

            # if --with-healthcheck was passed, start the healthcheck server
            if with_healthcheck:
                # we'll start the ASGI server in a separate thread so that
                # uvicorn does not block the main thread
                server_thread = threading.Thread(
                    name="healthcheck-server-thread",
                    target=partial(
                        start_healthcheck_server,
                        worker=worker,
                        query_interval_seconds=PREFECT_WORKER_QUERY_SECONDS.value(),
                    ),
                    daemon=True,
                )
                server_thread.start()

    await worker._emit_worker_stopped_event(started_event)
    app.console.print(f"Worker {worker.name!r} stopped!")


async def _retrieve_worker_type_from_pool(work_pool_name: Optional[str] = None) -> str:
    try:
        async with get_client() as client:
            work_pool = await client.read_work_pool(work_pool_name=work_pool_name)
        worker_type = work_pool.type
        app.console.print(
            f"Discovered worker type {worker_type!r} for work pool {work_pool.name!r}."
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


async def _install_and_load_package(
    worker_type: str, worker_metadata: dict, auto_install: bool = False
) -> Optional[Type[BaseWorker]]:
    worker_types_with_packages = {
        worker_type: package_name
        for package_name, worker_dict in worker_metadata.items()
        for worker_type in worker_dict
        if worker_type != "prefect-agent"
    }

    if worker_type in worker_types_with_packages and (
        auto_install
        or (
            is_interactive()
            and confirm(
                (
                    f"Could not find a {worker_type} worker in the current"
                    " environment. Install it now?"
                ),
                default=True,
            )
        )
    ):
        package = worker_types_with_packages[worker_type]
        app.console.print(f"Installing {package}...")
        await run_process(
            [sys.executable, "-m", "pip", "install", package], stream_output=True
        )
        return _load_worker_class(worker_type)


async def _get_worker_class(
    worker_type: Optional[str] = None,
    work_pool_name: Optional[str] = None,
    auto_install: bool = False,
) -> Optional[Type[BaseWorker]]:
    if worker_type is None and work_pool_name is None:
        raise ValueError("Must provide either worker_type or work_pool_name.")

    if worker_type is None:
        worker_type = await _retrieve_worker_type_from_pool(work_pool_name)
    worker_cls = _load_worker_class(worker_type)

    if worker_cls is None:
        async with get_collections_metadata_client() as client:
            worker_metadata = await client.read_worker_metadata()
        worker_cls = await _install_and_load_package(
            worker_type, worker_metadata, auto_install
        )

    return worker_cls
