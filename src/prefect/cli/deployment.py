"""
Command line interface for working with deployments.
"""
import sys
from pathlib import Path
from typing import List

import fastapi
import httpx
import pendulum
import typer
from rich.padding import Padding
from rich.pretty import Pretty
from rich.traceback import Traceback

from prefect.cli.base import app, console, exit_with_error
from prefect.client import OrionClient
from prefect.deployments import (
    create_deployment_from_spec,
    deployment_specs_from_script,
    deployment_specs_from_yaml,
    load_flow_from_deployment,
)
from prefect.exceptions import FlowScriptError
from prefect.orion.schemas.filters import FlowFilter
from prefect.utilities.asyncio import sync_compatible

deployment_app = typer.Typer(name="deployment")
app.add_typer(deployment_app)


def assert_deployment_name_format(name: str) -> None:
    if "/" not in name:
        exit_with_error(
            "Invalid deployment name. Expected '<flow-name>/<deployment-name>'"
        )


@deployment_app.command()
@sync_compatible
async def inspect(name: str):
    """
    View details about a deployment

    \b
    Example:
        \b
        $ prefect deployment inspect "hello-world/inline-deployment"
        Deployment(
            id='dfd3e220-a130-4149-9af6-8d487e02fea6',
            created='39 minutes ago',
            updated='39 minutes ago',
            name='inline-deployment',
            flow_id='fe50cfa6-fd54-42e3-8930-6d9192678f89',
            flow_data=DataDocument(encoding='file'),
            parameters={'name': 'Marvin'},
            tags=['foo', 'bar']
        )
    """
    assert_deployment_name_format(name)

    async with OrionClient() as client:
        try:
            deployment = await client.read_deployment_by_name(name)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == fastapi.status.HTTP_404_NOT_FOUND:
                exit_with_error(f"Deployment {name!r} not found!")
            else:
                raise

    console.print(Pretty(deployment))


@deployment_app.command()
@sync_compatible
async def ls(flow_name: List[str] = None, by_created: bool = False):
    """
    View all deployments or deployments for specific flows
    """
    async with OrionClient() as client:
        deployments = await client.read_deployments(
            flow_filter=FlowFilter(name={"any_": flow_name}) if flow_name else None
        )
        flows = {
            flow.id: flow
            for flow in await client.read_flows(
                flow_filter=FlowFilter(id={"any_": [d.flow_id for d in deployments]})
            )
        }

    sort_by_name_keys = lambda d: (flows[d.flow_id].name, d.name)
    sort_by_created_key = lambda d: pendulum.now("utc") - d.created

    for deployment in sorted(
        deployments, key=sort_by_created_key if by_created else sort_by_name_keys
    ):
        console.print(
            f"[blue]{flows[deployment.flow_id].name}/[bold]{deployment.name}[/][/]"
        )


@deployment_app.command()
@sync_compatible
async def execute(name: str):
    """
    Create and execute a local flow run for the given deployment
    """
    assert_deployment_name_format(name)

    async with OrionClient() as client:
        deployment = await client.read_deployment_by_name(name)
        flow = await load_flow_from_deployment(deployment, client=client)
        parameters = deployment.parameters or {}

    flow(**parameters)


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

    Deployments can be specified in Python or YAML

        \b
        ```python
        from prefect.deployments import DeploymentSpec
        \b
        DeploymentSpec(
            name="my-first-deploy", flow_location="./my_flow.py"
        )
        ```

        \b
        ```yaml
        name: "my-first-deploy"
        flow_location: "./my_flow.py"
        ```

    Multiple deployments can be declared in each file

        \b
        ```python
        from prefect.deployments import DeploymentSpec
        \b
        DeploymentSpec(
            name="my-first-deploy", flow_location="./my_flow.py"
        )
        \b
        DeploymentSpec(
            name="my-second-deploy", flow_location="./my_other_flow.py"
        )
        ```

        \b
        ```yaml
        - name: "my-first-deploy"
          flow_location: "./my_flow.py"
        - name: "my-second-deploy"
          flow_location: "./my_other_flowflow.py"
        ```
    """
    if path.name.endswith(".py"):
        from_msg = "python script"
        loader = deployment_specs_from_script

    elif path.name.endswith(".yaml") or path.name.endswith(".yml"):
        from_msg = "yaml file"
        loader = deployment_specs_from_yaml

    else:
        exit_with_error("Unknown file type. Expected a '.py', '.yml', or '.yaml' file.")

    console.print(f"Loading deployments from {from_msg} at [green]{str(path)!r}[/]...")
    try:
        specs = loader(path)
    except Exception as exc:
        console.print_exception()
        exit_with_error(
            f"Encountered exception while loading specifications from {str(path)!r}"
        )

    if not specs:
        exit_with_error(f"No deployment specifications found!", style="yellow")

    for spec in specs:
        traceback = None
        try:
            await create_deployment_from_spec(spec)

        except FlowScriptError as exc:
            traceback = exc.rich_user_traceback()
        except Exception as exc:
            traceback = Traceback.from_exception(*sys.exc_info())

        stylized_name = f"deployment [bold blue]{spec.name!r}[/]"
        if spec.flow_name:
            stylized_name += f" for flow [blue]{spec.flow_name!r}[/]"
        else:
            stylized_name += f" for flow at [blue]{spec.flow_location!r}[/]"

        if traceback:
            console.print(f"Failed to create {stylized_name}", style="red")
            console.print(Padding(traceback, (1, 4, 1, 4)))
        else:
            console.print(f"Created {stylized_name}", style="green")
