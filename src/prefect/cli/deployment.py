from collections import Counter
from pathlib import Path

import typer
from rich.json import JSON
from rich.padding import Padding
from rich.traceback import Traceback
from rich.console import Group
from rich.text import Text

from prefect.cli.base import app, console, exit_with_error
from prefect.deployments import (
    create_deployment_from_spec,
    deployment_specs_from_script,
    deployment_specs_from_yaml,
)
from prefect.exceptions import FlowScriptError
from prefect.utilities.asyncio import sync_compatible

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
        failed = False
        try:

            stylized_name = f"[bold blue]{spec.name!r}[/]"
            flow_name_msg = f" for flow {spec.flow_name!r}" if spec.flow_name else ""

            console.print(f"Found deployment {stylized_name}{flow_name_msg}:")
            console.print(
                Padding(
                    Group(
                        Text("Deployment specification:"),
                        JSON(spec.json(exclude={"flow", "name", "flow_name"})),
                    ),
                    (0, 4, 0, 4),
                )
            )

            await create_deployment_from_spec(spec)
        except FlowScriptError as exc:
            console.print(
                Padding(
                    Group(
                        Text(
                            "Encountered exception while loading flow for deployment:\n",
                            style="red",
                        ),
                        exc.rich_user_traceback(),
                    ),
                    (1, 4, 1, 4),
                )
            )
            failed = True
        except Exception as exc:
            console.print(
                Padding(
                    Group(
                        Text(
                            "Encountered exception while registering deployment with server:\n",
                            style="red",
                        ),
                        Traceback.from_exception(),
                    ),
                    (1, 4, 1, 4),
                )
            )
            failed = True

        if failed:
            console.print(f"Failed to create deployment {stylized_name}", style="red")
            stats["errored"] += 1
        else:
            console.print(f"[green]Registered[/] {stylized_name}")
            stats["created"] += 1

        console.print()

    created, errored = stats["created"], stats["errored"]
    parts = []
    if created:
        parts.append(f"[green]Created {created} deployment(s)[/]")
    if errored:
        parts.append(f"[red]Failed to create {errored} deployment(s)[/]")
    summary = ", ".join(parts)

    console.print(f"[bold]{summary}[/]")

    if errored:
        raise typer.Exit(1)
