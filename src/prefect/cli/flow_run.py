"""
Command line interface for working with flow runs
"""
from typing import List
from uuid import UUID

import fastapi
import httpx
import pendulum
import typer
from rich.pretty import Pretty
from rich.table import Table

from prefect.cli.base import app, console, exit_with_error
from prefect.client import OrionClient
from prefect.orion.schemas.filters import FlowFilter, FlowRunFilter
from prefect.orion.schemas.sorting import FlowRunSort
from prefect.orion.schemas.states import StateType
from prefect.utilities.asyncio import sync_compatible

flow_run_app = typer.Typer(name="flow-run")
app.add_typer(flow_run_app)


@flow_run_app.command()
@sync_compatible
async def inspect(id: UUID):
    """
    View details about a flow run
    """
    async with OrionClient() as client:
        try:
            flow_run = await client.read_flow_run(id)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == fastapi.status.HTTP_404_NOT_FOUND:
                exit_with_error(f"Flow run {id!r} not found!")
            else:
                raise

    console.print(Pretty(flow_run))


@flow_run_app.command()
@sync_compatible
async def ls(
    flow_name: List[str] = None,
    limit: int = 15,
    state_type: List[StateType] = None,
):
    """
    View recent flow runs or flow runs for specific flows
    """
    async with OrionClient() as client:
        flow_runs = await client.read_flow_runs(
            flow_filter=FlowFilter(name={"any_": flow_name}) if flow_name else None,
            flow_run_filter=(
                FlowRunFilter(state={"type": {"any_": state_type}})
                if state_type
                else None
            ),
            limit=limit,
            sort=FlowRunSort.EXPECTED_START_TIME_DESC,
        )
        flows_by_id = {
            flow.id: flow
            for flow in await client.read_flows(
                flow_filter=FlowFilter(id={"any_": [run.flow_id for run in flow_runs]})
            )
        }

    table = Table("flow", "name", "id", "state", "when")
    for flow_run in sorted(flow_runs, key=lambda d: d.created, reverse=True):
        flow = flows_by_id[flow_run.flow_id]
        timestamp = (
            flow_run.state.state_details.scheduled_time
            if flow_run.state.is_scheduled()
            else flow_run.state.timestamp
        )
        table.add_row(
            f"[blue]{flow.name}[/]",
            f"[bold blue]{flow_run.name}[/]",
            f"[green]{flow_run.id}[/]",
            f"[bold]{flow_run.state.type.value}[/]",
            pendulum.instance(timestamp).diff_for_humans(),
        )

    console.print(table)


@flow_run_app.command()
@sync_compatible
async def create(name: str):
    """
    Create a flow run for the given flow and deployment

    The flow run will be exected by an agent
    """
    async with OrionClient() as client:
        deployment = await client.read_deployment_by_name(name)
        flow_run_id = await client.create_flow_run_from_deployment(deployment)
    console.print(f"Created flow run '{flow_run_id}'")
