"""
Command line interface for working with deployments.
"""

from __future__ import annotations

import json
import sys
import textwrap
import warnings
from asyncio import iscoroutine
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Optional, TypedDict
from uuid import UUID

import typer
import yaml
from rich.console import Console
from rich.pretty import Pretty
from rich.table import Table

from prefect.blocks.core import Block
from prefect.cli._types import PrefectTyper
from prefect.cli._utilities import exit_with_error, exit_with_success
from prefect.cli.root import app, is_interactive
from prefect.client.orchestration import get_client
from prefect.client.schemas.filters import FlowFilter, FlowFilterId, FlowFilterName
from prefect.client.schemas.objects import DeploymentSchedule
from prefect.client.schemas.responses import DeploymentResponse
from prefect.client.schemas.schedules import (
    CronSchedule,
    IntervalSchedule,
    RRuleSchedule,
)
from prefect.client.utilities import inject_client
from prefect.exceptions import (
    ObjectAlreadyExists,
    ObjectNotFound,
    PrefectHTTPStatusError,
)
from prefect.flow_runs import wait_for_flow_run
from prefect.states import Scheduled
from prefect.types._datetime import (
    DateTime,
    format_diff,
    local_timezone,
    parse_datetime,
)
from prefect.utilities import urls
from prefect.utilities.collections import listrepr

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient


def str_presenter(
    dumper: yaml.Dumper | yaml.representer.SafeRepresenter, data: str
) -> yaml.ScalarNode:
    """
    configures yaml for dumping multiline strings
    Ref: https://stackoverflow.com/questions/8640959/how-can-i-control-what-scalar-form-pyyaml-uses-for-my-data
    """
    if len(data.splitlines()) > 1:  # check for multiline string
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")  # type: ignore[reportUnknownMemberType] incomplete type stubs
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)  # type: ignore[reportUnknownMemberType] incomplete type stubs


yaml.add_representer(str, str_presenter)
yaml.representer.SafeRepresenter.add_representer(str, str_presenter)

deployment_app: PrefectTyper = PrefectTyper(
    name="deployment", help="Manage deployments."
)
schedule_app: PrefectTyper = PrefectTyper(
    name="schedule", help="Manage deployment schedules."
)

deployment_app.add_typer(schedule_app, aliases=["schedule"])
app.add_typer(deployment_app, aliases=["deployments"])


def assert_deployment_name_format(name: str) -> None:
    if "/" not in name:
        exit_with_error(
            "Invalid deployment name. Expected '<flow-name>/<deployment-name>'"
        )


async def get_deployment(
    client: "PrefectClient", name: str | None, deployment_id: str | None
) -> DeploymentResponse:
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
    work_queue_name: str,
    work_pool_name: str | None,
    work_queue_concurrency: int | None,
) -> None:
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
    work_pool_name: str | None, client: "PrefectClient | None" = None
):
    if TYPE_CHECKING:
        assert client is not None
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


class RichTextIO:
    def __init__(self, console: Console, prefix: str | None = None) -> None:
        self.console = console
        self.prefix = prefix

    def write(self, content: str) -> None:
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

        deployment_json = deployment.model_dump(mode="json")

        if deployment.infrastructure_document_id:
            coro = Block.load_from_ref(deployment.infrastructure_document_id)
            if TYPE_CHECKING:
                assert iscoroutine(coro)
            infrastructure = await coro
            deployment_json["infrastructure"] = infrastructure.model_dump(
                exclude={"_block_document_id", "_block_document_name", "_is_anonymous"}
            )

        deployment_json["automations"] = [
            a.model_dump()
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
    cron_day_or: bool = typer.Option(
        True,
        "--day_or",
        help="Control how croniter handles `day` and `day_of_week` entries",
    ),
    timezone: Optional[str] = typer.Option(
        None,
        "--timezone",
        help="Deployment schedule timezone string e.g. 'America/New_York'",
    ),
    active: bool = typer.Option(
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
                parse_datetime(interval_anchor)
            except ValueError:
                return exit_with_error("The anchor date must be a valid date string.")

        IntervalScheduleOptions = TypedDict(
            "IntervalScheduleOptions",
            {
                "interval": timedelta,
                "anchor_date": str,
                "timezone": str,
            },
            total=False,
        )
        interval_schedule: IntervalScheduleOptions = {
            "interval": timedelta(seconds=interval),
        }
        if interval_anchor:
            interval_schedule["anchor_date"] = interval_anchor
        if timezone:
            interval_schedule["timezone"] = timezone
        schedule = IntervalSchedule(**interval_schedule)

    if cron_string is not None:
        CronScheduleOptions = TypedDict(
            "CronScheduleOptions",
            {
                "cron": str,
                "day_or": bool,
                "timezone": str,
            },
            total=False,
        )
        cron_schedule: CronScheduleOptions = {
            "cron": cron_string,
            "day_or": cron_day_or,
        }
        if timezone:
            cron_schedule["timezone"] = timezone

        schedule = CronSchedule(**cron_schedule)

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
    assume_yes: bool = typer.Option(
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
        return DateTime.now("utc") - schedule.created

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
    assume_yes: bool = typer.Option(
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


@deployment_app.command()
async def ls(flow_name: Optional[list[str]] = None, by_created: bool = False):
    """
    View all deployments or deployments for specific flows.
    """
    async with get_client() as client:
        deployments = await client.read_deployments(
            flow_filter=FlowFilter(name=FlowFilterName(any_=flow_name))
            if flow_name
            else None
        )
        flows = {
            flow.id: flow
            for flow in await client.read_flows(
                flow_filter=FlowFilter(
                    id=FlowFilterId(any_=[d.flow_id for d in deployments])
                )
            )
        }

    def sort_by_name_keys(d: DeploymentResponse):
        return flows[d.flow_id].name, d.name

    def sort_by_created_key(d: DeploymentResponse):
        assert d.created is not None, "All deployments should have a created time."
        return DateTime.now("utc") - d.created

    table = Table(
        title="Deployments",
        expand=True,
    )
    table.add_column("Name", style="blue", no_wrap=True, ratio=40)
    table.add_column("ID", style="cyan", no_wrap=True, ratio=40)
    table.add_column(
        "Work Pool", style="green", no_wrap=True, ratio=20, overflow="crop"
    )

    for deployment in sorted(
        deployments, key=sort_by_created_key if by_created else sort_by_name_keys
    ):
        table.add_row(
            f"{flows[deployment.flow_id].name}/[bold]{deployment.name}[/]",
            str(deployment.id),
            deployment.work_pool_name or "",
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
    job_variables: list[str] = typer.Option(
        None,
        "-jv",
        "--job-variable",
        help=(
            "A key, value pair (key=value) specifying a flow run job variable. The value will"
            " be interpreted as JSON. May be passed multiple times to specify multiple"
            " job variable values."
        ),
    ),
    params: list[str] = typer.Option(
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
    tags: list[str] = typer.Option(
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

    now = DateTime.now("UTC")

    multi_params: dict[str, Any] = {}
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
    cli_params: dict[str, Any] = _load_json_key_values(params or [], "parameter")
    conflicting_keys = set(cli_params.keys()).intersection(multi_params.keys())
    if conflicting_keys:
        app.console.print(
            "The following parameters were specified by `--param` and `--params`, the "
            f"`--param` value will be used: {conflicting_keys}"
        )
    parameters: dict[str, Any] = {**multi_params, **cli_params}

    job_vars: dict[str, Any] = _load_json_key_values(
        job_variables or [], "job variable"
    )
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
        elif start_at:
            start_time_raw = "at " + start_at
        else:
            exit_with_error("No start time specified")

        with warnings.catch_warnings():
            # PyTZ throws a warning based on dateparser usage of the library
            # See https://github.com/scrapinghub/dateparser/issues/1089
            warnings.filterwarnings("ignore", module="dateparser")

            try:
                start_time_parsed = dateparser.parse(  # type: ignore[reportUnknownMemberType]
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

        scheduled_start_time = DateTime.instance(start_time_parsed)
        human_dt_diff = " (" + format_diff(scheduled_start_time.diff(now)) + ")"

    async with get_client() as client:
        deployment = await get_deployment(client, name, deployment_id)
        flow = await client.read_flow(deployment.flow_id)

        if TYPE_CHECKING:
            assert deployment.parameter_openapi_schema is not None
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

    run_url = urls.url_for(flow_run) or "<no dashboard available>"
    datetime_local_tz = scheduled_start_time.in_tz(local_timezone())
    scheduled_display = datetime_local_tz.to_datetime_string()
    tz_name = datetime_local_tz.tzname()
    if tz_name:
        scheduled_display += " " + tz_name
    scheduled_display += human_dt_diff

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
        app.console.print(f"Watching flow run {flow_run.name!r}...")
        finished_flow_run = await wait_for_flow_run(
            flow_run.id,
            timeout=watch_timeout,
            poll_interval=watch_interval,
            log_states=True,
        )
        finished_flow_run_state = finished_flow_run.state
        if finished_flow_run_state is None:
            exit_with_error("Flow run finished in an unknown state.")
        if finished_flow_run_state.is_completed():
            exit_with_success(
                f"Flow run finished successfully in {finished_flow_run_state.name!r}."
            )
        exit_with_error(
            f"Flow run finished in state {finished_flow_run_state.name!r}.",
            code=1,
        )


@deployment_app.command()
async def delete(
    name: Optional[str] = typer.Argument(
        None, help="A deployed flow's name: <FLOW_NAME>/<DEPLOYMENT_NAME>"
    ),
    deployment_id: Optional[UUID] = typer.Option(
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
                if is_interactive() and not typer.confirm(
                    (
                        f"Are you sure you want to delete deployment with id {deployment_id!r}?"
                    ),
                    default=False,
                ):
                    exit_with_error("Deletion aborted.")
                await client.delete_deployment(deployment_id)
                exit_with_success(f"Deleted deployment '{deployment_id}'.")
            except ObjectNotFound:
                exit_with_error(f"Deployment {deployment_id!r} not found!")
        elif name is not None:
            try:
                deployment = await client.read_deployment_by_name(name)
                if is_interactive() and not typer.confirm(
                    (f"Are you sure you want to delete deployment with name {name!r}?"),
                    default=False,
                ):
                    exit_with_error("Deletion aborted.")
                await client.delete_deployment(deployment.id)
                exit_with_success(f"Deleted deployment '{name}'.")
            except ObjectNotFound:
                exit_with_error(f"Deployment {name!r} not found!")
        else:
            exit_with_error("Must provide a deployment name or id")


def _load_json_key_values(
    cli_input: list[str], display_name: str
) -> dict[str, dict[str, Any] | str | int]:
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
    parsed: dict[str, dict[str, Any] | str | int] = {}

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
