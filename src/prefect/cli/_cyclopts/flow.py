"""
Flow command — native cyclopts implementation.

View and serve flows.
"""

from typing import Annotated, Optional

import cyclopts
from rich.table import Table

from prefect.cli._cyclopts._utilities import (
    exit_with_error,
    run_async,
    with_cli_exception_handling,
)

flow_app = cyclopts.App(name="flow", help="View and serve flows.")


def _get_console():
    from prefect.cli._cyclopts import console

    return console


@flow_app.command()
@with_cli_exception_handling
@run_async
async def ls(
    *,
    limit: Annotated[
        int,
        cyclopts.Parameter("--limit", help="Maximum number of flows to show."),
    ] = 15,
):
    """View flows."""
    from prefect.client.orchestration import get_client
    from prefect.client.schemas.sorting import FlowSort

    async with get_client() as client:
        flows = await client.read_flows(limit=limit, sort=FlowSort.CREATED_DESC)

    table = Table(title="Flows")
    table.add_column("ID", justify="right", style="cyan", no_wrap=True)
    table.add_column("Name", style="green", no_wrap=True)
    table.add_column("Created", no_wrap=True)

    for flow in flows:
        table.add_row(str(flow.id), str(flow.name), str(flow.created))

    _get_console().print(table)


@flow_app.command()
@with_cli_exception_handling
@run_async
async def serve(
    entrypoint: Annotated[
        str,
        cyclopts.Parameter(
            help="Path to flow file in format ./path/to/file.py:flow_func_name."
        ),
    ],
    *,
    name: Annotated[
        str,
        cyclopts.Parameter("--name", alias="-n", help="Deployment name."),
    ],
    description: Annotated[
        Optional[str],
        cyclopts.Parameter("--description", alias="-d", help="Deployment description."),
    ] = None,
    version: Annotated[
        Optional[str],
        cyclopts.Parameter("--version", alias="-v", help="Deployment version."),
    ] = None,
    tags: Annotated[
        Optional[list[str]],
        cyclopts.Parameter("--tag", alias="-t", help="Tags (repeatable)."),
    ] = None,
    cron: Annotated[
        Optional[str],
        cyclopts.Parameter("--cron", help="Cron schedule string."),
    ] = None,
    interval: Annotated[
        Optional[int],
        cyclopts.Parameter("--interval", help="Interval in seconds."),
    ] = None,
    interval_anchor: Annotated[
        Optional[str],
        cyclopts.Parameter("--anchor-date", help="Start date for interval."),
    ] = None,
    rrule: Annotated[
        Optional[str],
        cyclopts.Parameter("--rrule", help="RRule schedule string."),
    ] = None,
    timezone: Annotated[
        Optional[str],
        cyclopts.Parameter("--timezone", help="Schedule timezone."),
    ] = None,
    pause_on_shutdown: Annotated[
        bool,
        cyclopts.Parameter(
            "--pause-on-shutdown",
            negative="--no-pause-on-shutdown",
            help="Pause schedule when serve stops.",
        ),
    ] = True,
    limit: Annotated[
        Optional[int],
        cyclopts.Parameter("--limit", help="Max concurrent runs for this flow."),
    ] = None,
    global_limit: Annotated[
        Optional[int],
        cyclopts.Parameter(
            "--global-limit", help="Max concurrent runs across all instances."
        ),
    ] = None,
):
    """Serve a flow via an entrypoint."""
    from prefect.client.schemas.actions import DeploymentScheduleCreate
    from prefect.client.schemas.schedules import construct_schedule
    from prefect.deployments.runner import RunnerDeployment
    from prefect.exceptions import MissingFlowError
    from prefect.runner import Runner
    from prefect.utilities import urls

    console = _get_console()

    runner = Runner(name=name, pause_on_shutdown=pause_on_shutdown, limit=limit)
    try:
        schedules = []
        if interval or cron or rrule:
            schedule = construct_schedule(
                interval=interval,
                cron=cron,
                rrule=rrule,
                timezone=timezone,
                anchor_date=interval_anchor,
            )
            schedules = [DeploymentScheduleCreate(schedule=schedule, active=True)]

        runner_deployment = RunnerDeployment.from_entrypoint(
            entrypoint=entrypoint,
            name=name,
            schedules=schedules,
            description=description,
            tags=tags or [],
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

    console.print(help_message, soft_wrap=True)
    await runner.start()
