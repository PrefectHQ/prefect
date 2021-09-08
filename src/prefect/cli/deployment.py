from pathlib import Path

import typer
from rich.live import Live
from rich.status import Status
from rich.panel import Panel
from rich.text import Text
from rich.json import JSON
from rich.padding import Padding

from prefect.cli.base import (
    app,
    console,
    exit_with_error,
    exit_with_success,
)
from prefect.client import OrionClient
from prefect.flows import Flow
from prefect.utilities.asyncio import sync_compatible
from prefect.deployments import DeploymentSpec, deployment_specs_from_script
from prefect.utilities.collections import listrepr
from collections import Counter

deployment_app = typer.Typer(name="deployment")
app.add_typer(deployment_app)


@deployment_app.command()
@sync_compatible
async def inspect(name: str, flow_name: str = None):
    """
    View details about a deployment
    """
    ...


@deployment_app.command()
@sync_compatible
async def list_(flow_name: str = None):
    """
    View all deployments or deployments for a specific flow
    """
    ...


@deployment_app.command()
@sync_compatible
async def create(
    script_path: Path = typer.Argument(
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
    await create_deployment(script_path, name=name, flow_name=flow_name)


@deployment_app.command()
@sync_compatible
async def run(deployment_name: str, watch: bool = True):
    """
    Create a flow run for the given deployment
    """
    ...


async def create_deployment(
    script_path: Path,
    name: str = None,
    flow_name: str = None,
):
    if script_path.name.endswith(".py"):
        console.print(
            f"Loading deployments from python script at {str(script_path)!r}..."
        )
        specs = deployment_specs_from_script(script_path)

    stats = Counter(created=0, errored=0)
    for spec in specs:
        try:
            await create_deployment_from_spec(spec)
        except Exception as exc:
            console.print_exception()
            stats["errored"] += 1
        else:
            stats["created"] += 1


async def create_deployment_from_spec(spec: DeploymentSpec):
    console.print(f"Found deployment [bold blue]{spec.name!r}")
    console.print(Padding(JSON(spec.json(exclude={"flow", "name"})), (0, 4)))

    status = Status("")
    with Live(status, transient=True, console=console):
        async with OrionClient() as client:
            status.update("Connecting to Orion...")
            await client.hello()

            status.update("Registering flow...")
            flow_id = await client.create_flow(spec.flow)

            status.update("Registering deployment...")
            deployment_id = await client.create_deployment(
                flow_id=flow_id, name=spec.name, schedule=None
            )

    console.print("Registered deployment!", style="green")
