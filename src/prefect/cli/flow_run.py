import sys
from pathlib import Path
from typing import List

import typer
from rich.table import Table

from prefect.cli.base import app, console, exit_with_error
from prefect.client import OrionClient
from prefect.utilities.asyncio import sync_compatible
from prefect.orion.schemas.filters import FlowFilter

flow_run_app = typer.Typer(name="flow-run")
app.add_typer(flow_run_app)


@flow_run_app.command(name="list")
@sync_compatible
async def list_(flow_name: List[str] = None):
    """
    View all flow runs or flow runs for specific flows
    """
    flow_filter = FlowFilter(names=flow_name) if flow_name else None
    async with OrionClient() as client:
        flow_runs = await client.read_flow_runs(flows=flow_filter)
        flows_by_id = {
            flow.id: flow
            for flow in await client.read_flows(
                flows=FlowFilter(ids=[run.flow_id for run in flow_runs])
            )
        }

    table = Table("flow name", "id", "state", "updated")
    for flow_run in sorted(flow_runs, key=lambda d: d.created, reverse=True):
        flow = flows_by_id[flow_run.flow_id]
        table.add_row(
            flow.name,
            str(flow_run.id),
            flow_run.state.type.value,
            str(flow_run.state.updated),
        )

    console.print(table)
