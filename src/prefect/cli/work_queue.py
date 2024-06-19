"""
Command line interface for working with work queues.
"""

import warnings
from textwrap import dedent
from typing import Optional, Union
from uuid import UUID

import pendulum
import typer
from rich.pretty import Pretty
from rich.table import Table

from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.root import app, is_interactive
from prefect.client.orchestration import get_client
from prefect.client.schemas.filters import WorkPoolFilter, WorkPoolFilterId
from prefect.client.schemas.objects import DEFAULT_AGENT_WORK_POOL_NAME
from prefect.exceptions import ObjectAlreadyExists, ObjectNotFound

work_app = PrefectTyper(name="work-queue", help="Manage work queues.")
app.add_typer(work_app, aliases=["work-queues"])


async def _get_work_queue_id_from_name_or_id(
    name_or_id: Union[UUID, str], work_pool_name: Optional[str] = None
) -> UUID:
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
                work_queue = await client.read_work_queue_by_name(
                    name=name_or_id,
                    work_pool_name=work_pool_name,
                )
                return work_queue.id
            except ObjectNotFound:
                if not work_pool_name:
                    exit_with_error(f"No work queue named {name_or_id!r} found.")

                exit_with_error(
                    f"No work queue named {name_or_id!r} found in work pool"
                    f" {work_pool_name!r}."
                )


@work_app.command()
async def create(
    name: str = typer.Argument(..., help="The unique name to assign this work queue"),
    limit: int = typer.Option(
        None, "-l", "--limit", help="The concurrency limit to set on the queue."
    ),
    pool: Optional[str] = typer.Option(
        None,
        "-p",
        "--pool",
        help="The name of the work pool to create the work queue in.",
    ),
    priority: Optional[int] = typer.Option(
        None,
        "-q",
        "--priority",
        help="The associated priority for the created work queue",
    ),
):
    """
    Create a work queue.
    """

    async with get_client() as client:
        try:
            result = await client.create_work_queue(
                name=name, work_pool_name=pool, priority=priority
            )
            if limit is not None:
                await client.update_work_queue(
                    id=result.id,
                    concurrency_limit=limit,
                )
        except ObjectAlreadyExists:
            exit_with_error(f"Work queue with name: {name!r} already exists.")
        except ObjectNotFound:
            exit_with_error(f"Work pool with name: {pool!r} not found.")

    if not pool:
        # specify the default work pool name after work queue creation to allow the server
        # to handle a bunch of logic associated with agents without work pools
        pool = DEFAULT_AGENT_WORK_POOL_NAME
    output_msg = dedent(
        f"""
        Created work queue with properties:
            name - {name!r}
            work pool - {pool!r}
            id - {result.id}
            concurrency limit - {limit}
        Start a worker to pick up flow runs from the work queue:
            prefect worker start -q '{result.name} -p {pool}'

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
        help="The name of the work pool that the work queue belongs to.",
    ),
):
    """
    Set a concurrency limit on a work queue.
    """
    queue_id = await _get_work_queue_id_from_name_or_id(
        name_or_id=name,
        work_pool_name=pool,
    )

    async with get_client() as client:
        try:
            await client.update_work_queue(
                id=queue_id,
                concurrency_limit=limit,
            )
        except ObjectNotFound:
            if pool:
                error_message = (
                    f"No work queue named {name!r} found in work pool {pool!r}."
                )
            else:
                error_message = f"No work queue named {name!r} found."
            exit_with_error(error_message)

    if pool:
        success_message = (
            f"Concurrency limit of {limit} set on work queue {name!r} in work pool"
            f" {pool!r}"
        )
    else:
        success_message = f"Concurrency limit of {limit} set on work queue {name!r}"
    exit_with_success(success_message)


@work_app.command()
async def clear_concurrency_limit(
    name: str = typer.Argument(..., help="The name or ID of the work queue to clear"),
    pool: Optional[str] = typer.Option(
        None,
        "-p",
        "--pool",
        help="The name of the work pool that the work queue belongs to.",
    ),
):
    """
    Clear any concurrency limits from a work queue.
    """
    queue_id = await _get_work_queue_id_from_name_or_id(
        name_or_id=name,
        work_pool_name=pool,
    )
    async with get_client() as client:
        try:
            await client.update_work_queue(
                id=queue_id,
                concurrency_limit=None,
            )
        except ObjectNotFound:
            if pool:
                error_message = f"No work queue found: {name!r} in work pool {pool!r}"
            else:
                error_message = f"No work queue found: {name!r}"
            exit_with_error(error_message)

    if pool:
        success_message = (
            f"Concurrency limits removed on work queue {name!r} in work pool {pool!r}"
        )
    else:
        success_message = f"Concurrency limits removed on work queue {name!r}"
    exit_with_success(success_message)


@work_app.command()
async def pause(
    name: str = typer.Argument(..., help="The name or ID of the work queue to pause"),
    pool: Optional[str] = typer.Option(
        None,
        "-p",
        "--pool",
        help="The name of the work pool that the work queue belongs to.",
    ),
):
    """
    Pause a work queue.
    """

    if not pool and not typer.confirm(
        f"You have not specified a work pool. Are you sure you want to pause {name} work queue in `{DEFAULT_AGENT_WORK_POOL_NAME}`?"
    ):
        exit_with_error("Work queue pause aborted!")

    queue_id = await _get_work_queue_id_from_name_or_id(
        name_or_id=name,
        work_pool_name=pool,
    )

    async with get_client() as client:
        try:
            await client.update_work_queue(
                id=queue_id,
                is_paused=True,
            )
        except ObjectNotFound:
            if pool:
                error_message = f"No work queue found: {name!r} in work pool {pool!r}"
            else:
                error_message = f"No work queue found: {name!r}"
            exit_with_error(error_message)

    if pool:
        success_message = f"Work queue {name!r} in work pool {pool!r} paused"
    else:
        success_message = f"Work queue {name!r} paused"
    exit_with_success(success_message)


@work_app.command()
async def resume(
    name: str = typer.Argument(..., help="The name or ID of the work queue to resume"),
    pool: Optional[str] = typer.Option(
        None,
        "-p",
        "--pool",
        help="The name of the work pool that the work queue belongs to.",
    ),
):
    """
    Resume a paused work queue.
    """
    queue_id = await _get_work_queue_id_from_name_or_id(
        name_or_id=name,
        work_pool_name=pool,
    )

    async with get_client() as client:
        try:
            await client.update_work_queue(
                id=queue_id,
                is_paused=False,
            )
        except ObjectNotFound:
            if pool:
                error_message = f"No work queue found: {name!r} in work pool {pool!r}"
            else:
                error_message = f"No work queue found: {name!r}"
            exit_with_error(error_message)

    if pool:
        success_message = f"Work queue {name!r} in work pool {pool!r} resumed"
    else:
        success_message = f"Work queue {name!r} resumed"
    exit_with_success(success_message)


@work_app.command()
async def inspect(
    name: str = typer.Argument(
        None, help="The name or ID of the work queue to inspect"
    ),
    pool: Optional[str] = typer.Option(
        None,
        "-p",
        "--pool",
        help="The name of the work pool that the work queue belongs to.",
    ),
):
    """
    Inspect a work queue by ID.
    """
    queue_id = await _get_work_queue_id_from_name_or_id(
        name_or_id=name,
        work_pool_name=pool,
    )
    async with get_client() as client:
        try:
            result = await client.read_work_queue(id=queue_id)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=DeprecationWarning)

                app.console.print(Pretty(result))
        except ObjectNotFound:
            if pool:
                error_message = f"No work queue found: {name!r} in work pool {pool!r}"
            else:
                error_message = f"No work queue found: {name!r}"
            exit_with_error(error_message)

        try:
            status = await client.read_work_queue_status(id=queue_id)
            app.console.print(Pretty(status))
        except ObjectNotFound:
            pass


@work_app.command()
async def ls(
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Display more information."
    ),
    work_queue_prefix: str = typer.Option(
        None,
        "--match",
        "-m",
        help=(
            "Will match work queues with names that start with the specified prefix"
            " string"
        ),
    ),
    pool: Optional[str] = typer.Option(
        None,
        "-p",
        "--pool",
        help="The name of the work pool containing the work queues to list.",
    ),
):
    """
    View all work queues.
    """
    if not pool:
        table = Table(
            title="Work Queues",
            caption="(**) denotes a paused queue",
            caption_style="red",
        )
        table.add_column("Name", style="green", no_wrap=True)
        table.add_column("Pool", style="magenta", no_wrap=True)
        table.add_column("ID", justify="right", style="cyan", no_wrap=True)
        table.add_column("Concurrency Limit", style="blue", no_wrap=True)
        if verbose:
            table.add_column("Filter (Deprecated)", style="magenta", no_wrap=True)

        async with get_client() as client:
            if work_queue_prefix is not None:
                queues = await client.match_work_queues([work_queue_prefix])
            else:
                queues = await client.read_work_queues()

            pool_ids = [q.work_pool_id for q in queues]
            wp_filter = WorkPoolFilter(id=WorkPoolFilterId(any_=pool_ids))
            pools = await client.read_work_pools(work_pool_filter=wp_filter)
            pool_id_name_map = {p.id: p.name for p in pools}

            def sort_by_created_key(q):
                return pendulum.now("utc") - q.created

            for queue in sorted(queues, key=sort_by_created_key):
                row = [
                    f"{queue.name} [red](**)" if queue.is_paused else queue.name,
                    pool_id_name_map[queue.work_pool_id],
                    str(queue.id),
                    (
                        f"[red]{queue.concurrency_limit}"
                        if queue.concurrency_limit is not None
                        else "[blue]None"
                    ),
                ]
                if verbose and queue.filter is not None:
                    row.append(queue.filter.model_dump_json())
                table.add_row(*row)

    else:
        table = Table(
            title=f"Work Queues in Work Pool {pool!r}",
            caption="(**) denotes a paused queue",
            caption_style="red",
        )
        table.add_column("Name", style="green", no_wrap=True)
        table.add_column("Priority", style="magenta", no_wrap=True)
        table.add_column("Concurrency Limit", style="blue", no_wrap=True)
        if verbose:
            table.add_column("Description", style="cyan", no_wrap=False)

        async with get_client() as client:
            try:
                queues = await client.read_work_queues(work_pool_name=pool)
            except ObjectNotFound:
                exit_with_error(f"No work pool found: {pool!r}")

            def sort_by_created_key(q):
                return pendulum.now("utc") - q.created

            for queue in sorted(queues, key=sort_by_created_key):
                row = [
                    f"{queue.name} [red](**)" if queue.is_paused else queue.name,
                    f"{queue.priority}",
                    (
                        f"[red]{queue.concurrency_limit}"
                        if queue.concurrency_limit is not None
                        else "[blue]None"
                    ),
                ]
                if verbose:
                    row.append(queue.description)
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
    pool: Optional[str] = typer.Option(
        None,
        "-p",
        "--pool",
        help="The name of the work pool that the work queue belongs to.",
    ),
):
    """
    Preview a work queue.
    """
    if pool:
        title = f"Preview of Work Queue {name!r} in Work Pool {pool!r}"
    else:
        title = f"Preview of Work Queue {name!r}"

    table = Table(title=title, caption="(**) denotes a late run", caption_style="red")
    table.add_column(
        "Scheduled Start Time", justify="left", style="yellow", no_wrap=True
    )
    table.add_column("Run ID", justify="left", style="cyan", no_wrap=True)
    table.add_column("Name", style="green", no_wrap=True)
    table.add_column("Deployment ID", style="blue", no_wrap=True)

    window = pendulum.now("utc").add(hours=hours or 1)

    queue_id = await _get_work_queue_id_from_name_or_id(
        name_or_id=name, work_pool_name=pool
    )
    async with get_client() as client:
        if pool:
            try:
                responses = await client.get_scheduled_flow_runs_for_work_pool(
                    work_pool_name=pool,
                    work_queue_names=[name],
                )
                runs = [response.flow_run for response in responses]
            except ObjectNotFound:
                exit_with_error(f"No work queue found: {name!r} in work pool {pool!r}")
        else:
            try:
                runs = await client.get_runs_in_work_queue(
                    queue_id,
                    limit=10,
                    scheduled_before=window,
                )
            except ObjectNotFound:
                exit_with_error(f"No work queue found: {name!r}")
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


@work_app.command()
async def delete(
    name: str = typer.Argument(..., help="The name or ID of the work queue to delete"),
    pool: Optional[str] = typer.Option(
        None,
        "-p",
        "--pool",
        help="The name of the work pool containing the work queue to delete.",
    ),
):
    """
    Delete a work queue by ID.
    """

    queue_id = await _get_work_queue_id_from_name_or_id(
        name_or_id=name,
        work_pool_name=pool,
    )
    async with get_client() as client:
        try:
            if is_interactive() and not typer.confirm(
                (f"Are you sure you want to delete work queue with name {name!r}?"),
                default=False,
            ):
                exit_with_error("Deletion aborted.")
            await client.delete_work_queue_by_id(id=queue_id)
        except ObjectNotFound:
            if pool:
                error_message = f"No work queue found: {name!r} in work pool {pool!r}"
            else:
                error_message = f"No work queue found: {name!r}"
            exit_with_error(error_message)
    if pool:
        success_message = (
            f"Successfully deleted work queue {name!r} in work pool {pool!r}"
        )
    else:
        success_message = f"Successfully deleted work queue {name!r}"
    exit_with_success(success_message)


@work_app.command("read-runs")
async def read_wq_runs(
    name: str = typer.Argument(..., help="The name or ID of the work queue to poll"),
    pool: Optional[str] = typer.Option(
        None,
        "-p",
        "--pool",
        help="The name of the work pool containing the work queue to poll.",
    ),
):
    """
    Get runs in a work queue. Note that this will trigger an artificial poll of
    the work queue.
    """

    queue_id = await _get_work_queue_id_from_name_or_id(
        name_or_id=name,
        work_pool_name=pool,
    )
    async with get_client() as client:
        try:
            runs = await client.get_runs_in_work_queue(id=queue_id)
        except ObjectNotFound:
            if pool:
                error_message = f"No work queue found: {name!r} in work pool {pool!r}"
            else:
                error_message = f"No work queue found: {name!r}"
            exit_with_error(error_message)
    success_message = (
        f"Read {len(runs)} runs for work queue {name!r} in work pool {pool}: {runs}"
    )
    exit_with_success(success_message)
