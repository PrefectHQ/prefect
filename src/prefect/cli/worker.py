from functools import partial
from typing import List, Optional

import anyio
import typer

from prefect.cli._types import PrefectTyper, SettingsOption
from prefect.cli._utilities import exit_with_error
from prefect.cli.root import app
from prefect.client.orchestration import get_client
from prefect.exceptions import ObjectNotFound
from prefect.settings import (
    PREFECT_WORKER_HEARTBEAT_SECONDS,
    PREFECT_WORKER_PREFETCH_SECONDS,
    PREFECT_WORKER_QUERY_SECONDS,
)
from prefect.utilities.dispatch import lookup_type
from prefect.utilities.services import critical_service_loop
from prefect.workers.base import BaseWorker

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
        ..., "-p", "--pool", help="The work pool the started worker should poll."
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
):
    """
    Start a worker process to poll a work pool for flow runs.
    """
    try:
        if worker_type is None:
            async with get_client() as client:
                work_pool = await client.read_work_pool(work_pool_name=work_pool_name)
            worker_type = work_pool.type
            app.console.print(
                f"Discovered worker type {worker_type!r} for work pool"
                f" {work_pool.name!r}."
            )
        worker_cls = lookup_type(BaseWorker, worker_type)
    except KeyError:
        # TODO: Use collection registry info to direct users on how to install the worker type
        exit_with_error(
            f"Unable to start worker of type {worker_type!r}. "
            "Please ensure that you have installed this worker type on this machine."
        )
    except ObjectNotFound:
        exit_with_error(
            f"Work pool {work_pool_name!r} does not exist. To create a new work pool "
            "on worker startup, include a worker type with the --type option."
        )

    async with worker_cls(
        name=worker_name,
        work_pool_name=work_pool_name,
        work_queues=work_queues,
        limit=limit,
        prefetch_seconds=prefetch_seconds,
    ) as worker:
        app.console.print(f"Worker {worker.name!r} started!")
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

    await worker._emit_worker_stopped_event(started_event)
    app.console.print(f"Worker {worker.name!r} stopped!")
