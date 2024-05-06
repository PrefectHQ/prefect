"""
Command line interface for working with deployments.
"""

import json
import sys
import textwrap
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

import pendulum
import typer
import yaml
from rich.pretty import Pretty
from rich.table import Table

from prefect._internal.compatibility.experimental import experiment_enabled
from prefect.blocks.core import Block
from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.root import app
from prefect.client.orchestration import PrefectClient, ServerType, get_client
from prefect.client.schemas.filters import FlowFilter
from prefect.client.schemas.objects import DeploymentSchedule
from prefect.client.schemas.schedules import (
    CronSchedule,
    IntervalSchedule,
    RRuleSchedule,
)
from prefect.client.utilities import inject_client
from prefect.context import PrefectObjectRegistry, registry_from_script
from prefect.deployments import Deployment, load_deployments_from_yaml
from prefect.exceptions import (
    ObjectAlreadyExists,
    ObjectNotFound,
    PrefectHTTPStatusError,
    ScriptError,
    exception_traceback,
)
from prefect.flow_runs import wait_for_flow_run
from prefect.flows import load_flow_from_entrypoint
from prefect.settings import PREFECT_UI_URL
from prefect.states import Scheduled
from prefect.utilities.asyncutils import run_sync_in_worker_thread
from prefect.utilities.collections import listrepr
from prefect.utilities.dispatch import get_registry_for_type
from prefect.utilities.filesystem import create_default_ignore_file


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
schedule_app = PrefectTyper(
    name="schedule", help="Commands for interacting with your deployment's schedules."
)

deployment_app.add_typer(schedule_app, aliases=["schedule"])
app.add_typer(deployment_app, aliases=["deployments"])


def assert_deployment_name_format(name: str) -> None:
    if "/" not in name:
        exit_with_error(
            "Invalid deployment name. Expected '<flow-name>/<deployment-name>'"
        )


async def get_deployment(client: PrefectClient, name, deployment_id):
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
    work_queue_name, work_pool_name, work_queue_concurrency
):
    async with get_client() as client:
        if work_queue_concurrency is not None and work_queue_name:
            try:
                try:
                    await check_work_pool_exists(work_pool_name)
                    res = await client.create_work_queue(
                        name=work_queue_name, work_pool_name=work_pool_name
                    )
                except ObjectAlreadyExists:
                    res = await client.read_work_queue_by_name(
                        name=work_queue_name, work_pool_name=work_pool_name
                    )
                    if res.concurrency_limit != work_queue_concurrency:
                        if work_pool_name is None:
                            app.console.print(
                                (
                                    f"Work queue {work_queue_name!r} already exists"
                                    " with a concurrency limit of"
                                    f" {res.concurrency_limit}, this limit is being"
                                    " updated..."
                                ),
                                style="red",
                            )
                        else:
                            app.console.print(
                                (
                                    f"Work queue {work_queue_name!r} in work pool"
                                    f" {work_pool_name!r} already exists with a"
                                    f" concurrency limit of {res.concurrency_limit},"
                                    " this limit is being updated..."
                                ),
                                style="red",
                            )
                await client.update_work_queue(
                    res.id, concurrency_limit=work_queue_concurrency
                )
                if work_pool_name is None:
                    app.console.print(
                        (
                            "Updated concurrency limit on work queue"
                            f" {work_queue_name!r} to {work_queue_concurrency}"
                        ),
                        style="green",
                    )
                else:
                    app.console.print(
                        (
                            "Updated concurrency limit on work queue"
                            f" {work_queue_name!r} in work pool {work_pool_name!r} to"
                            f" {work_queue_concurrency}"
                        ),
                        style="green",
                    )
            except Exception:
                exit_with_error(
                    "Failed to set concurrency limit on work queue"
                    f" {work_queue_name!r} in work pool {work_pool_name!r}."
                )
        elif work_queue_concurrency:
            app.console.print(
                "No work queue set! The concurrency limit cannot be updated."
            )


@inject_client
async def check_work_pool_exists(
    work_pool_name: Optional[str], client: PrefectClient = None
):
    if work_pool_name is not None:
        try:
            await client.read_work_pool(work_pool_name=work_pool_name)
        except ObjectNotFound:
            app.console.print(
                (
                    "\nThis deployment specifies a work pool name of"
                    f" {work_pool_name!r}, but no such work pool exists.\n"
                ),
                style="red ",
            )
            app.console.print("To create a work pool via the CLI:\n")
            app.console.print(
                f"$ prefect work-pool create {work_pool_name!r}\n", style="blue"
            )
            exit_with_error("Work pool not found!")


@inject_client
async def _print_deployment_work_pool_instructions(
    work_pool_name: str, client: PrefectClient = None
):
    work_pool = await client.read_work_pool(work_pool_name)
    blurb = (
        "\nTo execute flow runs from this deployment, start an agent "
        f"that pulls work from the {work_pool_name!r} work pool:"
    )
    command = f"$ prefect agent start -p {work_pool_name!r}"
    if work_pool.type != "prefect-agent":
        if experiment_enabled("workers"):
            blurb = (
                "\nTo execute flow runs from this deployment, start a"
                " worker that pulls work from the"
                f" {work_pool_name!r} work pool:"
            )
            command = f"$ prefect worker start -p {work_pool_name!r}"
        else:
            blurb = (
                "\nTo execute flow runs from this deployment, please"
                " enable the workers CLI and start a worker that pulls"
                f" work from the {work_pool_name!r} work pool:"
            )
            command = (
                "$ prefect config set"
                " PREFECT_EXPERIMENTAL_ENABLE_WORKERS=True\n$ prefect"
                f" worker start -p {work_pool_name!r}"
            )

    app.console.print(blurb)
    app.console.print(command, style="blue")


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
            'schedules': None,
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

        if client.server_type.supports_automations():
            deployment_json["automations"] = [
                a.dict()
                for a in await client.read_resource_related_automations(
                    f"prefect.deployment.{deployment.id}"
                )
            ]

    app.console.print(Pretty(deployment_json))


@schedule_app.command("create")
async def create_schedule(
    name: str,
    interval: Optional[float] = typer.Option(
        None,
        "--interval",
        help="An interval to schedule on, specified in seconds",
        min=0.0001,
    ),
    interval_anchor: Optional[str] = typer.Option(
        None,
        "--anchor-date",
        help="The anchor date for an interval schedule",
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
    active: Optional[bool] = typer.Option(
        True,
        "--active",
        help="Whether the schedule is active. Defaults to True.",
    ),
    replace: Optional[bool] = typer.Option(
        False,
        "--replace",
        help="Replace the deployment's current schedule(s) with this new schedule.",
    ),
    assume_yes: Optional[bool] = typer.Option(
        False,
        "--accept-yes",
        "-y",
        help="Accept the confirmation prompt without prompting",
    ),
):
    """
    Create a schedule for a given deployment.
    """
    assert_deployment_name_format(name)

    if sum(option is not None for option in [interval, rrule_string, cron_string]) != 1:
        exit_with_error(
            "Exactly one of `--interval`, `--rrule`, or `--cron` must be provided."
        )

    schedule = None

    if interval_anchor and not interval:
        exit_with_error("An anchor date can only be provided with an interval schedule")

    if interval is not None:
        if interval_anchor:
            try:
                pendulum.parse(interval_anchor)
            except ValueError:
                return exit_with_error("The anchor date must be a valid date string.")
        interval_schedule = {
            "interval": interval,
            "anchor_date": interval_anchor,
            "timezone": timezone,
        }
        schedule = IntervalSchedule(
            **{k: v for k, v in interval_schedule.items() if v is not None}
        )

    if cron_string is not None:
        cron_schedule = {
            "cron": cron_string,
            "day_or": cron_day_or,
            "timezone": timezone,
        }
        schedule = CronSchedule(
            **{k: v for k, v in cron_schedule.items() if v is not None}
        )

    if rrule_string is not None:
        # a timezone in the `rrule_string` gets ignored by the RRuleSchedule constructor
        if "TZID" in rrule_string and not timezone:
            exit_with_error(
                "You can provide a timezone by providing a dict with a `timezone` key"
                " to the --rrule option. E.g. {'rrule': 'FREQ=MINUTELY;INTERVAL=5',"
                " 'timezone': 'America/New_York'}.\nAlternatively, you can provide a"
                " timezone by passing in a --timezone argument."
            )
        try:
            schedule = RRuleSchedule(**json.loads(rrule_string))
            if timezone:
                # override timezone if specified via CLI argument
                schedule.timezone = timezone
        except json.JSONDecodeError:
            schedule = RRuleSchedule(rrule=rrule_string, timezone=timezone)

    if schedule is None:
        return exit_with_success(
            "Could not create a valid schedule from the provided options."
        )

    async with get_client() as client:
        try:
            deployment = await client.read_deployment_by_name(name)
        except ObjectNotFound:
            return exit_with_error(f"Deployment {name!r} not found!")

        num_schedules = len(deployment.schedules)
        noun = "schedule" if num_schedules == 1 else "schedules"

        if replace and num_schedules > 0:
            if not assume_yes and not typer.confirm(
                f"Are you sure you want to replace {num_schedules} {noun} for {name}?"
            ):
                return exit_with_error("Schedule replacement cancelled.")

            for existing_schedule in deployment.schedules:
                try:
                    await client.delete_deployment_schedule(
                        deployment.id, existing_schedule.id
                    )
                except ObjectNotFound:
                    pass

        await client.create_deployment_schedules(deployment.id, [(schedule, active)])

        if replace and num_schedules > 0:
            exit_with_success(f"Replaced existing deployment {noun} with new schedule!")
        else:
            exit_with_success("Created deployment schedule!")


@schedule_app.command("delete")
async def delete_schedule(
    deployment_name: str,
    schedule_id: UUID,
    assume_yes: Optional[bool] = typer.Option(
        False,
        "--accept-yes",
        "-y",
        help="Accept the confirmation prompt without prompting",
    ),
):
    """
    Delete a deployment schedule.
    """
    assert_deployment_name_format(deployment_name)

    async with get_client() as client:
        try:
            deployment = await client.read_deployment_by_name(deployment_name)
        except ObjectNotFound:
            return exit_with_error(f"Deployment {deployment_name} not found!")

        try:
            schedule = [s for s in deployment.schedules if s.id == schedule_id][0]
        except IndexError:
            return exit_with_error("Deployment schedule not found!")

        if not assume_yes and not typer.confirm(
            f"Are you sure you want to delete this schedule: {schedule.schedule}",
        ):
            return exit_with_error("Deletion cancelled.")

        try:
            await client.delete_deployment_schedule(deployment.id, schedule_id)
        except ObjectNotFound:
            exit_with_error("Deployment schedule not found!")

        exit_with_success(f"Deleted deployment schedule {schedule_id}")


@schedule_app.command("pause")
async def pause_schedule(deployment_name: str, schedule_id: UUID):
    """
    Pause a deployment schedule.
    """
    assert_deployment_name_format(deployment_name)

    async with get_client() as client:
        try:
            deployment = await client.read_deployment_by_name(deployment_name)
        except ObjectNotFound:
            return exit_with_error(f"Deployment {deployment_name!r} not found!")

        try:
            schedule = [s for s in deployment.schedules if s.id == schedule_id][0]
        except IndexError:
            return exit_with_error("Deployment schedule not found!")

        if not schedule.active:
            return exit_with_error(
                f"Deployment schedule {schedule_id} is already inactive"
            )

        await client.update_deployment_schedule(
            deployment.id, schedule_id, active=False
        )
        exit_with_success(
            f"Paused schedule {schedule.schedule} for deployment {deployment_name}"
        )


@schedule_app.command("resume")
async def resume_schedule(deployment_name: str, schedule_id: UUID):
    """
    Resume a deployment schedule.
    """
    assert_deployment_name_format(deployment_name)

    async with get_client() as client:
        try:
            deployment = await client.read_deployment_by_name(deployment_name)
        except ObjectNotFound:
            return exit_with_error(f"Deployment {deployment_name!r} not found!")

        try:
            schedule = [s for s in deployment.schedules if s.id == schedule_id][0]
        except IndexError:
            return exit_with_error("Deployment schedule not found!")

        if schedule.active:
            return exit_with_error(
                f"Deployment schedule {schedule_id} is already active"
            )

        await client.update_deployment_schedule(deployment.id, schedule_id, active=True)
        exit_with_success(
            f"Resumed schedule {schedule.schedule} for deployment {deployment_name}"
        )


@schedule_app.command("ls")
async def list_schedules(deployment_name: str):
    """
    View all schedules for a deployment.
    """
    assert_deployment_name_format(deployment_name)
    async with get_client() as client:
        try:
            deployment = await client.read_deployment_by_name(deployment_name)
        except ObjectNotFound:
            return exit_with_error(f"Deployment {deployment_name!r} not found!")

    def sort_by_created_key(schedule: DeploymentSchedule):  # type: ignore
        assert schedule.created is not None, "All schedules should have a created time."
        return pendulum.now("utc") - schedule.created

    def schedule_details(schedule: DeploymentSchedule) -> str:
        if isinstance(schedule.schedule, IntervalSchedule):
            return f"interval: {schedule.schedule.interval}s"
        elif isinstance(schedule.schedule, CronSchedule):
            return f"cron: {schedule.schedule.cron}"
        elif isinstance(schedule.schedule, RRuleSchedule):
            return f"rrule: {schedule.schedule.rrule}"
        else:
            return "unknown"

    table = Table(
        title="Deployment Schedules",
    )
    table.add_column("ID", style="blue", no_wrap=True)
    table.add_column("Schedule", style="cyan", no_wrap=False)
    table.add_column("Active", style="purple", no_wrap=True)

    for schedule in sorted(deployment.schedules, key=sort_by_created_key):
        table.add_row(
            str(schedule.id),
            schedule_details(schedule),
            str(schedule.active),
        )

    app.console.print(table)


@schedule_app.command("clear")
async def clear_schedules(
    deployment_name: str,
    assume_yes: Optional[bool] = typer.Option(
        False,
        "--accept-yes",
        "-y",
        help="Accept the confirmation prompt without prompting",
    ),
):
    """
    Clear all schedules for a deployment.
    """
    assert_deployment_name_format(deployment_name)
    async with get_client() as client:
        try:
            deployment = await client.read_deployment_by_name(deployment_name)
        except ObjectNotFound:
            return exit_with_error(f"Deployment {deployment_name!r} not found!")

        await client.read_flow(deployment.flow_id)

        # Get input from user: confirm removal of all schedules
        if not assume_yes and not typer.confirm(
            "Are you sure you want to clear all schedules for this deployment?",
        ):
            exit_with_error("Clearing schedules cancelled.")

        for schedule in deployment.schedules:
            try:
                await client.delete_deployment_schedule(deployment.id, schedule.id)
            except ObjectNotFound:
                pass

        exit_with_success(f"Cleared all schedules for deployment {deployment_name}")


@deployment_app.command(
    "set-schedule",
    deprecated=True,
    deprecated_start_date="Mar 2024",
    deprecated_help="Use 'prefect deployment schedule create' instead.",
    deprecated_name="deployment set-schedule",
)
async def _set_schedule(
    name: str,
    interval: Optional[float] = typer.Option(
        None,
        "--interval",
        help="An interval to schedule on, specified in seconds",
        min=0.0001,
    ),
    interval_anchor: Optional[str] = typer.Option(
        None,
        "--anchor-date",
        help="The anchor date for an interval schedule",
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
    no_schedule: bool = typer.Option(
        False,
        "--no-schedule",
        help="An optional flag to disable scheduling for this deployment.",
    ),
    deprecated=True,
):
    """
    Set schedule for a given deployment.

    This command is deprecated. Use 'prefect deployment schedule create' instead.
    """
    assert_deployment_name_format(name)

    exclusive_options = sum(
        option is not None
        for option in [interval, rrule_string, cron_string] + [no_schedule or None]
    )

    if exclusive_options != 1:
        exit_with_error(
            "Exactly one of `--interval`, `--rrule`, `--cron` or `--no-schedule` must"
            " be provided."
        )

    if no_schedule:
        return await clear_schedules(name)
    else:
        async with get_client() as client:
            try:
                deployment = await client.read_deployment_by_name(name)
            except ObjectNotFound:
                return exit_with_error(f"Deployment {name!r} not found!")

            if len(deployment.schedules) > 1:
                return exit_with_error(
                    f"Deployment {name!r} has multiple schedules. "
                    "Use `prefect deployment schedules create` instead."
                )

            if deployment.schedules:
                try:
                    await client.delete_deployment_schedule(
                        deployment.id, deployment.schedules[0].id
                    )
                except ObjectNotFound:
                    pass

            await create_schedule(
                name=name,
                interval=interval,
                interval_anchor=interval_anchor,
                rrule_string=rrule_string,
                cron_string=cron_string,
                cron_day_or=cron_day_or,
                timezone=timezone,
                active=True,
            )


@deployment_app.command(
    "pause-schedule",
    deprecated=True,
    deprecated_start_date="Mar 2024",
    deprecated_help="Use 'prefect deployment schedule pause' instead.",
    deprecated_name="deployment pause-schedule",
)
async def _pause_schedule(
    name: str,
):
    """
    Pause schedule of a given deployment.

    This command is deprecated. Use `prefect deployment schedule pause` instead.
    """
    assert_deployment_name_format(name)

    async with get_client() as client:
        try:
            deployment = await client.read_deployment_by_name(name)
        except ObjectNotFound:
            return exit_with_error(f"Deployment {name!r} not found!")

        if not deployment.schedules:
            return exit_with_error(f"Deployment {name!r} has no schedules.")

        if len(deployment.schedules) > 1:
            return exit_with_error(
                f"Deployment {name!r} has multiple schedules. Use `prefect deployment"
                " schedule pause <deployment_name> <schedule_id>`"
            )

        return await pause_schedule(name, deployment.schedules[0].id)


@deployment_app.command(
    "resume-schedule",
    deprecated=True,
    deprecated_start_date="Mar 2024",
    deprecated_help="Use 'prefect deployment schedule resume' instead.",
    deprecated_name="deployment resume-schedule",
)
async def _resume_schedule(
    name: str,
):
    """
    Resume schedule of a given deployment.

    This command is deprecated. Use `prefect deployment schedule resume` instead.
    """
    # TODO only work if there is one schedule, otherwise error
    assert_deployment_name_format(name)
    async with get_client() as client:
        try:
            deployment = await client.read_deployment_by_name(name)
        except ObjectNotFound:
            return exit_with_error(f"Deployment {name!r} not found!")

        if not deployment.schedules:
            return exit_with_error(f"Deployment {name!r} has no schedules.")

        if len(deployment.schedules) > 1:
            return exit_with_error(
                f"Deployment {name!r} has multiple schedules. "
                "Use `prefect deployment schedule pause <deployment_name> <schedule_id>"
            )

        return await resume_schedule(name, deployment.schedules[0].id)


@deployment_app.command()
async def ls(flow_name: Optional[List[str]] = None, by_created: bool = False):
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

    def sort_by_name_keys(d):
        return flows[d.flow_id].name, d.name

    def sort_by_created_key(d):
        return pendulum.now("utc") - d.created

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
        None,
        "--id",
        help=("A deployment id to search for if no name is given"),
    ),
    job_variables: List[str] = typer.Option(
        None,
        "-jv",
        "--job-variable",
        help=(
            "A key, value pair (key=value) specifying a flow run job variable. The value will"
            " be interpreted as JSON. May be passed multiple times to specify multiple"
            " job variable values."
        ),
    ),
    params: List[str] = typer.Option(
        None,
        "-p",
        "--param",
        help=(
            "A key, value pair (key=value) specifying a flow parameter. The value will"
            " be interpreted as JSON. May be passed multiple times to specify multiple"
            " parameter values."
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
    start_in: Optional[str] = typer.Option(
        None,
        "--start-in",
        help=(
            "A human-readable string specifying a time interval to wait before starting"
            " the flow run. E.g. 'in 5 minutes', 'in 1 hour', 'in 2 days'."
        ),
    ),
    start_at: Optional[str] = typer.Option(
        None,
        "--start-at",
        help=(
            "A human-readable string specifying a time to start the flow run. E.g."
            " 'at 5:30pm', 'at 2022-08-01 17:30', 'at 2022-08-01 17:30:00'."
        ),
    ),
    tags: List[str] = typer.Option(
        None,
        "--tag",
        help=("Tag(s) to be applied to flow run."),
    ),
    watch: bool = typer.Option(
        False,
        "--watch",
        help=("Whether to poll the flow run until a terminal state is reached."),
    ),
    watch_interval: Optional[int] = typer.Option(
        None,
        "--watch-interval",
        help=("How often to poll the flow run for state changes (in seconds)."),
    ),
    watch_timeout: Optional[int] = typer.Option(
        None,
        "--watch-timeout",
        help=("Timeout for --watch."),
    ),
):
    """
    Create a flow run for the given flow and deployment.

    The flow run will be scheduled to run immediately unless `--start-in` or `--start-at` is specified.
    The flow run will not execute until a worker starts.
    To watch the flow run until it reaches a terminal state, use the `--watch` flag.
    """
    import dateparser

    now = pendulum.now("UTC")

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
        if watch_interval and not watch:
            exit_with_error(
                "`--watch-interval` can only be used with `--watch`.",
            )
    cli_params = _load_json_key_values(params or [], "parameter")
    conflicting_keys = set(cli_params.keys()).intersection(multi_params.keys())
    if conflicting_keys:
        app.console.print(
            "The following parameters were specified by `--param` and `--params`, the "
            f"`--param` value will be used: {conflicting_keys}"
        )
    parameters = {**multi_params, **cli_params}

    job_vars = _load_json_key_values(job_variables or [], "job variable")
    if start_in and start_at:
        exit_with_error(
            "Only one of `--start-in` or `--start-at` can be set, not both."
        )

    elif start_in is None and start_at is None:
        scheduled_start_time = now
        human_dt_diff = " (now)"
    else:
        if start_in:
            start_time_raw = "in " + start_in
        else:
            start_time_raw = "at " + start_at
        with warnings.catch_warnings():
            # PyTZ throws a warning based on dateparser usage of the library
            # See https://github.com/scrapinghub/dateparser/issues/1089
            warnings.filterwarnings("ignore", module="dateparser")

            try:
                start_time_parsed = dateparser.parse(
                    start_time_raw,
                    settings={
                        "TO_TIMEZONE": "UTC",
                        "RETURN_AS_TIMEZONE_AWARE": False,
                        "PREFER_DATES_FROM": "future",
                        "RELATIVE_BASE": datetime.fromtimestamp(
                            now.timestamp(), tz=timezone.utc
                        ),
                    },
                )

            except Exception as exc:
                exit_with_error(f"Failed to parse '{start_time_raw!r}': {exc!s}")

        if start_time_parsed is None:
            exit_with_error(f"Unable to parse scheduled start time {start_time_raw!r}.")

        scheduled_start_time = pendulum.instance(start_time_parsed)
        human_dt_diff = (
            " (" + pendulum.format_diff(scheduled_start_time.diff(now)) + ")"
        )

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

        try:
            flow_run = await client.create_flow_run_from_deployment(
                deployment.id,
                parameters=parameters,
                state=Scheduled(scheduled_time=scheduled_start_time),
                tags=tags,
                job_variables=job_vars,
            )
        except PrefectHTTPStatusError as exc:
            detail = exc.response.json().get("detail")
            if detail:
                exit_with_error(
                    exc.response.json()["detail"],
                )
            else:
                raise

    if PREFECT_UI_URL:
        run_url = f"{PREFECT_UI_URL.value()}/flow-runs/flow-run/{flow_run.id}"
    else:
        run_url = "<no dashboard available>"

    datetime_local_tz = scheduled_start_time.in_tz(pendulum.tz.local_timezone())
    scheduled_display = (
        datetime_local_tz.to_datetime_string()
        + " "
        + datetime_local_tz.tzname()
        + human_dt_diff
    )

    app.console.print(f"Created flow run {flow_run.name!r}.")
    app.console.print(
        textwrap.dedent(
            f"""
        └── UUID: {flow_run.id}
        └── Parameters: {flow_run.parameters}
        └── Job Variables: {flow_run.job_variables}
        └── Scheduled start time: {scheduled_display}
        └── URL: {run_url}
        """
        ).strip(),
        soft_wrap=True,
    )
    if watch:
        watch_interval = 5 if watch_interval is None else watch_interval
        app.console.print(f"Watching flow run {flow_run.name!r}...")
        finished_flow_run = await wait_for_flow_run(
            flow_run.id,
            timeout=watch_timeout,
            poll_interval=watch_interval,
            log_states=True,
        )
        finished_flow_run_state = finished_flow_run.state
        if finished_flow_run_state.is_completed():
            exit_with_success(
                f"Flow run finished successfully in {finished_flow_run_state.name!r}."
            )
        exit_with_error(
            f"Flow run finished in state {finished_flow_run_state.name!r}.",
            code=1,
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


@deployment_app.command(
    deprecated=True,
    deprecated_start_date="Mar 2024",
    deprecated_name="deployment apply",
    deprecated_help="Use 'prefect deploy' to deploy flows via YAML instead.",
)
async def apply(
    paths: List[str] = typer.Argument(
        ...,
        help="One or more paths to deployment YAML files.",
    ),
    upload: bool = typer.Option(
        False,
        "--upload",
        help=(
            "A flag that, when provided, uploads this deployment's files to remote"
            " storage."
        ),
    ),
    work_queue_concurrency: int = typer.Option(
        None,
        "--limit",
        "-l",
        help=(
            "Sets the concurrency limit on the work queue that handles this"
            " deployment's runs"
        ),
    ),
):
    """
    Create or update a deployment from a YAML file.
    """
    deployment = None
    async with get_client() as client:
        for path in paths:
            try:
                deployment = await Deployment.load_from_yaml(path)
                app.console.print(
                    f"Successfully loaded {deployment.name!r}", style="green"
                )
            except Exception as exc:
                exit_with_error(
                    f"'{path!s}' did not conform to deployment spec: {exc!r}"
                )

            assert deployment

            await create_work_queue_and_set_concurrency_limit(
                deployment.work_queue_name,
                deployment.work_pool_name,
                work_queue_concurrency,
            )

            if upload:
                if (
                    deployment.storage
                    and "put-directory" in deployment.storage.get_block_capabilities()
                ):
                    file_count = await deployment.upload_to_storage()
                    if file_count:
                        app.console.print(
                            (
                                f"Successfully uploaded {file_count} files to"
                                f" {deployment.location}"
                            ),
                            style="green",
                        )
                else:
                    app.console.print(
                        (
                            f"Deployment storage {deployment.storage} does not have"
                            " upload capabilities; no files uploaded."
                        ),
                        style="red",
                    )
            await check_work_pool_exists(
                work_pool_name=deployment.work_pool_name, client=client
            )

            if client.server_type != ServerType.CLOUD and deployment.triggers:
                app.console.print(
                    (
                        "Deployment triggers are only supported on "
                        f"Prefect Cloud. Triggers defined in {path!r} will be "
                        "ignored."
                    ),
                    style="red",
                )

            deployment_id = await deployment.apply()
            app.console.print(
                (
                    f"Deployment '{deployment.flow_name}/{deployment.name}'"
                    f" successfully created with id '{deployment_id}'."
                ),
                style="green",
            )

            if PREFECT_UI_URL:
                app.console.print(
                    "View Deployment in UI:"
                    f" {PREFECT_UI_URL.value()}/deployments/deployment/{deployment_id}"
                )

            if deployment.work_pool_name is not None:
                await _print_deployment_work_pool_instructions(
                    work_pool_name=deployment.work_pool_name, client=client
                )
            elif deployment.work_queue_name is not None:
                app.console.print(
                    "\nTo execute flow runs from this deployment, start an agent that"
                    f" pulls work from the {deployment.work_queue_name!r} work queue:"
                )
                app.console.print(
                    f"$ prefect agent start -q {deployment.work_queue_name!r}",
                    style="blue",
                )
            else:
                app.console.print(
                    (
                        "\nThis deployment does not specify a work queue name, which"
                        " means agents will not be able to pick up its runs. To add a"
                        " work queue, edit the deployment spec and re-run this command,"
                        " or visit the deployment in the UI."
                    ),
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


builtin_infrastructure_types = [
    slug
    for slug, block in get_registry_for_type(Block).items()
    if "run-infrastructure" in block.get_block_capabilities()
]


@deployment_app.command(
    deprecated=True,
    deprecated_start_date="Mar 2024",
    deprecated_name="deployment build",
    deprecated_help="Use 'prefect deploy' to deploy flows via YAML instead.",
)
async def build(
    entrypoint: str = typer.Argument(
        ...,
        help=(
            "The path to a flow entrypoint, in the form of"
            " `./path/to/file.py:flow_func_name`"
        ),
    ),
    name: str = typer.Option(
        None, "--name", "-n", help="The name to give the deployment."
    ),
    description: str = typer.Option(
        None,
        "--description",
        "-d",
        help=(
            "The description to give the deployment. If not provided, the description"
            " will be populated from the flow's description."
        ),
    ),
    version: str = typer.Option(
        None, "--version", "-v", help="A version to give the deployment."
    ),
    tags: List[str] = typer.Option(
        None,
        "-t",
        "--tag",
        help=(
            "One or more optional tags to apply to the deployment. Note: tags are used"
            " only for organizational purposes. For delegating work to agents, use the"
            " --work-queue flag."
        ),
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
    work_pool_name: str = typer.Option(
        None,
        "-p",
        "--pool",
        help="The work pool that will handle this deployment's runs.",
    ),
    work_queue_concurrency: int = typer.Option(
        None,
        "--limit",
        "-l",
        help=(
            "Sets the concurrency limit on the work queue that handles this"
            " deployment's runs"
        ),
    ),
    infra_type: str = typer.Option(
        None,
        "--infra",
        "-i",
        help="The infrastructure type to use, prepopulated with defaults. For example: "
        + listrepr(builtin_infrastructure_types, sep=", "),
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
        help=(
            "One or more optional infrastructure overrides provided as a dot delimited"
            " path, e.g., `env.env_key=env_value`"
        ),
    ),
    storage_block: str = typer.Option(
        None,
        "--storage-block",
        "-sb",
        help=(
            "The slug of a remote storage block. Use the syntax:"
            " 'block_type/block_name', where block_type is one of 'github', 's3',"
            " 'gcs', 'azure', 'smb', or a registered block from a library that"
            " implements the WritableDeploymentStorage interface such as"
            " 'gitlab-repository', 'bitbucket-repository', 's3-bucket',"
            " 'gcs-bucket'"
        ),
    ),
    skip_upload: bool = typer.Option(
        False,
        "--skip-upload",
        help=(
            "A flag that, when provided, skips uploading this deployment's files to"
            " remote storage."
        ),
    ),
    cron: str = typer.Option(
        None,
        "--cron",
        help="A cron string that will be used to set a CronSchedule on the deployment.",
    ),
    interval: int = typer.Option(
        None,
        "--interval",
        help=(
            "An integer specifying an interval (in seconds) that will be used to set an"
            " IntervalSchedule on the deployment."
        ),
    ),
    interval_anchor: Optional[str] = typer.Option(
        None, "--anchor-date", help="The anchor date for an interval schedule"
    ),
    rrule: str = typer.Option(
        None,
        "--rrule",
        help="An RRule that will be used to set an RRuleSchedule on the deployment.",
    ),
    timezone: str = typer.Option(
        None,
        "--timezone",
        help="Deployment schedule timezone string e.g. 'America/New_York'",
    ),
    path: str = typer.Option(
        None,
        "--path",
        help=(
            "An optional path to specify a subdirectory of remote storage to upload to,"
            " or to point to a subdirectory of a locally stored flow."
        ),
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
        help=(
            "An optional flag to automatically register the resulting deployment with"
            " the API."
        ),
    ),
    param: List[str] = typer.Option(
        None,
        "--param",
        help=(
            "An optional parameter override, values are parsed as JSON strings e.g."
            " --param question=ultimate --param answer=42"
        ),
    ),
    params: str = typer.Option(
        None,
        "--params",
        help=(
            "An optional parameter override in a JSON string format e.g."
            ' --params=\'{"question": "ultimate", "answer": 42}\''
        ),
    ),
    no_schedule: bool = typer.Option(
        False,
        "--no-schedule",
        help="An optional flag to disable scheduling for this deployment.",
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

    if (
        len([value for value in (cron, rrule, interval) if value is not None])
        + (1 if no_schedule else 0)
        > 1
    ):
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
            missing_flow_name_msg = (
                "Your flow entrypoint must include the name of the function that is"
                f" the entrypoint to your flow.\nTry {entrypoint}:<flow_name>"
            )
            exit_with_error(missing_flow_name_msg)
        else:
            raise exc
    try:
        flow = await run_sync_in_worker_thread(load_flow_from_entrypoint, entrypoint)
    except Exception as exc:
        exit_with_error(exc)
    app.console.print(f"Found flow {flow.name!r}", style="green")
    job_variables = {}
    for override in overrides or []:
        key, value = override.split("=", 1)
        job_variables[key] = value

    if infra_block:
        infrastructure = await Block.load(infra_block)
    elif infra_type:
        # Create an instance of the given type
        infrastructure = Block.get_block_class_from_key(infra_type)()
    else:
        # will reset to a default of Process is no infra is present on the
        # server-side definition of this deployment
        infrastructure = None

    if interval_anchor and not interval:
        exit_with_error("An anchor date can only be provided with an interval schedule")

    schedule = None
    if cron:
        cron_kwargs = {"cron": cron, "timezone": timezone}
        schedule = CronSchedule(
            **{k: v for k, v in cron_kwargs.items() if v is not None}
        )
    elif interval:
        interval_kwargs = {
            "interval": timedelta(seconds=interval),
            "anchor_date": interval_anchor,
            "timezone": timezone,
        }
        schedule = IntervalSchedule(
            **{k: v for k, v in interval_kwargs.items() if v is not None}
        )
    elif rrule:
        try:
            schedule = RRuleSchedule(**json.loads(rrule))
            if timezone:
                # override timezone if specified via CLI argument
                schedule.timezone = timezone
        except json.JSONDecodeError:
            schedule = RRuleSchedule(rrule=rrule, timezone=timezone)

    # parse storage_block
    if storage_block:
        block_type, block_name, *block_path = storage_block.split("/")
        if block_path and path:
            exit_with_error(
                "Must provide a `path` explicitly or provide one on the storage block"
                " specification, but not both."
            )
        elif not path:
            path = "/".join(block_path)
        storage_block = f"{block_type}/{block_name}"
        storage = await Block.load(storage_block)
    else:
        storage = None

    if create_default_ignore_file(path="."):
        app.console.print(
            (
                "Default '.prefectignore' file written to"
                f" {(Path('.') / '.prefectignore').absolute()}"
            ),
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
        job_variables=job_variables or {},
    )

    if parameters:
        init_kwargs["parameters"] = parameters

    if description:
        init_kwargs["description"] = description

    # if a schedule, tags, work_queue_name, or infrastructure are not provided via CLI,
    # we let `build_from_flow` load them from the server
    if schedule or no_schedule:
        init_kwargs.update(schedule=schedule)
    if tags:
        init_kwargs.update(tags=tags)
    if infrastructure:
        init_kwargs.update(infrastructure=infrastructure)
    if work_queue_name:
        init_kwargs.update(work_queue_name=work_queue_name)
    if work_pool_name:
        init_kwargs.update(work_pool_name=work_pool_name)

    deployment_loc = output_file or f"{obj_name}-deployment.yaml"
    deployment = await Deployment.build_from_flow(
        flow=flow,
        name=name,
        output=deployment_loc,
        skip_upload=skip_upload,
        apply=False,
        **init_kwargs,
    )
    app.console.print(
        f"Deployment YAML created at '{Path(deployment_loc).absolute()!s}'.",
        style="green",
    )

    await create_work_queue_and_set_concurrency_limit(
        deployment.work_queue_name, deployment.work_pool_name, work_queue_concurrency
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
                    (
                        f"Successfully uploaded {file_count} files to"
                        f" {deployment.location}"
                    ),
                    style="green",
                )
        else:
            app.console.print(
                (
                    f"Deployment storage {deployment.storage} does not have upload"
                    " capabilities; no files uploaded.  Pass --skip-upload to suppress"
                    " this warning."
                ),
                style="green",
            )

    if _apply:
        async with get_client() as client:
            await check_work_pool_exists(
                work_pool_name=deployment.work_pool_name, client=client
            )
            deployment_id = await deployment.apply()
            app.console.print(
                (
                    f"Deployment '{deployment.flow_name}/{deployment.name}'"
                    f" successfully created with id '{deployment_id}'."
                ),
                style="green",
            )
            if deployment.work_pool_name is not None:
                await _print_deployment_work_pool_instructions(
                    work_pool_name=deployment.work_pool_name, client=client
                )

            elif deployment.work_queue_name is not None:
                app.console.print(
                    "\nTo execute flow runs from this deployment, start an agent that"
                    f" pulls work from the {deployment.work_queue_name!r} work queue:"
                )
                app.console.print(
                    f"$ prefect agent start -q {deployment.work_queue_name!r}",
                    style="blue",
                )
            else:
                app.console.print(
                    (
                        "\nThis deployment does not specify a work queue name, which"
                        " means agents will not be able to pick up its runs. To add a"
                        " work queue, edit the deployment spec and re-run this command,"
                        " or visit the deployment in the UI."
                    ),
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
