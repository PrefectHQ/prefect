"""Tasks for interacting with shell commands"""

import io
import logging
import shlex
from typing import List

import typer
from pydantic import VERSION as PYDANTIC_VERSION

from prefect import flow
from prefect.cli._types import PrefectTyper
from prefect.cli.root import app
from prefect.client.schemas.schedules import CronSchedule
from prefect.context import tags
from prefect.deployments.runner import EntrypointType
from prefect.logging.loggers import get_run_logger
from prefect.runner import Runner
from prefect.settings import PREFECT_UI_URL
from prefect.utilities.processutils import run_process

if PYDANTIC_VERSION.startswith("2."):
    pass
else:
    pass

shell_app = PrefectTyper(name="shell", help="Commands for working with shell commands.")
app.add_typer(shell_app)


@flow
async def run_shell_process(command: str, log_output: bool = True):
    """
    Run a shell process with the given command.

    Args:
        command (str): The shell command to execute.
        log_output (bool, optional): Whether to log the output of the process. Defaults to True.
    """
    # Explicitly configure logging
    logger = get_run_logger() if log_output else logging.getLogger("prefect")

    command_list = shlex.split(command)
    err_stream = io.StringIO()
    out_stream = io.StringIO()

    process = await run_process(command_list, stream_output=(out_stream, err_stream))

    if process.returncode != 0:
        err_stream.seek(0)
        logger.error(err_stream.read())
    else:
        out_stream.seek(0)
        logger.info(out_stream.read())


@shell_app.command("watch")
async def watch(
    command: str,
    log_output: bool = typer.Option(
        True, help="Log the output of the command to Prefect"
    ),
    flows_run_name: str = typer.Option(None, help="Name of the flow"),
    flow_name: str = typer.Option(None, help="Name of the flow"),
    flow_run_tags: List[str] = typer.Option(None, "--tag", help="Tags for the flow"),
):
    """
    Executes a shell command asynchronously.

    Args:
        command (str): The shell command to execute.
        log_output (bool, optional): Whether to log the output of the command to Prefect. Defaults to True.
    """

    # Call the shell_run_command flow with provided arguments
    with tags(*flow_run_tags.append("shell") if flow_run_tags else "shell"):
        await run_shell_process(command=command, log_output=log_output)


@shell_app.command("serve")
async def serve(
    command: str,
    name: str = typer.Option(..., help="Name of the flow"),
    tags: List[str] = typer.Option(None, "--tag", help="Tags for the flow"),
    log_output: bool = typer.Option(
        True, help="Stream the output of the command", hidden=True
    ),
    cron_schedule: str = typer.Option(None, help="Cron schedule for the flow"),
    timezone: str = typer.Option(None, help="Timezone for the schedule"),
    concurrency_limit: int = typer.Option(
        None,
        help="The maximum number of flow runs that can execute at the same time",
    ),
    deployment_name: str = typer.Option(
        "CLI Runner Deployment", help="Name of the deployment"
    ),
    run_once: bool = typer.Option(
        False, help="Run the agent loop once, instead of forever."
    ),
):
    """
    Serves a Prefect flow by running it in a shell process.

    Args:
        command (str): The command to be executed in the shell process.
        name (str, optional): Name of the flow. Defaults to typer.Option(..., help="Name of the flow").
        cron_schedule (str, optional): Cron schedule for the flow. Defaults to typer.Option(None, help="Cron schedule for the flow").
        log_output (bool, optional): Stream the output of the command. Defaults to typer.Option(True, help="Stream the output of the command", hidden=True).
        timezone (str, optional): Timezone for the schedule. Defaults to typer.Option(None, help="Timezone for the schedule").
        concurrency_limit (int, optional): The maximum number of flow runs that can execute at the same time. Defaults to typer.Option(None, help="The maximum number of flow runs that can execute at the same time").
        deployment_name (str, optional): Name of the deployment. Defaults to typer.Option("CLI Runner Deployment", help="Name of the deployment").
    """
    schedule = CronSchedule(cron=cron_schedule) if cron_schedule else None
    run_shell_process.name = name

    runner_deployment = await run_shell_process.to_deployment(
        name=deployment_name,
        parameters={"command": command, "log_output": log_output},
        entrypoint_type=EntrypointType.MODULE_PATH,
        schedule=schedule,
        tags=tags.append("shell") if tags else ["shell"],
    )

    runner = Runner(name=name)
    deployment_id = await runner.add_deployment(runner_deployment)
    help_message = (
        f"[green]Your flow {runner_deployment.flow_name!r} is being served and polling"
        " for scheduled runs!\n[/]\nTo trigger a run for this flow, use the following"
        " command:\n[blue]\n\t$ prefect deployment run"
        f" '{runner_deployment.flow_name}/{deployment_name}'\n[/]"
    )
    if PREFECT_UI_URL:
        help_message += (
            "\nYou can also run your flow via the Prefect UI:"
            f" [blue]{PREFECT_UI_URL.value()}/deployments/deployment/{deployment_id}[/]\n"
        )

    app.console.print(help_message, soft_wrap=True)
    await runner.start(run_once=run_once)
