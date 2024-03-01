"""Tasks for interacting with shell commands"""

import shlex

import typer
from pydantic import VERSION as PYDANTIC_VERSION

import prefect
from prefect import flow
from prefect.cli._types import PrefectTyper
from prefect.cli.root import app
from prefect.deployments.runner import EntrypointType
from prefect.utilities.processutils import run_process

if PYDANTIC_VERSION.startswith("2."):
    pass
else:
    pass

shell_app = PrefectTyper(name="shell", help="Commands for working with shell commands.")
app.add_typer(shell_app)


@flow
async def run_shell_process(command: str, stream_output: bool = False):
    """
    Run a shell process asynchronously.

    Args:
        command (str): The shell command to execute.
        stream_output (bool, optional): Whether to stream the output of the process. Defaults to False.
        **kwargs: Additional keyword arguments to pass to the underlying process runner.

    Returns:
        None
    """

    command_list = shlex.split(command)
    await run_process(command=command_list, stream_output=stream_output)


@shell_app.command("watch")
async def command(
    command: str,
    stream_output: bool = typer.Option(False, help="Stream the output of the command"),
):
    """
    Watch the execution of a command by executing it as a Prefect flow
    """
    # Call the shell_run_command flow with provided arguments
    await run_shell_process(command=command, stream_output=stream_output)


@shell_app.command("serve")
async def serve(
    command: str,
    name: str = typer.Option(..., help="Name of the flow"),
    cron_schedule: str = typer.Option(None, help="Cron schedule for the flow"),
):
    """
    Serve the execution of a command by executing it as a Prefect flow
    """
    # CronSchedule(cron_schedule) if cron_schedule else None
    # Call the shell_run_command flow with provided arguments
    # await shell_run_command.serve(
    #     name=name,
    #     parameters={"command": command, "cwd": cwd},
    # )

    flow_from_source = await run_shell_process.to_deployment(
        name=name,
        parameters={"command": command, "stream_output": True},
        entrypoint_type=EntrypointType.MODULE_PATH,
    )
    await prefect.serve(flow_from_source, name=name)
