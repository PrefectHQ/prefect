"""
Command line interface for working with work queues.
"""
import pendulum
import typer
from rich.pretty import Pretty
from rich.table import Table

from prefect import get_client
from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import (
    exit_with_error,
    exit_with_success,
)
from prefect.cli._prompts import prompt_select_from_table
from prefect.cli.root import app, is_interactive
from prefect.client.collections import get_collections_metadata_client
from prefect.client.schemas.actions import WorkPoolCreate, WorkPoolUpdate
from prefect.exceptions import ObjectAlreadyExists, ObjectNotFound
from prefect.workers.utilities import (
    get_available_work_pool_types,
    get_default_base_job_template_for_infrastructure_type,
)

work_pool_app = PrefectTyper(
    name="work-pool", help="Commands for working with work pools."
)
app.add_typer(work_pool_app, aliases=["work-pool"])


@work_pool_app.command()
async def create(
    name: str = typer.Argument(..., help="The name of the work pool."),
    paused: bool = typer.Option(
        False,
        "--paused",
        help="Whether or not to create the work pool in a paused state.",
    ),
    type: str = typer.Option(
        None, "-t", "--type", help="The type of work pool to create."
    ),
):
    """
    Create a new work pool.

    \b
    Examples:
        $ prefect work-pool create "my-pool" --paused
    """
    async with get_collections_metadata_client() as collections_client:
        if not name.lower().strip("'\" "):
            exit_with_error("Work pool name cannot be empty.")
        if type is None:
            if not is_interactive():
                exit_with_error(
                    "When not using an interactive terminal, you must supply a `--type`"
                    " value."
                )
            worker_metadata = await collections_client.read_worker_metadata()
            worker = prompt_select_from_table(
                app.console,
                "What infrastructure type would you like to use for this work pool?",
                columns=[
                    {"header": "Infrastructure Type", "key": "display_name"},
                    {"header": "Description", "key": "description"},
                ],
                data=[
                    worker
                    for collection in worker_metadata.values()
                    for worker in collection.values()
                ],
                table_kwargs={"show_lines": True},
            )
            type = worker["type"]
        base_job_template = await get_default_base_job_template_for_infrastructure_type(
            type
        )
        if base_job_template is None:
            exit_with_error(
                f"Unknown work pool type {type!r}. "
                "Please choose from"
                f" {', '.join(await get_available_work_pool_types())}."
            )
    async with get_client() as client:
        try:
            wp = WorkPoolCreate(
                name=name,
                type=type,
                base_job_template=base_job_template,
                is_paused=paused,
            )
            work_pool = await client.create_work_pool(work_pool=wp)
            exit_with_success(f"Created work pool {work_pool.name!r}.")
        except ObjectAlreadyExists:
            exit_with_error(
                f"Work pool named {name!r} already exists. Please try creating your"
                " work pool again with a different name."
            )


@work_pool_app.command()
async def ls(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show additional information about work pools.",
    ),
):
    """
    List work pools.

    \b
    Examples:
        $ prefect work-pool ls
    """
    table = Table(
        title="Work Pools", caption="(**) denotes a paused pool", caption_style="red"
    )
    table.add_column("Name", style="green", no_wrap=True)
    table.add_column("Type", style="magenta", no_wrap=True)
    table.add_column("ID", justify="right", style="cyan", no_wrap=True)
    table.add_column("Concurrency Limit", style="blue", no_wrap=True)
    if verbose:
        table.add_column("Base Job Template", style="magenta", no_wrap=True)

    async with get_client() as client:
        pools = await client.read_work_pools()

    def sort_by_created_key(q):
        return pendulum.now("utc") - q.created

    for pool in sorted(pools, key=sort_by_created_key):
        row = [
            f"{pool.name} [red](**)" if pool.is_paused else pool.name,
            str(pool.type),
            str(pool.id),
            (
                f"[red]{pool.concurrency_limit}"
                if pool.concurrency_limit
                else "[blue]None"
            ),
        ]
        if verbose:
            row.append(str(pool.base_job_template))
        table.add_row(*row)

    app.console.print(table)


@work_pool_app.command()
async def inspect(
    name: str = typer.Argument(..., help="The name of the work pool to inspect."),
):
    """
    Inspect a work pool.

    \b
    Examples:
        $ prefect work-pool inspect "my-pool"

    """
    async with get_client() as client:
        try:
            pool = await client.read_work_pool(work_pool_name=name)
        except ObjectNotFound as exc:
            exit_with_error(exc)

        app.console.print(Pretty(pool))


@work_pool_app.command()
async def pause(
    name: str = typer.Argument(..., help="The name of the work pool to pause."),
):
    """
    Pause a work pool.

    \b
    Examples:
        $ prefect work-pool pause "my-pool"

    """
    async with get_client() as client:
        try:
            await client.update_work_pool(
                work_pool_name=name,
                work_pool=WorkPoolUpdate(
                    is_paused=True,
                ),
            )
        except ObjectNotFound as exc:
            exit_with_error(exc)

        exit_with_success(f"Paused work pool {name!r}")


@work_pool_app.command()
async def resume(
    name: str = typer.Argument(..., help="The name of the work pool to resume."),
):
    """
    Resume a work pool.

    \b
    Examples:
        $ prefect work-pool resume "my-pool"

    """
    async with get_client() as client:
        try:
            await client.update_work_pool(
                work_pool_name=name,
                work_pool=WorkPoolUpdate(
                    is_paused=False,
                ),
            )
        except ObjectNotFound as exc:
            exit_with_error(exc)

        exit_with_success(f"Resumed work pool {name!r}")


@work_pool_app.command()
async def delete(
    name: str = typer.Argument(..., help="The name of the work pool to delete."),
):
    """
    Delete a work pool.

    \b
    Examples:
        $ prefect work-pool delete "my-pool"

    """
    async with get_client() as client:
        try:
            await client.delete_work_pool(work_pool_name=name)
        except ObjectNotFound as exc:
            exit_with_error(exc)

        exit_with_success(f"Deleted work pool {name!r}")


@work_pool_app.command()
async def set_concurrency_limit(
    name: str = typer.Argument(..., help="The name of the work pool to update."),
    concurrency_limit: int = typer.Argument(
        ..., help="The new concurrency limit for the work pool."
    ),
):
    """
    Set the concurrency limit for a work pool.

    \b
    Examples:
        $ prefect work-pool set-concurrency-limit "my-pool" 10

    """
    async with get_client() as client:
        try:
            await client.update_work_pool(
                work_pool_name=name,
                work_pool=WorkPoolUpdate(
                    concurrency_limit=concurrency_limit,
                ),
            )
        except ObjectNotFound as exc:
            exit_with_error(exc)

        exit_with_success(
            f"Set concurrency limit for work pool {name!r} to {concurrency_limit}"
        )


@work_pool_app.command()
async def clear_concurrency_limit(
    name: str = typer.Argument(..., help="The name of the work pool to update."),
):
    """
    Clear the concurrency limit for a work pool.

    \b
    Examples:
        $ prefect work-pool clear-concurrency-limit "my-pool"

    """
    async with get_client() as client:
        try:
            await client.update_work_pool(
                work_pool_name=name,
                work_pool=WorkPoolUpdate(
                    concurrency_limit=None,
                ),
            )
        except ObjectNotFound as exc:
            exit_with_error(exc)

        exit_with_success(f"Cleared concurrency limit for work pool {name!r}")


@work_pool_app.command()
async def preview(
    name: str = typer.Argument(None, help="The name or ID of the work pool to preview"),
    hours: int = typer.Option(
        None,
        "-h",
        "--hours",
        help="The number of hours to look ahead; defaults to 1 hour",
    ),
):
    """
    Preview the work pool's scheduled work for all queues.

    \b
    Examples:
        $ prefect work-pool preview "my-pool" --hours 24

    """
    if hours is None:
        hours = 1

    async with get_client() as client:
        try:
            responses = await client.get_scheduled_flow_runs_for_work_pool(
                work_pool_name=name,
            )
        except ObjectNotFound as exc:
            exit_with_error(exc)

    runs = [response.flow_run for response in responses]
    table = Table(caption="(**) denotes a late run", caption_style="red")

    table.add_column(
        "Scheduled Start Time", justify="left", style="yellow", no_wrap=True
    )
    table.add_column("Run ID", justify="left", style="cyan", no_wrap=True)
    table.add_column("Name", style="green", no_wrap=True)
    table.add_column("Deployment ID", style="blue", no_wrap=True)

    pendulum.now("utc").add(hours=hours or 1)

    now = pendulum.now("utc")

    def sort_by_created_key(r):
        return now - r.created

    for run in sorted(runs, key=sort_by_created_key):
        table.add_row(
            (
                f"{run.expected_start_time} [red](**)"
                if run.expected_start_time < now
                else f"{run.expected_start_time}"
            ),
            str(run.id),
            run.name,
            str(run.deployment_id),
        )

    if runs:
        app.console.print(table)
    else:
        app.console.print(
            (
                "No runs found - try increasing how far into the future you preview"
                " with the --hours flag"
            ),
            style="yellow",
        )
