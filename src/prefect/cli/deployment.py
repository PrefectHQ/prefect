import sys
from pathlib import Path

import typer
from rich.padding import Padding
from rich.traceback import Traceback
from prefect import cli

from prefect.cli.base import app, console, exit_with_error
from prefect.client import OrionClient
from prefect.deployments import (
    create_deployment_from_spec,
    deployment_specs_from_script,
    deployment_specs_from_yaml,
    load_flow_from_text,
    load_flow_from_deployment,
)
from prefect.exceptions import FlowScriptError
from prefect.utilities.asyncio import sync_compatible

deployment_app = typer.Typer(name="deployment")
app.add_typer(deployment_app)


@deployment_app.command()
@sync_compatible
async def inspect(name: str):
    """
    View details about a deployment
    """
    ...


@deployment_app.command(name="list")
@sync_compatible
async def list_(flow_name: str = None):
    """
    View all deployments or deployments for a specific flow
    """
    async with OrionClient() as client:
        deployments = await client.read_deployments()

    for deployment in sorted(deployments, key=lambda d: d.created, reverse=True):
        console.print(deployment.name)


@deployment_app.command()
@sync_compatible
async def execute(name: str):
    """
    Create and execute a local flow run for the given deployment
    """

    if "/" not in name:
        raise ValueError(
            "Invalid deployment name. Expected '<flow-name>/<deployment-name>'"
        )

    async with OrionClient() as client:
        deployment = await client.read_deployment_by_name(name)
        flow = await load_flow_from_deployment(deployment, client)

    # Call the flow
    # TODO: Pull parameters from the deployment
    flow()


@deployment_app.command()
@sync_compatible
async def create_run(name: str):
    """
    Create a flow run for the given deployment for execution by an agent
    """
    async with OrionClient() as client:
        deployment = await client.read_deployment_by_name(name)
        flow_run_id = await client.create_flow_run_from_deployment(deployment)
    console.print(f"Created flow run '{flow_run_id}'")


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
