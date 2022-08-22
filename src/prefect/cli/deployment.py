"""
Command line interface for working with deployments.
"""
from datetime import timedelta
from enum import Enum
from pathlib import Path
from typing import List, Optional

import pendulum
import typer
import yaml
from rich.pretty import Pretty
from rich.table import Table

import prefect
from prefect import Flow
from prefect.blocks.core import Block
from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.root import app
from prefect.client import get_client
from prefect.context import PrefectObjectRegistry, registry_from_script
from prefect.deployments import Deployment, load_deployments_from_yaml
from prefect.exceptions import (
    ObjectNotFound,
    PrefectHTTPStatusError,
    ScriptError,
    exception_traceback,
)
from prefect.infrastructure import DockerContainer, KubernetesJob, Process
from prefect.orion.schemas.filters import FlowFilter
from prefect.orion.schemas.schedules import (
    CronSchedule,
    IntervalSchedule,
    RRuleSchedule,
)
from prefect.utilities.callables import parameter_schema
from prefect.utilities.filesystem import set_default_ignore_file


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
app.add_typer(deployment_app, aliases=["deployments"])


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

        try:
            deployment = await Deployment.load_from_yaml(path)
            app.console.print(f"Successfully loaded {deployment.name!r}", style="green")
        except Exception as exc:
            exit_with_error(f"'{path!s}' did not conform to deployment spec: {exc!r}")

        deployment_id = await deployment.apply()
        app.console.print(
            f"Deployment '{deployment.flow_name}/{deployment.name}' successfully created with id '{deployment_id}'.",
            style="green",
        )

        if deployment.work_queue_name is not None:
            app.console.print(
                "\nTo execute flow runs from this deployment, start an agent "
                f"that pulls work from the the {deployment.work_queue_name!r} work queue:"
            )
            app.console.print(
                f"$ prefect agent start -q {deployment.work_queue_name!r}", style="blue"
            )
        else:
            app.console.print(
                "\nThis deployment does not specify a work queue name, which means agents "
                "will not be able to pick up its runs. To add a work queue, "
                "edit the deployment spec and re-run this command, or visit the deployment in the UI.",
                style="red",
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
        help="One or more optional tags to apply to the deployment. Note: tags are used only for organizational purposes. For delegating work to agents, use the --work-queue flag.",
    ),
    work_queue_name: str = typer.Option(
        None,
        "-q",
        "--work-queue",
        help=(
            "The work queue that will handle this deployment's runs. "
            "It will be created if it doesn't already exist. Defaults to `None`. "
            "Note that if a work queue is not set, work will not be scheduled."
        ),
    ),
    infra_type: Infra = typer.Option(
        None,
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
    overrides: List[str] = typer.Option(
        None,
        "--override",
        help="One or more optional infrastructure overrides provided as a dot delimited path, e.g., `env.env_key=env_value`",
    ),
    storage_block: str = typer.Option(
        None,
        "--storage-block",
        "-sb",
        help="The slug of a remote storage block. Use the syntax: 'block_type/block_name', where block_type must be one of 'remote-file-system', 's3', 'gcs', 'azure', 'smb'",
    ),
    cron: str = typer.Option(
        None,
        "--cron",
        help="A cron string that will be used to set a CronSchedule on the deployment.",
    ),
    interval: int = typer.Option(
        None,
        "--interval",
        help="An integer specifying an interval (in seconds) that will be used to set an IntervalSchedule on the deployment.",
    ),
    rrule: str = typer.Option(
        None,
        "--rrule",
        help="An RRule that will be used to set an RRuleSchedule on the deployment.",
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
    if not name:
        exit_with_error(
            "A name for this deployment must be provided with the '--name' flag."
        )

    if len([value for value in (cron, rrule, interval) if value is not None]) > 1:
        exit_with_error("Only one schedule type can be provided.")

    if infra_block and infra_type:
        exit_with_error(
            "Only one of `infra` or `infra_block` can be provided, please choose one."
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
        flow = prefect.utilities.importtools.import_object(path)
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

    infra_overrides = {}
    for override in overrides or []:
        key, value = override.split("=", 1)
        infra_overrides[key] = value

    if infra_block:
        infrastructure = await Block.load(infra_block)
    elif infra_type:
        if infra_type == Infra.kubernetes:
            infrastructure = KubernetesJob()
        elif infra_type == Infra.docker:
            infrastructure = DockerContainer()
        elif infra_type == Infra.process:
            infrastructure = Process()
    else:
        # will reset to a default of Process is no infra is present on the
        # server-side definition of this deployment
        infrastructure = None

    schedule = None
    if cron:
        schedule = CronSchedule(cron=cron)
    elif interval:
        schedule = IntervalSchedule(interval=timedelta(seconds=interval))
    elif rrule:
        schedule = RRuleSchedule(rrule=rrule)

    # set up deployment object
    deployment = Deployment(name=name, flow_name=flow.name)
    await deployment.load()  # load server-side settings, if any

    flow_parameter_schema = parameter_schema(flow)
    entrypoint = (
        f"{Path(fpath).absolute().relative_to(Path('.').absolute())}:{obj_name}"
    )
    updates = dict(
        parameter_openapi_schema=flow_parameter_schema,
        entrypoint=entrypoint,
        description=deployment.description or flow.description,
        version=version or deployment.version or flow.version,
        tags=tags or None,
        infrastructure=infrastructure,
        infra_overrides=infra_overrides or None,
        schedule=schedule,
        work_queue_name=work_queue_name,
    )
    await deployment.update(**updates, ignore_none=True)

    ## process storage, move files around and process path logic
    if set_default_ignore_file(path="."):
        app.console.print(
            f"Default '.prefectignore' file written to {(Path('.') / '.prefectignore').absolute()}",
            style="green",
        )

    file_count = await deployment.upload_to_storage(storage_block)
    if file_count:
        app.console.print(
            f"Successfully uploaded {file_count} files to {deployment.storage.basepath}",
            style="green",
        )
    deployment_loc = output_file or f"{obj_name}-deployment.yaml"
    await deployment.to_yaml(deployment_loc)
    exit_with_success(
        f"Deployment YAML created at '{Path(deployment_loc).absolute()!s}'."
    )
