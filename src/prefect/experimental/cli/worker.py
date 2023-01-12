from functools import partial

import anyio
import typer

from prefect.cli._types import PrefectTyper, SettingsOption
from prefect.cli._utilities import exit_with_error
from prefect.cli.root import app
from prefect.experimental.workers.base import BaseWorker
from prefect.settings import (
    PREFECT_WORKER_HEARTBEAT_SECONDS,
    PREFECT_WORKER_PREFETCH_SECONDS,
    PREFECT_WORKER_QUERY_SECONDS,
    PREFECT_WORKER_WORKFLOW_STORAGE_SCAN_SECONDS,
)
from prefect.utilities.dispatch import lookup_type
from prefect.utilities.services import critical_service_loop

worker_app = PrefectTyper(
    name="worker", help="Commands for starting and interacting with workers."
)
app.add_typer(worker_app)


@worker_app.command()
async def start(
    worker_name: str = typer.Option(
        None, "-n", "--name", help="The name to give to the started worker."
    ),
    work_pool_name: str = typer.Option(
        ..., "-p", "--pool", help="The work pool the started worker should join."
    ),
    worker_type: str = typer.Option(
        "process", "-t", "--type", help="The type of worker to start."
    ),
    prefetch_seconds: int = SettingsOption(PREFECT_WORKER_PREFETCH_SECONDS),
    run_once: bool = typer.Option(False, help="Run worker loops only one time."),
    limit: int = typer.Option(
        None,
        "-l",
        "--limit",
        help="Maximum number of flow runs to start simultaneously.",
    ),
):
    try:
        # TODO: Add ability to discover worker type from existing pool
        Worker = lookup_type(BaseWorker, worker_type)
    except KeyError:
        exit_with_error(
            f"Unable to start worker of type {worker_type}. "
            "Please ensure that you have installed this worker type on this machine."
        )
    async with Worker(
        name=worker_name,
        work_pool_name=work_pool_name,
        limit=limit,
        prefetch_seconds=prefetch_seconds,
    ) as worker:
        app.console.print(f"Worker {worker.name!r} started!")
        async with anyio.create_task_group() as tg:
            # wait for an initial heartbeat to configure the worker
            await worker.sync_with_backend()
            # perform initial scan of storage
            await worker.scan_storage_for_deployments()
            # schedule the scheduled flow run polling loop
            tg.start_soon(
                partial(
                    critical_service_loop,
                    workload=worker.get_and_submit_flow_runs,
                    interval=PREFECT_WORKER_QUERY_SECONDS.value(),
                    run_once=run_once,
                    printer=app.console.print,
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
                )
            )
            # schedule the storage scan loop
            tg.start_soon(
                partial(
                    critical_service_loop,
                    workload=worker.scan_storage_for_deployments,
                    interval=PREFECT_WORKER_WORKFLOW_STORAGE_SCAN_SECONDS.value(),
                    run_once=run_once,
                    printer=app.console.print,
                )
            )

    app.console.print(f"Worker {worker.name!r} stopped!")
