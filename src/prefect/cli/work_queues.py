"""
Command line interface for working with work queues.
"""
import anyio
import typer
from rich.pretty import Pretty
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
async def read(id: str):
    """
    Read a work queue by ID.
    """
    async with get_client() as client:
        result = await client.read_work_queue(id=id)

    console.print(Pretty(result))


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
