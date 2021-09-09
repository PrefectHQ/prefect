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
from prefect.deployments import (
    DeploymentSpec,
    deployment_specs_from_script,
    deployment_specs_from_yaml,
)
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
async def run(deployment_name: str, watch: bool = True):
    """
    Create a flow run for the given deployment
    """
    ...


@deployment_app.command()
@sync_compatible
async def create(
    path: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        writable=False,
        readable=True,
        resolve_path=False,
    ),
):
    """
    Create or update a deployment from a file containing deployment specifications
    """
    await create_deployments_from_file(path)


async def create_deployments_from_file(
    path: Path,
):
    if path.name.endswith(".py"):
        from_msg = "python script"
        loader = deployment_specs_from_script

    elif path.name.endswith(".yaml") or path.name.endswith(".yml"):
        from_msg = "yaml file"
        loader = deployment_specs_from_yaml

    else:
        exit_with_error("Unknown file type. Expected a '.py', '.yml', or '.yaml' file.")

    console.print(f"Loading deployments from {from_msg} at {str(path)!r}...")
    try:
        specs = loader(path)
    except Exception as exc:
        # TODO: Raise and catch more specific exceptions?
        console.print_exception()
        exit_with_error(
            f"Encountered exception while loading deployments from {str(path)!r}"
        )

    if not specs:
        exit_with_error(f"No deployment specifications found!", style="yellow")

    stats = Counter(created=0, errored=0)
    for spec in specs:
        try:
            await create_deployment_from_spec(spec)
        except Exception:
            console.print_exception()
            stats["errored"] += 1
        else:
            stats["created"] += 1

    created, errored = stats["created"], stats["errored"]
    parts = []
    if created:
        parts.append(f"[green]Created {created} deployments[/]")
    if errored:
        parts.append(f"[red]Failed to create {errored} deployments[/]")
    summary = ", ".join(parts)

    console.print(f"[bold]{summary}[/]")

    if errored:
        raise typer.Exit(1)


async def create_deployment_from_spec(spec: DeploymentSpec):
    stylized_name = f"[bold blue]{spec.name!r}[/]"
    console.print(f"Found deployment {stylized_name}:")
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

    console.print(f"Registered {stylized_name}!")
