"""
Flow command — native cyclopts implementation.

View and serve flows.
"""

from typing import Annotated, Optional

import cyclopts
from rich.table import Table

import prefect.cli._app as _cli
from prefect.cli._utilities import (
    exit_with_error,
    with_cli_exception_handling,
)
from prefect.client.orchestration import get_client
from prefect.client.schemas.actions import DeploymentScheduleCreate
from prefect.client.schemas.schedules import construct_schedule
from prefect.client.schemas.sorting import FlowSort
from prefect.deployments.runner import RunnerDeployment
from prefect.exceptions import MissingFlowError
from prefect.runner import Runner
from prefect.utilities import urls

flow_app: cyclopts.App = cyclopts.App(
    name="flow",
    alias="flows",
    help="View and serve flows.",
    version_flags=[],
    help_flags=["--help"],
)


@flow_app.command()
@with_cli_exception_handling
async def ls(
    *,
    limit: Annotated[
        int,
        cyclopts.Parameter("--limit", help="Maximum number of flows to list."),
    ] = 15,
):
    """View flows."""
    async with get_client() as client:
        flows = await client.read_flows(
            limit=limit,
            sort=FlowSort.CREATED_DESC,
        )

    table = Table(title="Flows")
    table.add_column("ID", justify="right", style="cyan", no_wrap=True)
    table.add_column("Name", style="green", no_wrap=True)
    table.add_column("Created", no_wrap=True)

    for flow in flows:
        table.add_row(
            str(flow.id),
            str(flow.name),
            str(flow.created),
        )

    _cli.console.print(table)


@flow_app.command()
@with_cli_exception_handling
async def serve(
    entrypoint: str,
    *,
    name: Annotated[
        str,
        cyclopts.Parameter(
            "--name",
            alias="-n",
            help="The name to give the deployment created for the flow.",
        ),
    ],
    description: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--description",
            alias="-d",
            help=(
                "The description to give the created deployment. If not provided, the"
                " description will be populated from the flow's description."
            ),
        ),
    ] = None,
    version: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--version", alias="-v", help="A version to give the created deployment."
        ),
    ] = None,
    tag: Annotated[
        Optional[list[str]],
        cyclopts.Parameter(
            "--tag",
            alias="-t",
            help="One or more optional tags to apply to the created deployment.",
        ),
    ] = None,
    cron: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--cron",
            help=(
                "A cron string that will be used to set a schedule for the created"
                " deployment."
            ),
        ),
    ] = None,
    interval: Annotated[
        Optional[int],
        cyclopts.Parameter(
            "--interval",
            help=(
                "An integer specifying an interval (in seconds) between scheduled runs"
                " of the flow."
            ),
        ),
    ] = None,
    anchor_date: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--anchor-date", help="The start date for an interval schedule."
        ),
    ] = None,
    rrule: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--rrule",
            help="An RRule that will be used to set a schedule for the created deployment.",
        ),
    ] = None,
    timezone: Annotated[
        Optional[str],
        cyclopts.Parameter(
            "--timezone",
            help="Timezone to used scheduling flow runs e.g. 'America/New_York'",
        ),
    ] = None,
    pause_on_shutdown: Annotated[
        bool,
        cyclopts.Parameter(
            "--pause-on-shutdown",
            help=(
                "If set, provided schedule will be paused when the serve command is"
                " stopped. If not set, the schedules will continue running."
            ),
        ),
    ] = True,
    limit: Annotated[
        Optional[int],
        cyclopts.Parameter(
            "--limit",
            help=(
                "The maximum number of runs that can be executed concurrently by the"
                " created runner; only applies to this served flow."
                " To apply a limit across multiple served flows, use global_limit."
            ),
        ),
    ] = None,
    global_limit: Annotated[
        Optional[int],
        cyclopts.Parameter(
            "--global-limit",
            help=(
                "The maximum number of concurrent runs allowed across all served"
                " flow instances associated with the same deployment."
            ),
        ),
    ] = None,
):
    """Serve a flow via an entrypoint."""
    runner = Runner(
        name=name,
        pause_on_shutdown=pause_on_shutdown,
        limit=limit,
    )
    try:
        schedules = []
        if interval or cron or rrule:
            schedule = construct_schedule(
                interval=interval,
                cron=cron,
                rrule=rrule,
                timezone=timezone,
                anchor_date=anchor_date,
            )
            schedules = [DeploymentScheduleCreate(schedule=schedule, active=True)]

        runner_deployment = RunnerDeployment.from_entrypoint(
            entrypoint=entrypoint,
            name=name,
            schedules=schedules,
            description=description,
            tags=tag or [],
            version=version,
            concurrency_limit=global_limit,
        )
    except (MissingFlowError, ValueError) as exc:
        exit_with_error(str(exc))

    deployment_id = await runner.add_deployment(runner_deployment)

    help_message = (
        f"[green]Your flow {runner_deployment.flow_name!r} is being served and polling"
        " for scheduled runs!\n[/]\nTo trigger a run for this flow, use the following"
        " command:\n[blue]\n\t$ prefect deployment run"
        f" '{runner_deployment.flow_name}/{name}'\n[/]"
    )

    deployment_url = urls.url_for("deployment", obj_id=deployment_id)
    if deployment_url:
        help_message += (
            "\nYou can also run your flow via the Prefect UI:"
            f" [blue]{deployment_url}[/]\n"
        )

    _cli.console.print(help_message, soft_wrap=True)
    await runner.start()
