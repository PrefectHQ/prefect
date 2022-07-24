"""
Command line interface for working with flows.
"""
import json
from pathlib import Path

from rich.table import Table

from prefect import Manifest
from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_success
from prefect.cli.root import app
from prefect.client import get_client
from prefect.orion.schemas.sorting import FlowSort
from prefect.utilities.callables import parameter_schema
from prefect.utilities.importtools import load_script_as_module

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
    Generate a basic flow manifest from a path.

    Example usage:

        prefect flow generate-manifest ./path/to/flow/file.py:flow_object_name

    Note that the flow object name may be different than the name of the flow.
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

    exit_with_success(
        f"Manifest created at '{Path('prefect-manifest.json').absolute()!s}'."
    )
