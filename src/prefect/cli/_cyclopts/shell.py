"""
Shell command — native cyclopts implementation.

Run shell commands as Prefect flows.
"""

from typing import Annotated, Optional

import cyclopts

import prefect.cli._cyclopts as _cli
from prefect.cli._cyclopts._utilities import (
    exit_with_error,
    with_cli_exception_handling,
)

shell_app = cyclopts.App(
    name="shell", help="Serve and watch shell commands as Prefect flows."
)


@shell_app.command(name="watch")
@with_cli_exception_handling
async def watch(
    command: str,
    *,
    log_output: Annotated[
        bool,
        cyclopts.Parameter(
            "--log-output", negative="--no-log-output", help="Log output to Prefect."
        ),
    ] = True,
    flow_run_name: Annotated[
        Optional[str],
        cyclopts.Parameter("--flow-run-name", help="Name of the flow run."),
    ] = None,
    flow_name: Annotated[
        str,
        cyclopts.Parameter("--flow-name", help="Name of the flow."),
    ] = "Shell Command",
    stream_stdout: Annotated[
        bool,
        cyclopts.Parameter(
            "--stream-stdout", negative="--no-stream-stdout", help="Stream output."
        ),
    ] = True,
    tag: Annotated[
        Optional[list[str]],
        cyclopts.Parameter("--tag", help="Tags for the flow run (repeatable)."),
    ] = None,
):
    """
    Execute a shell command and observe it as a Prefect flow.
    """
    from prefect.cli.shell import run_shell_process
    from prefect.context import tags

    tag = (tag or []) + ["shell"]

    defined_flow = run_shell_process.with_options(
        name=flow_name, flow_run_name=flow_run_name
    )
    with tags(*tag):
        defined_flow(
            command=command, log_output=log_output, stream_stdout=stream_stdout
        )


@shell_app.command(name="serve")
@with_cli_exception_handling
async def serve(
    command: str,
    *,
    flow_name: Annotated[
        str,
        cyclopts.Parameter("--flow-name", help="Name of the flow."),
    ],
    deployment_name: Annotated[
        str,
        cyclopts.Parameter("--deployment-name", help="Name of the deployment."),
    ] = "CLI Runner Deployment",
    deployment_tags: Annotated[
        Optional[list[str]],
        cyclopts.Parameter("--tag", help="Deployment tags (repeatable)."),
    ] = None,
    log_output: Annotated[
        bool,
        cyclopts.Parameter("--log-output", help="Log command output.", show=False),
    ] = True,
    stream_stdout: Annotated[
        bool,
        cyclopts.Parameter(
            "--stream-stdout", negative="--no-stream-stdout", help="Stream output."
        ),
    ] = True,
    cron_schedule: Annotated[
        Optional[str],
        cyclopts.Parameter("--cron-schedule", help="Cron schedule."),
    ] = None,
    timezone: Annotated[
        Optional[str],
        cyclopts.Parameter("--timezone", help="Timezone for the schedule."),
    ] = None,
    concurrency_limit: Annotated[
        Optional[int],
        cyclopts.Parameter("--concurrency-limit", help="Max concurrent flow runs."),
    ] = None,
    run_once: Annotated[
        bool,
        cyclopts.Parameter("--run-once", help="Run once instead of forever."),
    ] = False,
):
    """
    Create and serve a deployment that runs a shell command.
    """
    if concurrency_limit is not None and concurrency_limit < 1:
        exit_with_error("--concurrency-limit must be >= 1.")

    from prefect.cli.shell import run_shell_process
    from prefect.client.schemas.actions import DeploymentScheduleCreate
    from prefect.client.schemas.schedules import CronSchedule
    from prefect.runner import Runner
    from prefect.settings import get_current_settings
    from prefect.types.entrypoint import EntrypointType

    schedule = (
        CronSchedule(cron=cron_schedule, timezone=timezone) if cron_schedule else None
    )
    defined_flow = run_shell_process.with_options(name=flow_name)

    runner_deployment = await defined_flow.to_deployment(
        name=deployment_name,
        parameters={
            "command": command,
            "log_output": log_output,
            "stream_stdout": stream_stdout,
        },
        entrypoint_type=EntrypointType.MODULE_PATH,
        schedules=[DeploymentScheduleCreate(schedule=schedule)] if schedule else [],
        tags=(deployment_tags or []) + ["shell"],
    )

    runner = Runner(name=flow_name)
    deployment_id = await runner.add_deployment(runner_deployment)
    help_message = (
        f"[green]Your flow {runner_deployment.flow_name!r} is being served and polling"
        " for scheduled runs!\n[/]\nTo trigger a run for this flow, use the following"
        " command:\n[blue]\n\t$ prefect deployment run"
        f" '{runner_deployment.flow_name}/{deployment_name}'\n[/]"
    )
    if ui_url := get_current_settings().ui_url:
        help_message += (
            "\nYou can also run your flow via the Prefect UI:"
            f" [blue]{ui_url}/deployments/deployment/{deployment_id}[/]\n"
        )

    _cli.console.print(help_message, soft_wrap=True)
    await runner.start(run_once=run_once)
