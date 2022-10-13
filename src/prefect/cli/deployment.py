"""
Command line interface for working with deployments.
"""
import json
import sys
import textwrap
from datetime import timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

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
from prefect.cli.orion_utils import check_orion_connection, ui_base_url
from prefect.cli.root import app
from prefect.client import get_client
from prefect.client.orion import OrionClient
from prefect.context import PrefectObjectRegistry, registry_from_script
from prefect.deployments import Deployment, load_deployments_from_yaml
from prefect.exceptions import (
    ObjectAlreadyExists,
    ObjectNotFound,
    PrefectHTTPStatusError,
    ScriptError,
    exception_traceback,
)
from prefect.infrastructure.base import Block
from prefect.orion.schemas.filters import FlowFilter
from prefect.orion.schemas.schedules import (
    CronSchedule,
    IntervalSchedule,
    RRuleSchedule,
)
from prefect.utilities.collections import listrepr
from prefect.utilities.dispatch import get_registry_for_type, lookup_type
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


async def get_deployment(client: OrionClient, name, deployment_id):
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


async def create_work_queue_and_set_concurrency_limit(
    work_queue_name, work_queue_concurrency
):
    async with get_client() as client:
        if work_queue_concurrency is not None and work_queue_name:
            try:
                try:
                    res = await client.create_work_queue(name=work_queue_name)
                except ObjectAlreadyExists:
                    res = await client.read_work_queue_by_name(name=work_queue_name)
                    if res.concurrency_limit != work_queue_concurrency:
                        app.console.print(
                            f"Work queue {work_queue_name!r} already exists with a concurrency limit of {res.concurrency_limit}, this limit is being updated...",
                            style="red",
                        )
                await client.update_work_queue(
                    res.id, concurrency_limit=work_queue_concurrency
                )
                app.console.print(
                    f"Updated concurrency limit on work queue {work_queue_name!r} to {work_queue_concurrency}",
                    style="green",
                )
            except Exception as exc:
                exit_with_error(
                    f"Failed to set concurrency limit on work queue {work_queue_name}."
                )
        elif work_queue_concurrency:
            app.console.print(
                f"No work queue set! The concurrency limit cannot be updated."
            )


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


@deployment_app.command("set-schedule")
async def set_schedule(
    name: str,
    interval: Optional[float] = typer.Option(
        None,
        "--interval",
        help="An interval to schedule on, specified in seconds",
    ),
    interval_anchor: Optional[str] = typer.Option(
        None, "--anchor-date", help="The anchor date for an interval schedule"
    ),
    rrule_string: Optional[str] = typer.Option(
        None, "--rrule", help="Deployment schedule rrule string"
    ),
    cron_string: Optional[str] = typer.Option(
        None, "--cron", help="Deployment schedule cron string"
    ),
    cron_day_or: Optional[str] = typer.Option(
        None,
        "--day_or",
        help="Control how croniter handles `day` and `day_of_week` entries",
    ),
    timezone: Optional[str] = typer.Option(
        None,
        "--timezone",
        help="Deployment schedule timezone string e.g. 'America/New_York'",
    ),
):
    """
    Set schedule for a given deployment.
    """
    assert_deployment_name_format(name)

    interval_schedule = {
        "interval": interval,
        "interval_anchor": interval_anchor,
        "timezone": timezone,
    }
    cron_schedule = {"cron": cron_string, "day_or": cron_day_or, "timezone": timezone}
    if rrule_string is not None:
        rrule_schedule = json.loads(rrule_string)
    else:
        # fall back to empty schedule dictionary
        rrule_schedule = {"rrule": None}

    def updated_schedule_check(schedule):
        return any(v is not None for k, v in schedule.items() if k != "timezone")

    updated_schedules = list(
        filter(
            updated_schedule_check, (interval_schedule, cron_schedule, rrule_schedule)
        )
    )

    if len(updated_schedules) == 0:
        exit_with_error("No deployment schedule updates provided")
    if len(updated_schedules) > 1:
        exit_with_error("Incompatible schedule parameters")

    updated_schedule = {k: v for k, v in updated_schedules[0].items() if v is not None}

    async with get_client() as client:
        try:
            deployment = await client.read_deployment_by_name(name)
        except ObjectNotFound:
            exit_with_error(f"Deployment {name!r} not found!")

        await client.update_deployment(deployment, schedule=updated_schedule)
        exit_with_success("Updated deployment schedule!")


@deployment_app.command("pause-schedule")
async def pause_schedule(
    name: str,
):
    """
    Pause schedule of a given deployment.
    """
    assert_deployment_name_format(name)
    async with get_client() as client:
        try:
            deployment = await client.read_deployment_by_name(name)
        except ObjectNotFound:
            exit_with_error(f"Deployment {name!r} not found!")

        await client.update_deployment(deployment, is_schedule_active=False)
        exit_with_success(f"Paused schedule for deployment {name}")


@deployment_app.command("resume-schedule")
async def resume_schedule(
    name: str,
):
    """
    Resume schedule of a given deployment.
    """
    assert_deployment_name_format(name)
    async with get_client() as client:
        try:
            deployment = await client.read_deployment_by_name(name)
        except ObjectNotFound:
            exit_with_error(f"Deployment {name!r} not found!")

        await client.update_deployment(deployment, is_schedule_active=True)
        exit_with_success(f"Resumed schedule for deployment {name}")


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
    params: List[str] = typer.Option(
        None,
        "-p",
        "--param",
        help=(
            "A key, value pair (key=value) specifying a flow parameter. The value will be "
            "interpreted as JSON. May be passed multiple times to specify multiple "
            "parameter values."
        ),
    ),
    multiparams: Optional[str] = typer.Option(
        None,
        "--params",
        help=(
            "A mapping of parameters to values. To use a stdin, pass '-'. Any "
            "parameters passed with `--param` will take precedence over these values."
        ),
    ),
):
    """
    Create a flow run for the given flow and deployment.

    The flow run will be scheduled for now and an agent must execute it.

    The flow run will not execute until an agent starts.
    """
    multi_params = {}
    if multiparams:
        if multiparams == "-":
            multiparams = sys.stdin.read()
            if not multiparams:
                exit_with_error("No data passed to stdin")

        try:
            multi_params = json.loads(multiparams)
        except ValueError as exc:
            exit_with_error(f"Failed to parse JSON: {exc}")

    cli_params = _load_json_key_values(params, "parameter")
    conflicting_keys = set(cli_params.keys()).intersection(multi_params.keys())
    if conflicting_keys:
        app.console.print(
            "The following parameters were specified by `--param` and `--params`, the "
            f"`--param` value will be used: {conflicting_keys}"
        )
    parameters = {**multi_params, **cli_params}

    async with get_client() as client:
        deployment = await get_deployment(client, name, deployment_id)
        flow = await client.read_flow(deployment.flow_id)

        deployment_parameters = deployment.parameter_openapi_schema["properties"].keys()
        unknown_keys = set(parameters.keys()).difference(deployment_parameters)
        if unknown_keys:
            available_parameters = (
                (
                    "The following parameters are available on the deployment: "
                    + listrepr(deployment_parameters, sep=", ")
                )
                if deployment_parameters
                else "This deployment does not accept parameters."
            )

            exit_with_error(
                "The following parameters were specified but not found on the "
                f"deployment: {listrepr(unknown_keys, sep=', ')}"
                f"\n{available_parameters}"
            )

        app.console.print(
            f"Creating flow run for deployment '{flow.name}/{deployment.name}'...",
        )

        flow_run = await client.create_flow_run_from_deployment(
            deployment.id, parameters=parameters
        )

    connection_status = await check_orion_connection()
    ui_url = ui_base_url(connection_status)

    if ui_url:
        run_url = f"{ui_url}/flow-runs/flow-run/{flow_run.id}"
    else:
        run_url = "<no dashboard available>"

    app.console.print(f"Created flow run {flow_run.name!r}.")
    app.console.print(
        textwrap.dedent(
            f"""
        └── UUID: {flow_run.id}
        └── Parameters: {flow_run.parameters}
        └── URL: {run_url}
        """
        ).strip()
    )


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
    upload: bool = typer.Option(
        False,
        "--upload",
        help="A flag that, when provided, uploads this deployment's files to remote storage.",
    ),
    work_queue_concurrency: int = typer.Option(
        None,
        "--limit",
        "-l",
        help="Sets the concurrency limit on the work queue that handles this deployment's runs",
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

        await create_work_queue_and_set_concurrency_limit(
            deployment.work_queue_name, work_queue_concurrency
        )

        if upload:
            if (
                deployment.storage
                and "put-directory" in deployment.storage.get_block_capabilities()
            ):
                file_count = await deployment.upload_to_storage()
                if file_count:
                    app.console.print(
                        f"Successfully uploaded {file_count} files to {deployment.location}",
                        style="green",
                    )
            else:
                app.console.print(
                    f"Deployment storage {deployment.storage} does not have upload capabilities; no files uploaded.",
                    style="red",
                )

        deployment_id = await deployment.apply()
        app.console.print(
            f"Deployment '{deployment.flow_name}/{deployment.name}' successfully created with id '{deployment_id}'.",
            style="green",
        )

        connection_status = await check_orion_connection()
        ui = ui_base_url(connection_status)

        if ui:
            app.console.print(f"View Deployment in UI: {ui}/deployment/{deployment_id}")

        if deployment.work_queue_name is not None:
            app.console.print(
                "\nTo execute flow runs from this deployment, start an agent "
                f"that pulls work from the {deployment.work_queue_name!r} work queue:"
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


InfrastructureSlugs = Enum(
    "InfastructureSlugs",
    {
        slug: slug
        for slug, block in get_registry_for_type(Block).items()
        if "run-infrastructure" in block.get_block_capabilities()
    },
)


@deployment_app.command()
async def build(
    entrypoint: str = typer.Argument(
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
    work_queue_concurrency: int = typer.Option(
        None,
        "--limit",
        "-l",
        help="Sets the concurrency limit on the work queue that handles this deployment's runs",
    ),
    infra_type: InfrastructureSlugs = typer.Option(
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
        help="The slug of a remote storage block. Use the syntax: 'block_type/block_name', where block_type must be one of 'github', 's3', 'gcs', 'azure', 'smb'",
    ),
    skip_upload: bool = typer.Option(
        False,
        "--skip-upload",
        help="A flag that, when provided, skips uploading this deployment's files to remote storage.",
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
    path: str = typer.Option(
        None,
        "--path",
        help="An optional path to specify a subdirectory of remote storage to upload to, or to point to a subdirectory of a locally stored flow.",
    ),
    output: str = typer.Option(
        None,
        "--output",
        "-o",
        help="An optional filename to write the deployment file to.",
    ),
    _apply: bool = typer.Option(
        False,
        "--apply",
        "-a",
        help="An optional flag to automatically register the resulting deployment with the API.",
    ),
    param: List[str] = typer.Option(
        None,
        "--param",
        help="An optional parameter override, values are parsed as JSON strings e.g. --param question=ultimate --param answer=42",
    ),
    params: str = typer.Option(
        None,
        "--params",
        help='An optional parameter override in a JSON string format e.g. --params=\'{"question": "ultimate", "answer": 42}\'',
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
        fpath, obj_name = entrypoint.rsplit(":", 1)
    except ValueError as exc:
        if str(exc) == "not enough values to unpack (expected 2, got 1)":
            missing_flow_name_msg = f"Your flow entrypoint must include the name of the function that is the entrypoint to your flow.\nTry {entrypoint}:<flow_name>"
            exit_with_error(missing_flow_name_msg)
        else:
            raise exc
    try:
        flow = prefect.utilities.importtools.import_object(entrypoint)
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
        # Create an instance of the given type
        infrastructure = lookup_type(Block, infra_type.value)()
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
        try:
            schedule = RRuleSchedule(**json.loads(rrule))
        except json.JSONDecodeError:
            schedule = RRuleSchedule(rrule=rrule)

    # parse storage_block
    if storage_block:
        block_type, block_name, *block_path = storage_block.split("/")
        if block_path and path:
            exit_with_error(
                "Must provide a `path` explicitly or provide one on the storage block specification, but not both."
            )
        elif not path:
            path = "/".join(block_path)
        storage_block = f"{block_type}/{block_name}"
        storage = await Block.load(storage_block)
    else:
        storage = None

    if set_default_ignore_file(path="."):
        app.console.print(
            f"Default '.prefectignore' file written to {(Path('.') / '.prefectignore').absolute()}",
            style="green",
        )

    if param and (params is not None):
        exit_with_error("Can only pass one of `param` or `params` options")

    parameters = dict()

    if param:
        for p in param or []:
            k, unparsed_value = p.split("=", 1)
            try:
                v = json.loads(unparsed_value)
                app.console.print(
                    f"The parameter value {unparsed_value} is parsed as a JSON string"
                )
            except json.JSONDecodeError:
                v = unparsed_value
            parameters[k] = v

    if params is not None:
        parameters = json.loads(params)

    # set up deployment object
    entrypoint = (
        f"{Path(fpath).absolute().relative_to(Path('.').absolute())}:{obj_name}"
    )

    init_kwargs = dict(
        path=path,
        entrypoint=entrypoint,
        version=version,
        storage=storage,
        infra_overrides=infra_overrides or {},
    )

    if parameters:
        init_kwargs["parameters"] = parameters

    # if a schedule, tags, work_queue_name, or infrastructure are not provided via CLI,
    # we let `build_from_flow` load them from the server
    if schedule:
        init_kwargs.update(schedule=schedule)
    if tags:
        init_kwargs.update(tags=tags)
    if infrastructure:
        init_kwargs.update(infrastructure=infrastructure)
    if work_queue_name:
        init_kwargs.update(work_queue_name=work_queue_name)

    deployment_loc = output_file or f"{obj_name}-deployment.yaml"
    deployment = await Deployment.build_from_flow(
        flow=flow,
        name=name,
        output=deployment_loc,
        skip_upload=False,
        apply=False,
        **init_kwargs,
    )
    app.console.print(
        f"Deployment YAML created at '{Path(deployment_loc).absolute()!s}'.",
        style="green",
    )

    await create_work_queue_and_set_concurrency_limit(
        deployment.work_queue_name, work_queue_concurrency
    )

    # we process these separately for informative output
    if not skip_upload:
        if (
            deployment.storage
            and "put-directory" in deployment.storage.get_block_capabilities()
        ):
            file_count = await deployment.upload_to_storage()
            if file_count:
                app.console.print(
                    f"Successfully uploaded {file_count} files to {deployment.location}",
                    style="green",
                )
        else:
            app.console.print(
                f"Deployment storage {deployment.storage} does not have upload capabilities; no files uploaded.  Pass --skip-upload to suppress this warning.",
                style="green",
            )

    if _apply:
        deployment_id = await deployment.apply()
        app.console.print(
            f"Deployment '{deployment.flow_name}/{deployment.name}' successfully created with id '{deployment_id}'.",
            style="green",
        )
        if deployment.work_queue_name is not None:
            app.console.print(
                "\nTo execute flow runs from this deployment, start an agent "
                f"that pulls work from the {deployment.work_queue_name!r} work queue:"
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


def _load_json_key_values(
    cli_input: List[str], display_name: str
) -> Dict[str, Union[dict, str, int]]:
    """
    Parse a list of strings formatted as "key=value" where the value is loaded as JSON.

    We do the best here to display a helpful JSON parsing message, e.g.
    ```
    Error: Failed to parse JSON for parameter 'name' with value

        foo

    JSON Error: Expecting value: line 1 column 1 (char 0)
    Did you forget to include quotes? You may need to escape so your shell does not remove them, e.g. \"
    ```

    Args:
        cli_input: A list of "key=value" strings to parse
        display_name: A name to display in exceptions

    Returns:
        A mapping of keys -> parsed values
    """
    parsed = {}

    def cast_value(value: str) -> Any:
        """Cast the value from a string to a valid JSON type; add quotes for the user
        if necessary
        """
        try:
            return json.loads(value)
        except ValueError as exc:
            if (
                "Extra data" in str(exc) or "Expecting value" in str(exc)
            ) and '"' not in value:
                return cast_value(f'"{value}"')
            raise exc

    for spec in cli_input:
        try:
            key, _, value = spec.partition("=")
        except ValueError:
            exit_with_error(
                f"Invalid {display_name} option {spec!r}. Expected format 'key=value'."
            )

        try:
            parsed[key] = cast_value(value)
        except ValueError as exc:
            indented_value = textwrap.indent(value, prefix="\t")
            exit_with_error(
                f"Failed to parse JSON for {display_name} {key!r} with value"
                f"\n\n{indented_value}\n\n"
                f"JSON Error: {exc}"
            )

    return parsed
