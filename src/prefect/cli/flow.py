"""
Command line interface for working with flows.
"""
import json
from uuid import UUID

from rich.table import Table

from prefect import Manifest
from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.root import app
from prefect.client import get_client
from prefect.exceptions import ObjectNotFound
from prefect.orion.schemas.sorting import FlowSort
from prefect.utilities.importtools import load_script_as_module
from prefect.utilities.callables import parameter_schema

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
async def generate_manifest(path: str):
    """
    Generate a flow manifest from a path.
    """
    base_path, name = path.split(":", 1)

    mod = load_script_as_module(base_path)
    flow_parameter_schema = parameter_schema(getattr(mod, name))
    manifest = Manifest(
        flow_name=name,
        import_path=base_path,
        flow_parameter_schema=flow_parameter_schema,
    )
    with open("prefect-manifest.json", "w") as f:
        json.dump(manifest.dict(), f, indent=4)


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
