"""
Command line interface for working with flow runs
"""
from typing import List
from uuid import UUID

import httpx
import pendulum
import typer
from fastapi import status
from rich.pretty import Pretty
from rich.table import Table

from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.root import app
from prefect.client import get_client
from prefect.exceptions import ObjectNotFound
from prefect.orion.schemas.filters import FlowFilter, FlowRunFilter
from prefect.orion.schemas.sorting import FlowRunSort
from prefect.orion.schemas.states import StateType

flow_run_app = PrefectTyper(
    name="flow-run", help="Commands for interacting with flow runs."
)
app.add_typer(flow_run_app, aliases=["flow-runs"])


@flow_run_app.command()
async def inspect(id: UUID):
    """
    View details about a flow run.
    """
    async with get_client() as client:
        try:
            flow_run = await client.read_flow_run(id)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == status.HTTP_404_NOT_FOUND:
                exit_with_error(f"Flow run {id!r} not found!")
            else:
                raise

    app.console.print(Pretty(flow_run))


@flow_run_app.command()
async def ls(
    flow_name: List[str] = typer.Option(None, help="Name of the flow"),
    limit: int = typer.Option(15, help="Maximum number of flow runs to list"),
    state: List[str] = typer.Option(None, help="Name of the flow run's state"),
    state_type: List[StateType] = typer.Option(
        None, help="Type of the flow run's state"
    ),
):
    """
    View recent flow runs or flow runs for specific flows
    """

    state_filter = {}
    if state:
        state_filter["name"] = {"any_": state}
    if state_type:
        state_filter["type"] = {"any_": state_type}

    async with get_client() as client:
        flow_runs = await client.read_flow_runs(
            flow_filter=FlowFilter(name={"any_": flow_name}) if flow_name else None,
            flow_run_filter=FlowRunFilter(state=state_filter) if state_filter else None,
            limit=limit,
            sort=FlowRunSort.EXPECTED_START_TIME_DESC,
        )
        flows_by_id = {
            flow.id: flow
            for flow in await client.read_flows(
                flow_filter=FlowFilter(id={"any_": [run.flow_id for run in flow_runs]})
            )
        }

    table = Table(title="Flow Runs")
    table.add_column("ID", justify="right", style="cyan", no_wrap=True)
    table.add_column("Flow", style="blue", no_wrap=True)
    table.add_column("Name", style="green", no_wrap=True)
    table.add_column("State", no_wrap=True)
    table.add_column("When", style="bold", no_wrap=True)

    for flow_run in sorted(flow_runs, key=lambda d: d.created, reverse=True):
        flow = flows_by_id[flow_run.flow_id]
        timestamp = (
            flow_run.state.state_details.scheduled_time
            if flow_run.state.is_scheduled()
            else flow_run.state.timestamp
        )
        table.add_row(
            str(flow_run.id),
            str(flow.name),
            str(flow_run.name),
            str(flow_run.state.type.value),
            pendulum.instance(timestamp).diff_for_humans(),
        )

    app.console.print(table)


@flow_run_app.command()
async def delete(id: UUID):
    """
    Delete a flow run by ID.
    """
    async with get_client() as client:
        try:
            await client.delete_flow_run(id)
        except ObjectNotFound as exc:
            exit_with_error(f"Flow run '{id}' not found!")

    exit_with_success(f"Successfully deleted flow run '{id}'.")
