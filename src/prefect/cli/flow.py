"""
Command line interface for working with flows.
"""
from typing import List
from uuid import UUID

import httpx
import pendulum
from fastapi import status
from rich.pretty import Pretty
from rich.table import Table

from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.root import app
from prefect.client import get_client
from prefect.exceptions import ObjectNotFound
from prefect.orion.schemas.filters import FlowFilter, FlowRunFilter
from prefect.orion.schemas.sorting import FlowSort
from prefect.orion.schemas.states import StateType

flow_app = PrefectTyper(name="flow", help="Commands for interacting with flows.")
app.add_typer(flow_app)


@flow_app.command()
async def ls(
    limit: int = 15,
):
    """
    View flows.
    """
    async with get_client() as client:
        flows = await client.read_flows(
            limit=limit,
            sort=FlowSort.CREATED_DESC,
        )

    table = Table(title="Flows")
    table.add_column("ID", justify="right", style="cyan", no_wrap=True)
    table.add_column("Name", style="green", no_wrap=True)
    table.add_column("Created", no_wrap=True)

    for flow in flows:
        table.add_row(
            str(flow.id),
            str(flow.name),
            str(flow.created),
        )

    app.console.print(table)


@flow_app.command()
async def delete(id: UUID):
    """
    Delete a flow by ID.
    """
    async with get_client() as client:
        try:
            await client.delete_flow(id)
        except ObjectNotFound as exc:
            exit_with_error(f"Flow '{id}' not found!")

    exit_with_success(f"Successfully deleted flow '{id}'.")
