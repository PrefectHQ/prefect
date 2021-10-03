from typing import List

import typer
from rich.table import Table

from prefect.cli.base import app, console
from prefect.client import OrionClient
from prefect.utilities.asyncio import sync_compatible
from prefect.orion.schemas.filters import FlowFilter

flow_run_app = typer.Typer(name="flow-run")
app.add_typer(flow_run_app)


@flow_run_app.command()
@sync_compatible
async def ls(flow_name: List[str] = None):
    """
    View all flow runs or flow runs for specific flows
    """
    flow_filter = FlowFilter(name=flow_name) if flow_name else None
    async with OrionClient() as client:
        flow_runs = await client.read_flow_runs(flow_filter=flow_filter)
        flows_by_id = {
            flow.id: flow
            for flow in await client.read_flows(
                flow_filter=FlowFilter(id=[run.flow_id for run in flow_runs])
            )
        }

    table = Table("flow name", "id", "state", "timestamp")
    for flow_run in sorted(flow_runs, key=lambda d: d.created, reverse=True):
        flow = flows_by_id[flow_run.flow_id]
        table.add_row(
            flow.name,
            str(flow_run.id),
            flow_run.state.type.value,
            str(flow_run.state.timestamp),
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
