"""
Command line interface for working with work queues.
"""
from textwrap import dedent
from typing import List, Optional, Union
from uuid import UUID

import pendulum
import typer
from rich.pretty import Pretty
from rich.table import Table

from prefect import get_client
from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.root import app
from prefect.exceptions import ObjectAlreadyExists, ObjectNotFound
from prefect.orion.models.workers_migration import DEFAULT_AGENT_WORK_POOL_NAME
from prefect.orion.schemas.actions import WorkPoolQueueCreate

work_app = PrefectTyper(
    name="work-queue", help="Commands for working with work queues."
)
app.add_typer(work_app, aliases=["work-queues"])


async def _get_work_queue_id_from_name_or_id(name_or_id: Union[UUID, str]):
    """
    For backwards-compatibility, the main argument of the work queue CLI can be
    either a name (preferred) or an ID (legacy behavior).
    """

    if not name_or_id:
        # hint that we prefer names
        exit_with_error("Provide a work queue name.")

    # try parsing as ID
    try:
        return UUID(name_or_id)

    # parse as string
    except (AttributeError, ValueError):
        async with get_client() as client:
            try:
                work_queue = await client.read_work_queue_by_name(name=name_or_id)
                return work_queue.id
            except ObjectNotFound:
                exit_with_error(f"No work queue named {name_or_id!r} found.")


@work_app.command()
async def create(
    name: str = typer.Argument(..., help="The unique name to assign this work queue"),
    limit: int = typer.Option(
        None, "-l", "--limit", help="The concurrency limit to set on the queue."
    ),
    tags: List[str] = typer.Option(
        None,
        "-t",
        "--tag",
        help="DEPRECATED: One or more optional tags. This option will be removed on 2023-02-23.",
    ),
    work_pool_name: Optional[str] = typer.Option(
        None,
        "-wp",
        "--work-pool",
        help="The name of the work pool to create the work queue in.",
    ),
):
    """
    Create a work queue.
    """
    if tags:
        app.console.print(
            "Supplying `tags` for work queues is deprecated. This work "
            "queue will use legacy tag-matching behavior. "
            "This option will be removed on 2023-02-23.",
            style="red",
        )
    # if the queue name contains a "/", split the first element into the pool name
    # else use the work_pool_name argument
    if "/" in name:
        work_pool_name, name = name.split("/", 1)

    if work_pool_name and tags:
        exit_with_error(
            "Work queues created with tags cannot specify work pools or set priorities."
        )

    async with get_client() as client:
        if work_pool_name:
            try:
                work_pool_queue_create = WorkPoolQueueCreate(
                    name=name,
                    concurrency_limit=limit,
                )
                result = await client.create_work_pool_queue(
                    work_pool_name=work_pool_name,
                    work_pool_queue=work_pool_queue_create,
                )
            except Exception as exc:
                exit_with_error(exc)
        else:
            try:
                result = await client.create_work_queue(
                    name=name,
                    tags=tags or None,
                )
                if limit is not None:
                    await client.update_work_queue(
                        id=result.id,
                        concurrency_limit=limit,
                    )
            except ObjectAlreadyExists:
                exit_with_error(f"Work queue with name: {name!r} already exists.")

    if tags:
        tags_message = f"tags - {', '.join(sorted(tags))}\n" or ""
        output_msg = dedent(
            f"""
            Created work queue with properties:
                name - {name!r}
                id - {result.id}
                concurrency limit - {limit}
                {tags_message}
            Start an agent to pick up flow runs from the work queue:
                prefect agent start -q '{result.name}'

            Inspect the work queue:
                prefect work-queue inspect '{result.name}'
            """
        )
    else:
        if not work_pool_name:
            # specify the default work pool name after work queue creation to allow the server
            # to handle a bunch of logic associated with agents without work pools
            work_pool_name = DEFAULT_AGENT_WORK_POOL_NAME
        output_msg = dedent(
            f"""
            Created work queue with properties:
                name - {name!r}
                work pool - {work_pool_name!r}
                id - {result.id}
                concurrency limit - {limit}
            Start an agent to pick up flow runs from the work queue:
                prefect agent start -q '{result.name} -p {work_pool_name}'

            Inspect the work queue:
                prefect work-queue inspect '{result.name}'
            """
        )
    exit_with_success(output_msg)


@work_app.command()
async def set_concurrency_limit(
    name: str = typer.Argument(..., help="The name or ID of the work queue"),
    limit: int = typer.Argument(..., help="The concurrency limit to set on the queue."),
    pool: Optional[str] = typer.Option(
        None,
        "-p",
        "--pool",
        help="The name of the work pool to set the concurrency limit on.",
    ),
):
    """
    Set a concurrency limit on a work queue.
    """
    if not pool:
        queue_id = await _get_work_queue_id_from_name_or_id(name_or_id=name)

    # classic queue with tags
    # work pool queue with default
    # work pool queue
    async with get_client() as client:
        try:
            await client.update_work_queue(
                id=queue_id,
                concurrency_limit=limit,
            )
        except ObjectNotFound:
            exit_with_error(f"No work queue found: {name!r}")

    exit_with_success(f"Concurrency limit of {limit} set on work queue {name!r}")


@work_app.command()
async def clear_concurrency_limit(
    name: str = typer.Argument(..., help="The name or ID of the work queue to clear"),
):
    """
    Clear any concurrency limits from a work queue.
    """
    queue_id = await _get_work_queue_id_from_name_or_id(name_or_id=name)
    async with get_client() as client:
        try:
            await client.update_work_queue(
                id=queue_id,
                concurrency_limit=None,
            )
        except ObjectNotFound:
            exit_with_error(f"No work queue found: {name!r}")

    exit_with_success(f"Concurrency limits removed on work queue {name!r}")


@work_app.command()
async def pause(
    name: str = typer.Argument(..., help="The name or ID of the work queue to pause"),
):
    """
    Pause a work queue.
    """
    queue_id = await _get_work_queue_id_from_name_or_id(name_or_id=name)

    async with get_client() as client:
        try:
            await client.update_work_queue(
                id=queue_id,
                is_paused=True,
            )
        except ObjectNotFound:
            exit_with_error(f"No work queue found: {name!r}")

    exit_with_success(f"Paused work queue {name!r}")


@work_app.command()
async def resume(
    name: str = typer.Argument(..., help="The name or ID of the work queue to resume"),
):
    """
    Resume a paused work queue.
    """
    queue_id = await _get_work_queue_id_from_name_or_id(name_or_id=name)

    async with get_client() as client:
        try:
            await client.update_work_queue(
                id=queue_id,
                is_paused=False,
            )
        except ObjectNotFound:
            exit_with_error(f"No work queue found: {name!r}")

    exit_with_success(f"Resumed work queue {name!r}")


@work_app.command()
async def inspect(
    name: str = typer.Argument(
        None, help="The name or ID of the work queue to inspect"
    ),
):
    """
    Inspect a work queue by ID.
    """
    queue_id = await _get_work_queue_id_from_name_or_id(name_or_id=name)
    async with get_client() as client:
        try:
            result = await client.read_work_queue(id=queue_id)
        except ObjectNotFound:
            exit_with_error(f"No work queue found: {name!r}")

    app.console.print(Pretty(result))


@work_app.command()
async def ls(
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Display more information."
    ),
    work_queue_prefix: str = typer.Option(
        None,
        "--match",
        "-m",
        help="Will match work queues with names that start with the specified prefix string",
    ),
):
    """
    View all work queues.
    """
    table = Table(
        title="Work Queues", caption="(**) denotes a paused queue", caption_style="red"
    )
    table.add_column("Name", style="green", no_wrap=True)
    table.add_column("ID", justify="right", style="cyan", no_wrap=True)
    table.add_column("Concurrency Limit", style="blue", no_wrap=True)
    if verbose:
        table.add_column("Filter (Deprecated)", style="magenta", no_wrap=True)

    async with get_client() as client:
        if work_queue_prefix is not None:
            queues = await client.match_work_queues([work_queue_prefix])
        else:
            queues = await client.read_work_queues()

    sort_by_created_key = lambda q: pendulum.now("utc") - q.created

    for queue in sorted(queues, key=sort_by_created_key):

        row = [
            f"{queue.name} [red](**)" if queue.is_paused else queue.name,
            str(queue.id),
            f"[red]{queue.concurrency_limit}"
            if queue.concurrency_limit
            else "[blue]None",
        ]
        if verbose and queue.filter is not None:
            row.append(queue.filter.json())
        table.add_row(*row)

    app.console.print(table)


@work_app.command()
async def preview(
    name: str = typer.Argument(
        None, help="The name or ID of the work queue to preview"
    ),
    hours: int = typer.Option(
        None,
        "-h",
        "--hours",
        help="The number of hours to look ahead; defaults to 1 hour",
    ),
):
    """
    Preview a work queue.
    """
    queue_id = await _get_work_queue_id_from_name_or_id(name_or_id=name)

    table = Table(caption="(**) denotes a late run", caption_style="red")
    table.add_column(
        "Scheduled Start Time", justify="left", style="yellow", no_wrap=True
    )
    table.add_column("Run ID", justify="left", style="cyan", no_wrap=True)
    table.add_column("Name", style="green", no_wrap=True)
    table.add_column("Deployment ID", style="blue", no_wrap=True)

    window = pendulum.now("utc").add(hours=hours or 1)
    async with get_client() as client:
        try:
            runs = await client.get_runs_in_work_queue(
                queue_id, limit=10, scheduled_before=window
            )
        except ObjectNotFound:
            exit_with_error(f"No work queue found: {name!r}")

    now = pendulum.now("utc")
    sort_by_created_key = lambda r: now - r.created

    for run in sorted(runs, key=sort_by_created_key):
        table.add_row(
            f"{run.expected_start_time} [red](**)"
            if run.expected_start_time < now
            else f"{run.expected_start_time}",
            str(run.id),
            run.name,
            str(run.deployment_id),
        )

    if runs:
        app.console.print(table)
    else:
        app.console.print(
            "No runs found - try increasing how far into the future you preview with the --hours flag",
            style="yellow",
        )


@work_app.command()
async def delete(
    name: str = typer.Argument(..., help="The name or ID of the work queue to delete"),
):
    """
    Delete a work queue by ID.
    """
    queue_id = await _get_work_queue_id_from_name_or_id(name_or_id=name)
    async with get_client() as client:
        try:
            await client.delete_work_queue_by_id(id=queue_id)
        except ObjectNotFound:
            exit_with_error(f"No work queue found: {name!r}")

    exit_with_success(f"Deleted work queue {name!r}")
