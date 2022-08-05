"""
Command line interface for working with deployments.
"""
import json
from enum import Enum
from inspect import getdoc
from pathlib import Path
from typing import List, Optional

import pendulum
import typer
import yaml
from rich.pretty import Pretty
from rich.table import Table

from prefect import Flow, Manifest
from prefect.blocks.core import Block
from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.root import app
from prefect.client import get_client
from prefect.context import PrefectObjectRegistry, registry_from_script
from prefect.deployments import DeploymentYAML, load_deployments_from_yaml
from prefect.exceptions import (
    ObjectNotFound,
    PrefectHTTPStatusError,
    ScriptError,
    exception_traceback,
)
from prefect.filesystems import LocalFileSystem
from prefect.infrastructure import DockerContainer, KubernetesJob, Process
from prefect.orion.schemas.filters import FlowFilter
from prefect.utilities.callables import parameter_schema
from prefect.utilities.filesystem import set_default_ignore_file
from prefect.utilities.importtools import import_object


def str_presenter(dumper, data):
    """
    configures yaml for dumping multiline strings
    Ref: https://stackoverflow.com/questions/8640959/how-can-i-control-what-scalar-form-pyyaml-uses-for-my-data
    """
    if len(data.splitlines()) > 1:  # check for multiline string
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


yaml.add_representer(str, str_presenter)
yaml.representer.SafeRepresenter.add_representer(str, str_presenter)

deployment_app = PrefectTyper(
    name="deployment", help="Commands for working with deployments."
)
app.add_typer(deployment_app)


def assert_deployment_name_format(name: str) -> None:
    if "/" not in name:
        exit_with_error(
            "Invalid deployment name. Expected '<flow-name>/<deployment-name>'"
        )


async def get_deployment(client, name, deployment_id):
    if name is None and deployment_id is not None:
        try:
            deployment = await client.read_deployment(deployment_id)
        except PrefectHTTPStatusError:
            exit_with_error(f"Deployment {deployment_id!r} not found!")
    elif name is not None and deployment_id is None:
        try:
            deployment = await client.read_deployment_by_name(name)
        except ObjectNotFound:
            exit_with_error(f"Deployment {name!r} not found!")
    elif name is None and deployment_id is None:
        exit_with_error("Must provide a deployed flow's name or id")
    else:
        exit_with_error("Only provide a deployed flow's name or id")

    if not deployment.manifest_path:
        exit_with_error(
            f"This deployment has been deprecated. Please see https://orion-docs.prefect.io/concepts/deployments/ to learn how to create a deployment."
        )

    return deployment


class RichTextIO:
    def __init__(self, console, prefix: str = None) -> None:
        self.console = console
        self.prefix = prefix

    def write(self, content: str):
        if self.prefix:
            content = self.prefix + content
        self.console.print(content)


@deployment_app.command()
async def inspect(name: str):
    """
    View details about a deployment.

    \b
    Example:
        \b
        $ prefect deployment inspect "hello-world/my-deployment"
        {
            'id': '610df9c3-0fb4-4856-b330-67f588d20201',
            'created': '2022-08-01T18:36:25.192102+00:00',
            'updated': '2022-08-01T18:36:25.188166+00:00',
            'name': 'my-deployment',
            'description': None,
            'flow_id': 'b57b0aa2-ef3a-479e-be49-381fb0483b4e',
            'schedule': None,
            'is_schedule_active': True,
            'parameters': {'name': 'Marvin'},
            'tags': ['test'],
            'parameter_openapi_schema': {
                'title': 'Parameters',
                'type': 'object',
                'properties': {
                    'name': {
                        'title': 'name',
                        'type': 'string'
                    }
                },
                'required': ['name']
            },
            'manifest_path': 'my-deployment.json',
            'storage_document_id': '63ef008f-1e5d-4e07-a0d4-4535731adb32',
            'infrastructure_document_id': '6702c598-7094-42c8-9785-338d2ec3a028',
            'infrastructure': {
                'type': 'process',
                'env': {},
                'labels': {},
                'name': None,
                'command': ['python', '-m', 'prefect.engine'],
                'stream_output': True
            }
        }

    """
    assert_deployment_name_format(name)

    async with get_client() as client:
        try:
            deployment = await client.read_deployment_by_name(name)
        except ObjectNotFound:
            exit_with_error(f"Deployment {name!r} not found!")

        deployment_json = deployment.dict(json_compatible=True)

        if deployment.infrastructure_document_id:
            deployment_json["infrastructure"] = Block._from_block_document(
                await client.read_block_document(deployment.infrastructure_document_id)
            ).dict(
                exclude={"_block_document_id", "_block_document_name", "_is_anonymous"}
            )

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
async def run(
    name: Optional[str] = typer.Argument(
        None, help="A deployed flow's name: <FLOW_NAME>/<DEPLOYMENT_NAME>"
    ),
    deployment_id: Optional[str] = typer.Option(
        None, "--id", help="A deployment id to search for if no name is given"
    ),
):
    """
    Create a flow run for the given flow and deployment.

    The flow run will be scheduled for now and an agent must execute it.

    The flow run will not execute until an agent starts.
    """
    async with get_client() as client:
        deployment = await get_deployment(client, name, deployment_id)
        flow_run = await client.create_flow_run_from_deployment(deployment.id)
    app.console.print(f"Created flow run {flow_run.name!r} ({flow_run.id})")


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
async def apply(
    paths: List[str] = typer.Argument(
        ...,
        help="One or more paths to deployment YAML files.",
    ),
):
    """
    Create or update a deployment from a YAML file.
    """
    for path in paths:

        # load the file
        with open(str(path), "r") as f:
            data = yaml.safe_load(f)

        # create deployment object
        try:
            deployment = DeploymentYAML(**data)
            app.console.print(f"Successfully loaded {deployment.name!r}", style="green")
        except Exception as exc:
            exit_with_error(f"'{path!s}' did not conform to deployment spec: {exc!r}")

        async with get_client() as client:
            # prep IDs
            flow_id = await client.create_flow_from_name(deployment.flow_name)

            deployment.infrastructure = deployment.infrastructure.copy()
            infrastructure_document_id = await deployment.infrastructure._save(
                is_anonymous=True,
            )

            # we assume storage was already saved
            storage_document_id = deployment.storage._block_document_id

            deployment_id = await client.create_deployment(
                flow_id=flow_id,
                name=deployment.name,
                version=deployment.version,
                schedule=deployment.schedule,
                parameters=deployment.parameters,
                description=deployment.description,
                tags=deployment.tags,
                manifest_path=deployment.manifest_path,
                storage_document_id=storage_document_id,
                infrastructure_document_id=infrastructure_document_id,
                parameter_openapi_schema=deployment.parameter_openapi_schema.dict(),
            )

        app.console.print(
            f"Deployment '{deployment.flow_name}/{deployment.name}' successfully created with id '{deployment_id}'.",
            style="green",
        )


@deployment_app.command()
async def delete(
    name: Optional[str] = typer.Argument(
        None, help="A deployed flow's name: <FLOW_NAME>/<DEPLOYMENT_NAME>"
    ),
    deployment_id: Optional[str] = typer.Option(
        None, "--id", help="A deployment id to search for if no name is given"
    ),
):
    """
    Delete a deployment.

    \b
    Examples:
        \b
        $ prefect deployment delete test_flow/test_deployment
        $ prefect deployment delete --id dfd3e220-a130-4149-9af6-8d487e02fea6
    """
    async with get_client() as client:
        if name is None and deployment_id is not None:
            try:
                await client.delete_deployment(deployment_id)
                exit_with_success(f"Deleted deployment '{deployment_id}'.")
            except ObjectNotFound:
                exit_with_error(f"Deployment {deployment_id!r} not found!")
        elif name is not None:
            try:
                deployment = await client.read_deployment_by_name(name)
                await client.delete_deployment(deployment.id)
                exit_with_success(f"Deleted deployment '{name}'.")
            except ObjectNotFound:
                exit_with_error(f"Deployment {name!r} not found!")
        else:
            exit_with_error("Must provide a deployment name or id")


class Infra(str, Enum):
    kubernetes = KubernetesJob.get_block_type_slug()
    process = Process.get_block_type_slug()
    docker = DockerContainer.get_block_type_slug()


@deployment_app.command()
async def build(
    path: str = typer.Argument(
        ...,
        help="The path to a flow entrypoint, in the form of `./path/to/file.py:flow_func_name`",
    ),
    manifest_only: bool = typer.Option(
        False, "--manifest-only", help="Generate the manifest file only."
    ),
    name: str = typer.Option(
        None, "--name", "-n", help="The name to give the deployment."
    ),
    version: str = typer.Option(
        None, "--version", "-v", help="A version to give the deployment."
    ),
    tags: List[str] = typer.Option(
        None,
        "-t",
        "--tag",
        help="One or more optional tags to apply to the deployment.",
    ),
    infra_type: Infra = typer.Option(
        "process",
        "--infra",
        "-i",
        help="The infrastructure type to use, prepopulated with defaults.",
    ),
    infra_block: str = typer.Option(
        None,
        "--infra-block",
        "-ib",
        help="The slug of the infrastructure block to use as a template.",
    ),
    storage_block: str = typer.Option(
        None,
        "--storage-block",
        "-sb",
        help="The slug of the storage block. Use the syntax: 'block_type/block_name', where block_type must be one of 'local-file-system', 'remote-file-system', 's3', 'gcs', 'azure'",
    ),
    output: str = typer.Option(
        None,
        "--output",
        "-o",
        help="An optional filename to write the deployment file to.",
    ),
):
    """
    Generate a deployment YAML from /path/to/file.py:flow_function
    """

    # validate inputs
    if not name and not manifest_only:
        exit_with_error(
            "A name for this deployment must be provided with the '--name' flag."
        )

    output_file = None
    if output:
        output_file = Path(output)
        if output_file.suffix and output_file.suffix != ".yaml":
            exit_with_error("Output file must be a '.yaml' file.")
        else:
            output_file = output_file.with_suffix(".yaml")

    # validate flow
    try:
        fpath, obj_name = path.rsplit(":", 1)
    except ValueError as exc:
        if str(exc) == "not enough values to unpack (expected 2, got 1)":
            missing_flow_name_msg = f"Your flow path must include the name of the function that is the entrypoint to your flow.\nTry {path}:<flow_name> for your flow path."
            exit_with_error(missing_flow_name_msg)
        else:
            raise exc
    try:
        flow = import_object(path)
        if isinstance(flow, Flow):
            app.console.print(f"Found flow {flow.name!r}", style="green")
        else:
            exit_with_error(
                f"Found object of unexpected type {type(flow).__name__!r}. Expected 'Flow'."
            )
    except AttributeError:
        exit_with_error(f"{obj_name!r} not found in {fpath!r}.")
    except FileNotFoundError:
        exit_with_error(f"{fpath!r} not found.")
    flow_parameter_schema = parameter_schema(flow)
    manifest = Manifest(
        flow_name=flow.name,
        import_path=path,
        parameter_openapi_schema=flow_parameter_schema,
    )
    manifest_loc = f"{obj_name}-manifest.json"
    with open(manifest_loc, "w") as f:
        json.dump(manifest.dict(), f, indent=4)

    app.console.print(
        f"Manifest created at '{Path(manifest_loc).absolute()!s}'.",
        style="green",
    )
    if manifest_only:
        raise typer.Exit(0)

    ## process storage and move files around
    if storage_block:
        template = await Block.load(storage_block)
        storage = template.copy(
            exclude={"_block_document_id", "_block_document_name", "_is_anonymous"}
        )

        # process .prefectignore file
        if set_default_ignore_file(path="."):
            app.console.print(
                f"Default '.prefectignore' file written to {(Path('.') / '.prefectignore').absolute()}",
                style="green",
            )

        # upload current directory to storage location
        file_count = await storage.put_directory(ignore_file=".prefectignore")
        app.console.print(
            f"Successfully uploaded {file_count} files to {storage.basepath}",
            style="green",
        )
    else:
        # default storage, no need to move anything around
        storage = LocalFileSystem(basepath=Path(".").absolute())

    # persists storage now in case it contains secret values
    await storage._save(is_anonymous=True)

    if infra_block:
        template = await Block.load(infra_block)
        infrastructure = template.copy(
            exclude={"_block_document_id", "_block_document_name", "_is_anonymous"}
        )
    else:
        if infra_type == Infra.kubernetes:
            infrastructure = KubernetesJob()
        elif infra_type == Infra.docker:
            infrastructure = DockerContainer()
        else:
            infrastructure = Process()

    description = getdoc(flow)
    schedule = None
    async with get_client() as client:
        try:
            deployment = await client.read_deployment_by_name(f"{flow.name}/{name}")
            description = deployment.description
            schedule = deployment.schedule
        except ObjectNotFound:
            pass

    deployment = DeploymentYAML(
        name=name,
        description=description,
        tags=tags or [],
        version=version or flow.version,
        flow_name=flow.name,
        schedule=schedule,
        parameter_openapi_schema=manifest.parameter_openapi_schema,
        manifest_path=manifest_loc,
        storage=storage,
        infrastructure=infrastructure,
    )

    deployment_loc = output_file or f"{obj_name}-deployment.yaml"
    with open(deployment_loc, "w") as f:
        f.write(deployment.header)
        yaml.dump(deployment.editable_fields_dict(), f, sort_keys=False)
        f.write("###\n### DO NOT EDIT BELOW THIS LINE\n###\n")
        yaml.dump(deployment.immutable_fields_dict(), f, sort_keys=False)

    exit_with_success(
        f"Deployment YAML created at '{Path(deployment_loc).absolute()!s}'."
    )
