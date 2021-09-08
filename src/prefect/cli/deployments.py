from pathlib import Path
from typing import Any, Dict, Iterable

import typer
from rich.live import Live
from rich.status import Status

from prefect.cli.base import (
    app,
    console,
    exit_with_error,
    exit_with_success,
)
from prefect.client import OrionClient
from prefect.flows import Flow
from prefect.utilities.asyncio import sync_compatible

deployments_app = typer.Typer(name="deployments")
app.add_typer(deployments_app)


@deployments_app.command()
@sync_compatible
async def inspect(name: str, flow_name: str = None):
    """
    View details about a deployment
    """
    ...


@deployments_app.command()
@sync_compatible
async def list(flow_name: str = None):
    """
    View all deployments or deployments for a specific flow
    """
    ...


@deployments_app.command()
@sync_compatible
async def create(
    flow_path: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        writable=False,
        readable=True,
        resolve_path=False,
    ),
    name: str = None,
    flow_name: str = None,
):
    """
    Create or update a deployment of a flow
    """
    await _create_deployment(flow_path=flow_path, name=name, flow_name=flow_name)


@deployments_app.command()
@sync_compatible
async def run(deployment_name: str, watch: bool = True):
    """
    Create a flow run for the given deployment
    """
    ...


@app.command()  # Provides `prefect deploy` alias for `prefect deployment create`
@sync_compatible
async def deploy(
    flow_path: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        writable=False,
        readable=True,
        resolve_path=False,
    ),
    name: str = None,
    flow_name: str = None,
):
    """
    Create or update a deployment of a flow
    """
    await _create_deployment(flow_path=flow_path, name=name, flow_name=flow_name)


async def _create_deployment(
    flow_path: Path,
    name: str = None,
    flow_name: str = None,
):
    dsp_path = str(flow_path)  # Get a string for display

    flows = extract_flows_from_file(flow_path)
    if not flows:
        exit_with_error(f"No flows found at path {dsp_path!r}")
    elif flow_name and flow_name not in flows:
        exit_with_error(
            f"Flow {flow_name!r} not found at path {dsp_path!r}. "
            f"Found the following flows: {listrepr(flows.keys())}"
        )
    elif not flow_name and len(flows) > 1:
        exit_with_error(
            f"Found {len(flows)} flows at {dsp_path!r}: {listrepr(flows.keys())}. "
            "Provide a flow name to select a flow to deploy.",
            style="yellow",
        )

    if flow_name:
        flow = flows[flow_name]
    else:
        flow = list(flows.values())[0]

    # Load the default name from the flow object
    name = name or flow.name

    console.print(f"Creating deployment for flow {flow.name!r}...")
    status = Status("")
    with Live(status, transient=True, console=console):
        async with OrionClient() as client:
            status.update("Connecting to Orion...")
            await client.hello()

            status.update("Registering flow...")
            flow_id = await client.create_flow(flow)

            status.update("Registering deployment...")
            deployment_id = await client.create_deployment(
                flow_id=flow_id, name=name, schedule=None
            )

    exit_with_success(f"Created deployment {name!r} for flow {flow.name!r}")


def listrepr(objs: Iterable, sep=" ") -> str:
    return sep.join(repr(obj) for obj in objs)


def extract_flows_from_file(
    file_path: str = None, file_contents: str = None
) -> Dict[str, Flow]:
    """
    Extract all flow objects from a file

    Args:
        - file_path (str, optional): A file path pointing to a .py file containing a flow
        - file_contents (str, optional): The string contents of a .py file containing a flow

    Returns:
        - A mapping of flow name to flow object
    """
    if file_contents is None:
        if file_path is None:
            raise ValueError("Either `file_path` of `file_contents` must be provided")
        with open(file_path, "r") as f:
            file_contents = f.read()

    # If a file_path has been provided, provide __file__ as a global variable
    # so it resolves correctly during extraction
    exec_vals: Dict[str, Any] = {"__file__": file_path} if file_path else {}

    # Load objects from file into the dict
    exec(file_contents, exec_vals)

    # Create a mapping of name -> flow object from the exec values
    flows = {o.name: o for o in exec_vals.values() if isinstance(o, Flow)}

    return flows
