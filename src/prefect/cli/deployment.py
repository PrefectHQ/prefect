"""
Command line interface for working with deployments.
"""
import textwrap
import traceback
from pathlib import Path
from typing import List
from uuid import UUID

import pendulum
from rich.pretty import Pretty
from rich.table import Table

from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.root import app
from prefect.client import OrionClient, get_client
from prefect.context import PrefectObjectRegistry, registry_from_script
from prefect.deployments import (
    DataDocument,
    Deployment,
    FlowScript,
    PackageManifest,
    _source_to_flow,
    load_deployments_from_yaml,
    load_flow_from_deployment,
)
from prefect.exceptions import ObjectNotFound, ScriptError
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
    state = flow._run(**parameters)

    if state.is_failed():
        exit_with_error("Flow run failed!")
    else:
        exit_with_success("Flow run completed!")


def _load_deployments(path: Path, quietly=False) -> PrefectObjectRegistry:
    """
    Load deployments from the path the user gave on the command line, giving helpful
    error messages if they cannot be loaded.
    """
    if path.suffix == ".py":
        from_msg = "python script"
        loader = registry_from_script

    elif path.suffix in (".yaml", ".yml"):
        from_msg = "yaml file"
        loader = load_deployments_from_yaml

    else:
        exit_with_error("Unknown file type. Expected a '.py', '.yml', or '.yaml' file.")

    if not quietly:
        app.console.print(
            f"Loading deployments from {from_msg} at [green]{str(path)!r}[/]..."
        )
    try:
        specs = loader(path)
    except ScriptError as exc:
        app.console.print(exc)
        app.console.print(exception_traceback(exc.user_exc))
        exit_with_error(f"Failed to load deployments from {str(path)!r}")

    if not specs:
        exit_with_error("No deployments found!", style="yellow")

    return specs


@deployment_app.command()
async def create(path: Path):
    """
    Create or update a deployment from a file.

    File must contain one or more deployments in either Python or YAML

        \b
        ```python
        from prefect.deployments import Deployment
        \b
        Deployment(
            name="my-first-deploy", flow=my_flow,
        )
        ```

        \b
        ```yaml
        name: "my-first-deploy"
        flow:
            path: "./my_flow.py"
        ```

    Multiple deployments can be declared in each file

        \b
        ```python
        from prefect.deployments import Deployment
        \b
        Deployment(
            name="my-first-deploy", flow=my_flow,
        )
        \b
        Deployment(
            name="my-second-deploy", flow=my_other_flow,
        )
        ```

        \b
        ```yaml
        - name: "my-first-deploy"
            path: "./my_flows.py"
            name: "my-flow"
        - name: "my-second-deploy"
            path: "./my_flows.py"
            name: "my-other-flow"
        ```
    """
    # Load the deployments into a registry
    registry = _load_deployments(path)

    valid_deployments = registry.get_instances(Deployment)
    invalid_deployments = registry.get_instance_failures(Deployment)

    if invalid_deployments:
        app.console.print(f"[red]Found {len(invalid_deployments)} invalid deployments:")
        # Display all invalid deployments
        for exc, inst, args, kwargs in invalid_deployments:
            # Reconstruct the deployment as much as possible
            deployment = type(inst).construct(*args, **kwargs)

            # Attempt to recover a helpful name
            identifier = ""
            if deployment.name:
                identifier += f" for deployment with name {deployment.name!r}"
            if deployment.flow and hasattr(deployment.flow, "name"):
                identifier += f" for flow {deployment.flow.name!r}"
            identifier = identifier or ""

            app.console.print(
                textwrap.indent(
                    str(exc).replace(" for Deployment", identifier), prefix=" " * 4
                )
            )

            # Add a newline if we're displaying multiple
            if len(invalid_deployments) > 1:
                app.console.print()

        exit_with_error(
            "Invalid deployments must be removed or fixed before creation can continue."
        )

    failed, created = 0, 0

    async with get_client() as client:
        for deployment in valid_deployments:
            try:
                await _create_deployment(deployment, client=client)
            except Exception as exc:
                app.console.print(exception_traceback(exc))
                app.console.print("Failed to create deployment!", style="red")
                failed += 1
            else:
                created += 1

    if failed:
        exit_with_error(
            f"Failed to create {failed} out of {len(valid_deployments)} deployments."
        )
    else:
        s = "s" if created > 1 else ""
        exit_with_success(f"Created {created} deployment{s}!")


def _stylized_flow_name(deployment: Deployment, flow_name: str):
    second_name = deployment.name or flow_name
    return f"[blue]'{flow_name}/[/][bold blue]{second_name}'[/]"


async def _deployment_to_manifest(deployment: Deployment) -> PackageManifest:
    flow_source = deployment.flow

    if isinstance(flow_source, PackageManifest):
        return flow_source

    if isinstance(flow_source, FlowScript):
        # TODO: Add a utility for path display that will do this logic
        relative_path = str(flow_source.path.relative_to(Path(".").resolve()))
        absolute_path = str(flow_source.path)
        display_path = (
            relative_path if len(relative_path) < len(absolute_path) else absolute_path
        )
        app.console.print(
            f"Retrieving flow from script at [green]{display_path!r}[/]..."
        )

    flow = await _source_to_flow(flow_source)

    app.console.print(
        f"Packaging flow for deployment {_stylized_flow_name(deployment, flow.name)}..."
    )
    return await deployment.packager.package(flow)


async def _create_deployment(deployment: Deployment, client: OrionClient):
    manifest = await _deployment_to_manifest(deployment)
    stylized_name = _stylized_flow_name(deployment, manifest.flow_name)

    flow_data = DataDocument.encode("package-manifest", manifest)

    if "image" in manifest.__fields__:
        flow_runner = deployment.flow_runner.copy(update={"image": manifest.image})
    else:
        flow_runner = deployment.flow_runner

    flow_data = DataDocument.encode("package-manifest", manifest)

    app.console.print(f"Registering deployment {stylized_name} with the server...")
    flow_id = await client.create_flow_from_name(manifest.flow_name)
    deployment_id = await client.create_deployment(
        flow_id=flow_id,
        name=deployment.name or manifest.flow_name,
        flow_data=flow_data,
        schedule=deployment.schedule,
        parameters=deployment.parameters,
        tags=deployment.tags,
        flow_runner=flow_runner,
    )
    # TODO: Display a link to the UI if available
    app.console.print(f"Created deployment {stylized_name} ({deployment_id}).")


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
    registry = _load_deployments(path, quietly=True)

    # create an exemplar FlowRun
    flow_run = FlowRun(
        id=UUID(int=0),
        flow_id=UUID(int=0),
        name="cool-name",
    )

    deployments = registry.get_instances(Deployment)

    if not deployments:
        exit_with_error("No deployments found!")

    for deployment in deployments:
        name = repr(deployment.name) if deployment.name else "<unnamed deployment>"
        app.console.print(f"[green]Preview for {name}[/]:\n")
        print(await deployment.flow_runner.preview(flow_run))
        print()
