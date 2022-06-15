"""
Command line interface for working with deployments.
"""
import traceback
from pathlib import Path
from typing import Dict, List
from uuid import UUID

import pendulum
from rich.pretty import Pretty
from rich.table import Table

from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.root import app
from prefect.client import get_client
from prefect.deployments import (
    DeploymentSpec,
    deployment_specs_from_script,
    deployment_specs_from_yaml,
    load_flow_from_deployment,
)
from prefect.exceptions import ObjectNotFound, ScriptError, SpecValidationError
from prefect.orion.schemas.core import FlowRun
from prefect.orion.schemas.filters import FlowFilter

deployment_app = PrefectTyper(
    name="deployment", help="Commands for working with deployments."
)
app.add_typer(deployment_app)


def assert_deployment_name_format(name: str) -> None:
    if "/" not in name:
        exit_with_error(
            "Invalid deployment name. Expected '<flow-name>/<deployment-name>'"
        )


def exception_traceback(exc: Exception) -> str:
    """
    Convert an exception to a printable string with a traceback
    """
    tb = traceback.TracebackException.from_exception(exc)
    return "".join(list(tb.format()))


@deployment_app.command()
async def inspect(name: str):
    """
    View details about a deployment.

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

    async with get_client() as client:
        try:
            deployment = await client.read_deployment_by_name(name)
        except ObjectNotFound:
            exit_with_error(f"Deployment {name!r} not found!")

    deployment_json = deployment.dict(json_compatible=True)
    app.console.print(Pretty(deployment_json))


@deployment_app.command()
async def ls(flow_name: List[str] = None, by_created: bool = False):
    """
    View all deployments or deployments for specific flows.
    """
    async with get_client() as client:
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

    table = Table(
        title="Deployments",
    )
    table.add_column("Name", style="blue", no_wrap=True)
    table.add_column("ID", style="cyan", no_wrap=True)

    for deployment in sorted(
        deployments, key=sort_by_created_key if by_created else sort_by_name_keys
    ):
        table.add_row(
            f"{flows[deployment.flow_id].name}/[bold]{deployment.name}[/]",
            str(deployment.id),
        )

    app.console.print(table)


@deployment_app.command()
async def run(name: str):
    """
    Create a flow run for the given flow and deployment.

    The flow run will be scheduled for now and an agent must execute it.

    The flow run will not execute until an agent starts.
    """
    async with get_client() as client:
        try:
            deployment = await client.read_deployment_by_name(name)
        except ObjectNotFound:
            exit_with_error(f"Deployment {name!r} not found!")
        flow_run = await client.create_flow_run_from_deployment(deployment.id)

    app.console.print(f"Created flow run {flow_run.name!r} ({flow_run.id})")


@deployment_app.command()
async def execute(name: str):
    """
    Create and execute a local flow run for the given deployment.

    This does not require an agent and will bypass all flow runner settings attached to
    the deployment.

    This command will block until the flow run completes.
    """
    assert_deployment_name_format(name)

    async with get_client() as client:
        deployment = await client.read_deployment_by_name(name)
        app.console.print("Loading flow from deployed location...")
        flow = await load_flow_from_deployment(deployment, client=client)
        parameters = deployment.parameters or {}

    app.console.print("Running flow...")
    state = flow(**parameters)

    if state.is_failed():
        exit_with_error("Flow run failed!")
    else:
        exit_with_success("Flow run completed!")


def _load_deployment_specs(path: Path, quietly=False) -> Dict[DeploymentSpec, str]:
    """Load the deployment specification from the path the user gave on the command line, giving
    helpful error messages if they cannot be loaded."""
    if path.suffix == ".py":
        from_msg = "python script"
        loader = deployment_specs_from_script

    elif path.suffix in (".yaml", ".yml"):
        from_msg = "yaml file"
        loader = deployment_specs_from_yaml

    else:
        exit_with_error("Unknown file type. Expected a '.py', '.yml', or '.yaml' file.")

    if not quietly:
        app.console.print(
            f"Loading deployment specifications from {from_msg} "
            f"at [green]{str(path)!r}[/]..."
        )
    try:
        specs = loader(path)
    except ScriptError as exc:
        app.console.print(exc)
        app.console.print(exception_traceback(exc.user_exc))
        exit_with_error(f"Failed to load specifications from {str(path)!r}")

    if not specs:
        exit_with_error("No deployment specifications found!", style="yellow")

    return specs


@deployment_app.command()
async def create(path: Path):
    """
    Create or update a deployment from a file.

    File must contain one or more deployment specifications in either Python or YAML

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
    specs = _load_deployment_specs(path)

    failed = 0
    for spec, src in specs.items():
        try:
            await spec.validate()
        except SpecValidationError as exc:
            app.console.print(
                f"Specification in {str(src['file'])!r}, line {src['line']} failed "
                f"validation! {exc}",
                style="red",
            )
            failed += 1
            continue  # Attempt to create the next deployment

        stylized_name = f"[blue]'{spec.flow_name}/[/][bold blue]{spec.name}'[/]"

        try:
            app.console.print(
                f"Creating deployment [bold blue]{spec.name!r}[/] for flow [blue]{spec.flow_name!r}[/]..."
            )
            source = f"flow script from [green]{str(spec.flow_location)!r}[/]"
            app.console.print(
                f"Deploying {source} using {spec.flow_storage.get_block_type_name()}..."
            )
            await spec.create_deployment(validate=False)
        except Exception as exc:
            app.console.print(exception_traceback(exc))
            app.console.print(
                f"Failed to create deployment {stylized_name}", style="red"
            )
            failed += 1
            continue  # Attempt to create the next deployment
        else:
            app.console.print(f"Created deployment {stylized_name}.")

            # TODO: Check for an API url and link to the UI instead if a hosted API
            #       exists
            app.console.print(
                "View your new deployment with: "
                f"\n\n    prefect deployment inspect {stylized_name}"
            )

    if failed:
        exit_with_error(f"Failed to create {failed} out of {len(specs)} deployments.")
    else:
        exit_with_success(f"Created {len(specs)} deployments!")


@deployment_app.command()
async def delete(deployment_id: UUID):
    """
    Delete a deployment.

    \b
    Example:
        \b
        $ prefect deployment delete dfd3e220-a130-4149-9af6-8d487e02fea6
    """
    async with get_client() as client:
        try:
            await client.delete_deployment(deployment_id)
        except ObjectNotFound:
            exit_with_error(f"Deployment '{deployment_id}' not found!")

    exit_with_success(f"Deleted deployment '{deployment_id}'.")


@deployment_app.command()
async def preview(path: Path):
    """
    Prints a preview of a deployment.

    Accepts the same file types as `prefect deployment create`.  This preview will
    include any customizations you have made to your deployment's FlowRunner.  If your
    file includes multiple deployments, use `--name` to identify one to preview.

    `prefect deployment preview` is intended for previewing the customizations you've
    made to your deployments, and will include mock identifiers.  They will not run
    correctly if applied directly to an execution environment (like a Kubernetes
    cluster).  Use `prefect deployment create` and `prefect deployment run` to
    actually run your deployments.

    \b
    Example:
        \b
        $ prefect deployment preview my-flow.py

    \b
    Output:
        \b
        apiVersion: batch/v1
        kind: Job ...

    """
    specs = list(_load_deployment_specs(path, quietly=True))

    # create an exemplar FlowRun
    flow_run = FlowRun(
        id=UUID(int=0),
        flow_id=UUID(int=0),
        name="cool-name",
    )

    for spec in specs:
        name = repr(spec.name) if spec.name else "<unnamed deployment specification>"
        app.console.print(f"[green]Preview for {name}[/]:\n")
        print(await spec.flow_runner.preview(flow_run))
        print()
