"""
Command line interface for working with work queues.
"""
import anyio
import pendulum
import typer

from rich.pretty import Pretty
from rich.table import Table
from typing import List

from prefect.client import get_client
from prefect.cli.base import (
    PrefectTyper,
    app,
    console,
    exit_with_error,
    exit_with_success,
)

work_app = PrefectTyper(name="work-queue", help="Commands for work queue CRUD.")
app.add_typer(work_app)


@work_app.command()
async def create(
    name: str = typer.Argument(..., help="The unique name to assign this work queue"),
    tags: List[str] = typer.Option(
        None, "-t", "--tag", help="One or more optional tags"
    ),
    deployment_ids: List[str] = typer.Option(
        None, "-d", "--deployment", help="One or more optional deployment IDs"
    ),
    flow_runner_types: List[str] = typer.Option(
        None, "-fr", "--flow-runner", help="One or more optional flow runner types"
    ),
):
    """
    Create a work queue.
    """
    async with get_client() as client:
        result = await client.create_work_queue(
            name=name,
            tags=tags or None,
            deployment_ids=deployment_ids or None,
            flow_runner_types=flow_runner_types or None,
        )

    console.print(Pretty(result))


@work_app.command()
async def pause(
    name: str = typer.Option(
        None, "-n", "--name", help="The name of the work queue to pause."
    ),
    id: str = typer.Option(
        None, "-i", "--id", help="The ID of the work queue to pause."
    ),
):
    """
    Pause a work queue; only one of name or id should be provided.
    """
    if name and id:
        raise ValueError("Only one of name or ID should be provided.")

    async with get_client() as client:
        result = await client.update_work_queue(
            id=id,
            is_paused=True,
        )

    if result:
        exit_with_success(f"Paused work queue {id}")
    else:
        exit_with_error(f"No work queue found with id {id}")


@work_app.command()
async def unpause(
    name: str = typer.Option(
        None, "-n", "--name", help="The name of the work queue to unpause."
    ),
    id: str = typer.Option(
        None, "-i", "--id", help="The ID of the work queue to unpause."
    ),
):
    """
    Unpause a work queue; only one of name or id should be provided.
    """
    if name and id:
        raise ValueError("Only one of name or ID should be provided.")

    async with get_client() as client:
        result = await client.update_work_queue(
            id=id,
            is_paused=False,
        )

    if result:
        exit_with_success(f"Unpaused work queue {id}")
    else:
        exit_with_error(f"No work queue found with id {id}")


@work_app.command()
async def read(id: str):
    """
    Read a work queue by ID.
    """
    async with get_client() as client:
        result = await client.read_work_queue(id=id)

    console.print(Pretty(result))


@work_app.command()
async def ls():
    """
    View all work queues.
    """
    table = Table(title="Work Queues")
    table.add_column("ID", justify="right", style="cyan", no_wrap=True)
    table.add_column("Name", style="yellow", no_wrap=True)
    table.add_column("Paused", style="blue", no_wrap=True)
    table.add_column("Concurrency Limit", style="green", no_wrap=True)
    table.add_column("Filter", style="magenta", no_wrap=True)

    async with get_client() as client:
        queues = await client.read_work_queues()

    sort_by_created_key = lambda q: pendulum.now("utc") - q.created

    for queue in sorted(queues, key=sort_by_created_key):
        table.add_row(
            str(queue.id),
            queue.name,
            "[red]True" if queue.is_paused else "[blue]False",
            queue.concurrency_limit or "None",
            queue.filter.json(),
        )

    console.print(table)


@work_app.command()
async def delete(id: str):
    """
    Delete a work queue by ID.
    """
    async with get_client() as client:
        result = await client.delete_work_queue_by_id(id=id)

    if result:
        exit_with_success(f"Deleted work queue {id}")
    else:
        exit_with_error(f"No work queue found with id {id}")
