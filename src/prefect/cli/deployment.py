"""
Deployment command — native cyclopts implementation.

Manage deployments and deployment schedules.
"""

from __future__ import annotations

import json
import sys
import textwrap
import warnings
from asyncio import gather
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Annotated, Any, Optional, TypedDict
from uuid import UUID

import cyclopts
import orjson
import yaml
from rich.pretty import Pretty
from rich.table import Table

import prefect.cli._app as _cli
from prefect.cli._utilities import (
    exit_with_error,
    exit_with_success,
    load_json_key_values,
    with_cli_exception_handling,
)
from prefect.cli.flow_runs_watching import (
    watch_flow_run as watch_flow_run,  # noqa: F811
)
from prefect.client.orchestration import get_client
from prefect.client.schemas.filters import (
    DeploymentFilter,
    FlowFilter,
    FlowFilterId,
    FlowFilterName,
)
from prefect.client.schemas.objects import DeploymentSchedule
from prefect.client.schemas.responses import DeploymentResponse
from prefect.client.schemas.schedules import (
    CronSchedule,
    IntervalSchedule,
    RRuleSchedule,
)
from prefect.exceptions import (
    ObjectNotFound,
    PrefectHTTPStatusError,
)
from prefect.states import Scheduled
from prefect.types._datetime import (
    DateTime,
    create_datetime_instance,
    human_friendly_diff,
    in_local_tz,
    parse_datetime,
    to_datetime_string,
)
from prefect.utilities import urls
from prefect.utilities.collections import listrepr

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient


# -- yaml multiline string presenter --


def _str_presenter(
    dumper: yaml.Dumper | yaml.representer.SafeRepresenter, data: str
) -> yaml.ScalarNode:
    if len(data.splitlines()) > 1:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")  # type: ignore[reportUnknownMemberType]
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)  # type: ignore[reportUnknownMemberType]


yaml.add_representer(str, _str_presenter)
yaml.representer.SafeRepresenter.add_representer(str, _str_presenter)


# -- apps --

deployment_app: cyclopts.App = cyclopts.App(
    name="deployment",
    alias="deployments",
    help="Manage deployments.",
    version_flags=[],
    help_flags=["--help"],
)

schedule_app: cyclopts.App = cyclopts.App(
    name="schedule",
    help="Manage deployment schedules.",
    version_flags=[],
    help_flags=["--help"],
)
deployment_app.command(schedule_app)


# -- helpers --


def _assert_deployment_name_format(name: str) -> None:
    if "/" not in name:
        exit_with_error(
            "Invalid deployment name. Expected '<flow-name>/<deployment-name>'"
        )


async def _get_deployment(
    client: PrefectClient, name: str | None, deployment_id: str | None
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


# =============================================================================
# deployment commands
# =============================================================================


@deployment_app.command()
@with_cli_exception_handling
async def inspect(
    name: str,
    *,
    output: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--output",
            alias="-o",
            help="Specify an output format. Currently supports: json",
        ),
    ] = None,
):
    """View details about a deployment."""
    from asyncio import iscoroutine

    from prefect.blocks.core import Block

    if output and output.lower() != "json":
        exit_with_error("Only 'json' output format is supported.")

    _assert_deployment_name_format(name)

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

    if output and output.lower() == "json":
        json_output = orjson.dumps(deployment_json, option=orjson.OPT_INDENT_2).decode()
        _cli.console.print(json_output)
    else:
        _cli.console.print(Pretty(deployment_json))


@deployment_app.command()
@with_cli_exception_handling
async def ls(
    flow_name: Annotated[
        Optional[list[str]],
        cyclopts.Parameter(
            "flow_name",
            help="One or more flow names to filter deployments by.",
        ),
    ] = None,
    *,
    by_created: Annotated[
        bool,
        cyclopts.Parameter(
            "--by-created",
            help="Sort by created time instead of name.",
        ),
    ] = False,
    output: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--output",
            alias="-o",
            help="Specify an output format. Currently supports: json",
        ),
    ] = None,
):
    """View all deployments or deployments for specific flows."""
    if output and output.lower() != "json":
        exit_with_error("Only 'json' output format is supported.")

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

    if output and output.lower() == "json":
        deployments_json = [
            deployment.model_dump(mode="json") for deployment in deployments
        ]
        json_output = orjson.dumps(
            deployments_json, option=orjson.OPT_INDENT_2
        ).decode()
        _cli.console.print(json_output)
    else:
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

        _cli.console.print(table)


@deployment_app.command()
@with_cli_exception_handling
async def run(
    name: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "name",
            help="A deployed flow's name: <FLOW_NAME>/<DEPLOYMENT_NAME>",
        ),
    ] = None,
    *,
    deployment_id: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--id",
            help="A deployment id to search for if no name is given",
        ),
    ] = None,
    job_variables: Annotated[
        Optional[list[str]],
        cyclopts.Parameter(
            "--job-variable",
            help=(
                "A key, value pair (key=value) specifying a flow run job variable. The value will"
                " be interpreted as JSON. May be passed multiple times to specify multiple"
                " job variable values."
            ),
        ),
    ] = None,
    params: Annotated[
        Optional[list[str]],
        cyclopts.Parameter(
            "--param",
            alias="-p",
            help=(
                "A key, value pair (key=value) specifying a flow parameter. The value will"
                " be interpreted as JSON. May be passed multiple times to specify multiple"
                " parameter values."
            ),
        ),
    ] = None,
    multiparams: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--params",
            allow_leading_hyphen=True,
            help=(
                "A mapping of parameters to values. To use a stdin, pass '-'. Any "
                "parameters passed with `--param` will take precedence over these values."
            ),
        ),
    ] = None,
    start_in: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--start-in",
            help=(
                "A human-readable string specifying a time interval to wait before starting"
                " the flow run. E.g. 'in 5 minutes', 'in 1 hour', 'in 2 days'."
            ),
        ),
    ] = None,
    start_at: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--start-at",
            help=(
                "A human-readable string specifying a time to start the flow run. E.g."
                " 'at 5:30pm', 'at 2022-08-01 17:30', 'at 2022-08-01 17:30:00'."
            ),
        ),
    ] = None,
    tags: Annotated[
        Optional[list[str]],
        cyclopts.Parameter(
            "--tag",
            help="Tag(s) to be applied to flow run.",
        ),
    ] = None,
    watch: Annotated[
        bool,
        cyclopts.Parameter(
            "--watch",
            help="Whether to poll the flow run until a terminal state is reached.",
        ),
    ] = False,
    watch_interval: Annotated[
        Optional[int],
        cyclopts.Parameter(
            "--watch-interval",
            help="How often to poll the flow run for state changes (in seconds).",
        ),
    ] = None,
    watch_timeout: Annotated[
        Optional[int],
        cyclopts.Parameter(
            "--watch-timeout",
            help="Timeout for --watch.",
        ),
    ] = None,
    flow_run_name: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--flow-run-name",
            help="Custom name to give the flow run.",
        ),
    ] = None,
):
    """Create a flow run for the given flow and deployment.

    The flow run will be scheduled to run immediately unless `--start-in` or
    `--start-at` is specified. The flow run will not execute until a worker
    starts. To watch the flow run until it reaches a terminal state, use the
    `--watch` flag.
    """
    import dateparser

    import prefect.types._datetime

    now = prefect.types._datetime.now("UTC")

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

    cli_params: dict[str, Any] = load_json_key_values(params or [], "parameter")
    conflicting_keys = set(cli_params.keys()).intersection(multi_params.keys())
    if conflicting_keys:
        _cli.console.print(
            "The following parameters were specified by `--param` and `--params`, the "
            f"`--param` value will be used: {conflicting_keys}"
        )
    parameters: dict[str, Any] = {**multi_params, **cli_params}

    job_vars: dict[str, Any] = load_json_key_values(job_variables or [], "job variable")

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

        scheduled_start_time = create_datetime_instance(start_time_parsed)
        human_dt_diff = " (" + human_friendly_diff(scheduled_start_time) + ")"

    async with get_client() as client:
        deployment = await _get_deployment(client, name, deployment_id)
        flow = await client.read_flow(deployment.flow_id)

        if TYPE_CHECKING:
            assert deployment.parameter_openapi_schema is not None
        deployment_parameters = (
            deployment.parameter_openapi_schema.get("properties", {}).keys()
            if deployment.parameter_openapi_schema
            else []
        )
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

        templating_parameters = {**(deployment.parameters or {}), **(parameters or {})}
        if flow_run_name:
            try:
                flow_run_name = flow_run_name.format(**templating_parameters)
            except KeyError as e:
                exit_with_error(
                    f"Missing parameter for flow run name: '{e.args[0]}' is undefined"
                )
            except Exception as e:
                exit_with_error(f"Failed to format flow run name: {e}")

        _cli.console.print(
            f"Creating flow run for deployment '{flow.name}/{deployment.name}'...",
        )

        try:
            flow_run = await client.create_flow_run_from_deployment(
                deployment.id,
                parameters=parameters,
                state=Scheduled(scheduled_time=scheduled_start_time),
                tags=tags,
                job_variables=job_vars,
                name=flow_run_name,
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
    datetime_local_tz = in_local_tz(scheduled_start_time)
    scheduled_display = to_datetime_string(datetime_local_tz)
    scheduled_display += human_dt_diff

    _cli.console.print(f"Created flow run {flow_run.name!r}.")
    _cli.console.print(
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
        if watch_interval is not None:
            warnings.warn(
                "The --watch-interval flag is deprecated and will be removed in a future release. "
                "Flow run watching now uses real-time event streaming.",
                DeprecationWarning,
                stacklevel=2,
            )

        finished_flow_run = await watch_flow_run(
            flow_run.id, _cli.console, timeout=watch_timeout
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
@with_cli_exception_handling
async def delete(
    name: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "name",
            help="A deployed flow's name: <FLOW_NAME>/<DEPLOYMENT_NAME>",
        ),
    ] = None,
    *,
    deployment_id: Annotated[
        Optional[UUID],
        cyclopts.Parameter(
            "--id",
            help="A deployment id to search for if no name is given",
        ),
    ] = None,
    _all: Annotated[
        bool,
        cyclopts.Parameter(
            "--all",
            help="Delete all deployments",
        ),
    ] = False,
):
    """Delete a deployment."""
    from prefect.cli._prompts import confirm

    async with get_client() as client:
        if _all:
            if name is not None or deployment_id is not None:
                exit_with_error(
                    "Cannot provide a deployment name or id when deleting all deployments."
                )
            deployments = await client.read_deployments()
            if len(deployments) == 0:
                exit_with_success("No deployments found.")
            if _cli.is_interactive() and not confirm(
                f"Are you sure you want to delete all {len(deployments)} deployments?",
                default=False,
            ):
                exit_with_error("Deletion aborted.")
            for deployment in deployments:
                await client.delete_deployment(deployment.id)
            plural = "" if len(deployments) == 1 else "s"
            exit_with_success(f"Deleted {len(deployments)} deployment{plural}.")

        if name is None and deployment_id is not None:
            try:
                if _cli.is_interactive() and not confirm(
                    f"Are you sure you want to delete deployment with id {deployment_id!r}?",
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
                if _cli.is_interactive() and not confirm(
                    f"Are you sure you want to delete deployment with name {name!r}?",
                    default=False,
                ):
                    exit_with_error("Deletion aborted.")
                await client.delete_deployment(deployment.id)
                exit_with_success(f"Deleted deployment '{name}'.")
            except ObjectNotFound:
                exit_with_error(f"Deployment {name!r} not found!")
        else:
            exit_with_error("Must provide a deployment name or id")


# =============================================================================
# schedule commands
# =============================================================================


@schedule_app.command(name="create")
@with_cli_exception_handling
async def create_schedule(
    name: str,
    *,
    interval: Annotated[
        Optional[float],
        cyclopts.Parameter(
            "--interval",
            help="An interval to schedule on, specified in seconds",
        ),
    ] = None,
    interval_anchor: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--anchor-date",
            help="The anchor date for an interval schedule",
        ),
    ] = None,
    rrule_string: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--rrule",
            help="Deployment schedule rrule string",
        ),
    ] = None,
    cron_string: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--cron",
            help="Deployment schedule cron string",
        ),
    ] = None,
    cron_day_or: Annotated[
        bool,
        cyclopts.Parameter(
            "--day_or",
            help="Control how croniter handles `day` and `day_of_week` entries",
        ),
    ] = True,
    timezone: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--timezone",
            help="Deployment schedule timezone string e.g. 'America/New_York'",
        ),
    ] = None,
    active: Annotated[
        bool,
        cyclopts.Parameter(
            "--active",
            help="Whether the schedule is active. Defaults to True.",
        ),
    ] = True,
    replace: Annotated[
        bool,
        cyclopts.Parameter(
            "--replace",
            help="Replace the deployment's current schedule(s) with this new schedule.",
        ),
    ] = False,
    assume_yes: Annotated[
        bool,
        cyclopts.Parameter(
            "--accept-yes",
            alias="-y",
            help="Accept the confirmation prompt without prompting",
        ),
    ] = False,
):
    """Create a schedule for a given deployment."""
    from prefect.cli._prompts import confirm

    _assert_deployment_name_format(name)

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
                parsed_interval_anchor = parse_datetime(interval_anchor)
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
            interval_schedule["anchor_date"] = parsed_interval_anchor
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
            if not assume_yes and not confirm(
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


@schedule_app.command(name="delete")
@with_cli_exception_handling
async def delete_schedule(
    deployment_name: str,
    schedule_id: UUID,
    *,
    assume_yes: Annotated[
        bool,
        cyclopts.Parameter(
            "--accept-yes",
            alias="-y",
            help="Accept the confirmation prompt without prompting",
        ),
    ] = False,
):
    """Delete a deployment schedule."""
    from prefect.cli._prompts import confirm

    _assert_deployment_name_format(deployment_name)

    async with get_client() as client:
        try:
            deployment = await client.read_deployment_by_name(deployment_name)
        except ObjectNotFound:
            return exit_with_error(f"Deployment {deployment_name} not found!")

        try:
            schedule = [s for s in deployment.schedules if s.id == schedule_id][0]
        except IndexError:
            return exit_with_error("Deployment schedule not found!")

        if not assume_yes and not confirm(
            f"Are you sure you want to delete this schedule: {schedule.schedule}",
        ):
            return exit_with_error("Deletion cancelled.")

        try:
            await client.delete_deployment_schedule(deployment.id, schedule_id)
        except ObjectNotFound:
            exit_with_error("Deployment schedule not found!")

        exit_with_success(f"Deleted deployment schedule {schedule_id}")


async def _set_schedule_activation(
    deployment_name: Optional[str],
    schedule_id: Optional[UUID],
    _all: bool,
    activate: bool,
) -> None:
    """Enable or disable deployment schedules for one or all deployments."""
    from prefect.cli._prompts import confirm

    past_tense = "resumed" if activate else "paused"
    present_tense = "resume" if activate else "pause"

    if _all and (deployment_name is not None or schedule_id is not None):
        return exit_with_error(
            "Cannot specify deployment name or schedule ID with --all"
        )
    if not _all and (deployment_name is None or schedule_id is None):
        return exit_with_error(
            "Must provide deployment name and schedule ID, or use --all"
        )

    if _all:
        async with get_client() as client:
            deployments: list[DeploymentResponse] = []
            page_limit = 200
            offset = 0
            while True:
                page = await client.read_deployments(
                    deployment_filter=DeploymentFilter(),
                    limit=page_limit,
                    offset=offset,
                )
                if not page:
                    break
                deployments.extend(page)
                if len(page) < page_limit:
                    break
                offset += page_limit

            if not deployments:
                return exit_with_success("No deployments found.")

            schedules_to_update = sum(
                1 for d in deployments for s in d.schedules if s.active != activate
            )

            if schedules_to_update == 0:
                state_msg = "inactive" if activate else "active"
                return exit_with_success(
                    f"No {state_msg} schedules found to {present_tense}."
                )

            if _cli.is_interactive() and not confirm(
                f"Are you sure you want to {present_tense} {schedules_to_update} schedule(s) across all deployments?",
                default=False,
            ):
                return exit_with_error("Operation cancelled.")

            update_tasks = []
            deployment_names = []
            for deployment in deployments:
                if deployment.schedules:
                    for schedule in deployment.schedules:
                        if schedule.active != activate:
                            update_tasks.append((deployment.id, schedule.id))
                            deployment_names.append(deployment.name)

            if update_tasks:
                import asyncio

                semaphore = asyncio.Semaphore(10)

                async def limited_update(dep_id: UUID, sched_id: UUID):
                    async with semaphore:
                        await client.update_deployment_schedule(
                            dep_id, sched_id, active=activate
                        )

                await gather(*[limited_update(did, sid) for did, sid in update_tasks])

                for dep_name in deployment_names:
                    _cli.console.print(
                        f"{past_tense.capitalize()} schedule for deployment [cyan]{dep_name}[/cyan]"
                    )

            exit_with_success(
                f"{past_tense.capitalize()} {len(update_tasks)} deployment schedule(s)."
            )

    else:
        _assert_deployment_name_format(deployment_name)

        async with get_client() as client:
            try:
                deployment = await client.read_deployment_by_name(deployment_name)
            except ObjectNotFound:
                return exit_with_error(f"Deployment {deployment_name!r} not found!")

            schedule = next(
                (s for s in deployment.schedules if s.id == schedule_id), None
            )
            if schedule is None:
                return exit_with_error("Deployment schedule not found!")

            if schedule.active == activate:
                state = "active" if activate else "inactive"
                return exit_with_error(
                    f"Deployment schedule {schedule_id} is already {state}"
                )

            await client.update_deployment_schedule(
                deployment.id, schedule_id, active=activate
            )
            exit_with_success(
                f"{past_tense.capitalize()} schedule {schedule.schedule} for deployment {deployment_name}"
            )


@schedule_app.command(name="pause")
@with_cli_exception_handling
async def pause_schedule(
    deployment_name: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "deployment_name",
        ),
    ] = None,
    schedule_id: Annotated[
        Optional[UUID],
        cyclopts.Parameter(
            "schedule_id",
        ),
    ] = None,
    *,
    _all: Annotated[
        bool,
        cyclopts.Parameter(
            "--all",
            help="Pause all deployment schedules",
        ),
    ] = False,
):
    """Pause deployment schedules."""
    await _set_schedule_activation(deployment_name, schedule_id, _all, activate=False)


@schedule_app.command(name="resume")
@with_cli_exception_handling
async def resume_schedule(
    deployment_name: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "deployment_name",
        ),
    ] = None,
    schedule_id: Annotated[
        Optional[UUID],
        cyclopts.Parameter(
            "schedule_id",
        ),
    ] = None,
    *,
    _all: Annotated[
        bool,
        cyclopts.Parameter(
            "--all",
            help="Resume all deployment schedules",
        ),
    ] = False,
):
    """Resume deployment schedules."""
    await _set_schedule_activation(deployment_name, schedule_id, _all, activate=True)


@schedule_app.command(name="ls")
@with_cli_exception_handling
async def list_schedules(
    deployment_name: str,
    *,
    output: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--output",
            alias="-o",
            help="Specify an output format. Currently supports: json",
        ),
    ] = None,
):
    """View all schedules for a deployment."""
    import prefect.types._datetime

    _assert_deployment_name_format(deployment_name)
    async with get_client() as client:
        try:
            deployment = await client.read_deployment_by_name(deployment_name)
        except ObjectNotFound:
            return exit_with_error(f"Deployment {deployment_name!r} not found!")

    if output and output.lower() != "json":
        exit_with_error("Only 'json' output format is supported.")

    def sort_by_created_key(schedule: DeploymentSchedule):  # type: ignore
        assert schedule.created is not None, "All schedules should have a created time."
        return prefect.types._datetime.now("UTC") - schedule.created

    def schedule_details(schedule: DeploymentSchedule) -> str:
        if isinstance(schedule.schedule, IntervalSchedule):
            return f"interval: {schedule.schedule.interval}s"
        elif isinstance(schedule.schedule, CronSchedule):
            return f"cron: {schedule.schedule.cron}"
        elif isinstance(schedule.schedule, RRuleSchedule):
            return f"rrule: {schedule.schedule.rrule}"
        else:
            return "unknown"

    if output and output.lower() == "json":
        schedules_json = [
            {
                **schedule.model_dump(mode="json"),
                "schedule": schedule_details(schedule),
            }
            for schedule in deployment.schedules
        ]
        json_output = orjson.dumps(schedules_json, option=orjson.OPT_INDENT_2).decode()
        _cli.console.print(json_output)
    else:
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

        _cli.console.print(table)


@schedule_app.command(name="clear")
@with_cli_exception_handling
async def clear_schedules(
    deployment_name: str,
    *,
    assume_yes: Annotated[
        bool,
        cyclopts.Parameter(
            "--accept-yes",
            alias="-y",
            help="Accept the confirmation prompt without prompting",
        ),
    ] = False,
):
    """Clear all schedules for a deployment."""
    from prefect.cli._prompts import confirm

    _assert_deployment_name_format(deployment_name)
    async with get_client() as client:
        try:
            deployment = await client.read_deployment_by_name(deployment_name)
        except ObjectNotFound:
            return exit_with_error(f"Deployment {deployment_name!r} not found!")

        await client.read_flow(deployment.flow_id)

        if not assume_yes and not confirm(
            "Are you sure you want to clear all schedules for this deployment?",
        ):
            exit_with_error("Clearing schedules cancelled.")

        for schedule in deployment.schedules:
            try:
                await client.delete_deployment_schedule(deployment.id, schedule.id)
            except ObjectNotFound:
                pass

        exit_with_success(f"Cleared all schedules for deployment {deployment_name}")
