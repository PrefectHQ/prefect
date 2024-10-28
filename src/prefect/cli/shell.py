"""
Provides a set of tools for executing shell commands as Prefect flows.
Includes functionalities for running shell commands ad-hoc or serving them as Prefect flows,
with options for logging output, scheduling, and deployment customization.
"""

import logging
import subprocess
import sys
import threading
from typing import Any, Dict, List, Optional

import typer
from typing_extensions import Annotated

from prefect import flow
from prefect.cli._types import PrefectTyper
from prefect.cli.root import app
from prefect.client.schemas.actions import DeploymentScheduleCreate
from prefect.client.schemas.schedules import CronSchedule
from prefect.context import tags
from prefect.exceptions import FailedRun
from prefect.logging.loggers import get_run_logger
from prefect.runner import Runner
from prefect.settings import PREFECT_UI_URL
from prefect.types.entrypoint import EntrypointType

shell_app = PrefectTyper(
    name="shell", help="Serve and watch shell commands as Prefect flows."
)
app.add_typer(shell_app)


def output_stream(pipe, logger_function):
    """
    Read from a pipe line by line and log using the provided logging function.

    Args:
        pipe (IO): A file-like object for reading process output.
        logger_function (function): A logging function from the logger.
    """
    with pipe:
        for line in iter(pipe.readline, ""):
            logger_function(line.strip())


def output_collect(pipe, container):
    """
    Collects output from a subprocess pipe and stores it in a container list.

    Args:
        pipe: The output pipe of the subprocess, either stdout or stderr.
        container: A list to store the collected output lines.
    """
    for line in iter(pipe.readline, ""):
        container.append(line)


@flow
def run_shell_process(
    command: str,
    log_output: bool = True,
    stream_stdout: bool = False,
    log_stderr: bool = False,
    popen_kwargs: Optional[Dict[str, Any]] = None,
):
    """
    Asynchronously executes the specified shell command and logs its output.

    This function is designed to be used within Prefect flows to run shell commands as part of task execution.
    It handles both the execution of the command and the collection of its output for logging purposes.

    Args:
        command: The shell command to execute.
        log_output: If True, the output of the command (both stdout and stderr) is logged to Prefect.
        stream_stdout: If True, the stdout of the command is streamed to Prefect logs.
        log_stderr: If True, the stderr of the command is logged to Prefect logs.
        popen_kwargs: Additional keyword arguments to pass to the `subprocess.Popen` call.

    """

    logger = get_run_logger() if log_output else logging.getLogger("prefect")

    # Default Popen kwargs that can be overridden
    kwargs = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "shell": True,
        "text": True,
        "bufsize": 1,
        "universal_newlines": True,
    }

    if popen_kwargs:
        kwargs |= popen_kwargs

    # Containers for log batching
    stdout_container, stderr_container = [], []
    with subprocess.Popen(command, **kwargs) as proc:
        # Create threads for collecting stdout and stderr
        if stream_stdout:
            stdout_logger = logger.info
            output = output_stream
        else:
            stdout_logger = stdout_container
            output = output_collect

        stdout_thread = threading.Thread(
            target=output, args=(proc.stdout, stdout_logger)
        )

        stderr_thread = threading.Thread(
            target=output_collect, args=(proc.stderr, stderr_container)
        )

        stdout_thread.start()
        stderr_thread.start()

        stdout_thread.join()
        stderr_thread.join()

        proc.wait()
        if stdout_container:
            logger.info("".join(stdout_container).strip())

        if stderr_container and log_stderr:
            logger.error("".join(stderr_container).strip())
            # Suppress traceback
        if proc.returncode != 0:
            logger.error("".join(stderr_container).strip())
            sys.tracebacklimit = 0
            raise FailedRun(f"Command failed with exit code {proc.returncode}")


@shell_app.command("watch")
async def watch(
    command: str,
    log_output: bool = typer.Option(
        True, help="Log the output of the command to Prefect logs."
    ),
    flow_run_name: str = typer.Option(None, help="Name of the flow run."),
    flow_name: str = typer.Option("Shell Command", help="Name of the flow."),
    stream_stdout: bool = typer.Option(True, help="Stream the output of the command."),
    tag: Annotated[
        Optional[List[str]], typer.Option(help="Optional tags for the flow run.")
    ] = None,
):
    """
    Executes a shell command and observes it as Prefect flow.

    Args:
        command (str): The shell command to be executed.
        log_output (bool, optional): If True, logs the command's output. Defaults to True.
        flow_run_name (str, optional): An optional name for the flow run.
        flow_name (str, optional): An optional name for the flow. Useful for identification in the Prefect UI.
        tag (List[str], optional): An optional list of tags for categorizing and filtering flows in the Prefect UI.
    """
    tag = (tag or []) + ["shell"]

    # Call the shell_run_command flow with provided arguments
    defined_flow = run_shell_process.with_options(
        name=flow_name, flow_run_name=flow_run_name
    )
    with tags(*tag):
        defined_flow(
            command=command, log_output=log_output, stream_stdout=stream_stdout
        )


@shell_app.command("serve")
async def serve(
    command: str,
    flow_name: str = typer.Option(..., help="Name of the flow"),
    deployment_name: str = typer.Option(
        "CLI Runner Deployment", help="Name of the deployment"
    ),
    deployment_tags: List[str] = typer.Option(
        None, "--tag", help="Tag for the deployment (can be provided multiple times)"
    ),
    log_output: bool = typer.Option(
        True, help="Stream the output of the command", hidden=True
    ),
    stream_stdout: bool = typer.Option(True, help="Stream the output of the command"),
    cron_schedule: str = typer.Option(None, help="Cron schedule for the flow"),
    timezone: str = typer.Option(None, help="Timezone for the schedule"),
    concurrency_limit: int = typer.Option(
        None,
        min=1,
        help="The maximum number of flow runs that can execute at the same time",
    ),
    run_once: bool = typer.Option(
        False, help="Run the agent loop once, instead of forever."
    ),
):
    """
    Creates and serves a Prefect deployment that runs a specified shell command according to a cron schedule or ad hoc.

    This function allows users to integrate shell command execution into Prefect workflows seamlessly. It provides options for
    scheduled execution via cron expressions, flow and deployment naming for better management, and the application of tags for
    easier categorization and filtering within the Prefect UI. Additionally, it supports streaming command output to Prefect logs,
    setting concurrency limits to control flow execution, and optionally running the deployment once for ad-hoc tasks.

    Args:
        command (str): The shell command the flow will execute.
        name (str): The name assigned to the flow. This is required..
        deployment_tags (List[str], optional): Optional tags for the deployment to facilitate filtering and organization.
        log_output (bool, optional): If True, streams the output of the shell command to the Prefect logs. Defaults to True.
        cron_schedule (str, optional): A cron expression that defines when the flow will run. If not provided, the flow can be triggered manually.
        timezone (str, optional): The timezone for the cron schedule. This is important if the schedule should align with local time.
        concurrency_limit (int, optional): The maximum number of instances of the flow that can run simultaneously.
        deployment_name (str, optional): The name of the deployment. This helps distinguish deployments within the Prefect platform.
        run_once (bool, optional): When True, the flow will only run once upon deployment initiation, rather than continuously.
    """
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
    if PREFECT_UI_URL:
        help_message += (
            "\nYou can also run your flow via the Prefect UI:"
            f" [blue]{PREFECT_UI_URL.value()}/deployments/deployment/{deployment_id}[/]\n"
        )

    app.console.print(help_message, soft_wrap=True)
    await runner.start(run_once=run_once)
