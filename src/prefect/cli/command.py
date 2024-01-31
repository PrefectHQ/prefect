"""Tasks for interacting with shell commands"""

import logging
import os
import sys
import tempfile
from enum import Enum
from typing import List, Optional, Union

import anyio
import typer
from anyio.streams.text import TextReceiveStream
from pydantic import VERSION as PYDANTIC_VERSION

from prefect import flow
from prefect.cli._types import PrefectTyper
from prefect.cli.root import app
from prefect.logging import get_run_logger

if PYDANTIC_VERSION.startswith("2."):
    pass
else:
    pass

command_app = PrefectTyper(name="command", help="Commands for working with commands.")
app.add_typer(command_app)


class ScheduleType(str, Enum):
    INTERVAL = "interval"
    CRON = "cron"
    RRULE = "rrule"
    NOSCHEDULE = "noschedule"


@flow
async def shell_run_command(
    command: str,
    name: str = "Shell Run Command",
    env: Optional[dict] = None,
    helper_command: Optional[str] = None,
    shell: Optional[str] = None,
    extension: Optional[str] = None,
    return_all: bool = True,
    stream_level: int = logging.INFO,
    cwd: Optional[os.PathLike] = None,
) -> Union[List, str]:
    """
    Runs arbitrary shell commands.

    Args:
        command: Shell command to be executed; can also be
            provided post-initialization by calling this task instance.
        env: Dictionary of environment variables to use for
            the subprocess; can also be provided at runtime.
        helper_command: String representing a shell command, which
            will be executed prior to the `command` in the same process.
            Can be used to change directories, define helper functions, etc.
            for different commands in a flow.
        shell: Shell to run the command with.
        extension: File extension to be appended to the command to be executed.
        return_all: Whether this task should return all lines of stdout as a list,
            or just the last line as a string.
        stream_level: The logging level of the stream;
            defaults to 20 equivalent to `logging.INFO`.
        cwd: The working directory context the command will be executed within

    Returns:
        If return all, returns all lines as a list; else the last line as a string.

    Example:
        List contents in the current directory.
        ```python
        from prefect import flow
        from prefect_shell import shell_run_command

        @flow
        def example_shell_run_command_flow():
            return shell_run_command(command="ls .", return_all=True)

        example_shell_run_command_flow()
        ```
    """
    logger = get_run_logger()

    current_env = os.environ.copy()
    current_env.update(env or {})

    if shell is None:
        # if shell is not specified:
        # use powershell for windows
        # use bash for other platforms
        shell = "powershell" if sys.platform == "win32" else "bash"

    extension = ".ps1" if shell.lower() == "powershell" else extension

    tmp = tempfile.NamedTemporaryFile(prefix="prefect-", suffix=extension, delete=False)
    try:
        if helper_command:
            tmp.write(helper_command.encode())
            tmp.write(os.linesep.encode())
        tmp.write(command.encode())
        if shell.lower() == "powershell":
            # if powershell, set exit code to that of command
            tmp.write("\r\nExit $LastExitCode".encode())
        tmp.close()

        shell_command = [shell, tmp.name]

        lines = []
        async with await anyio.open_process(
            shell_command, env=current_env, cwd=cwd
        ) as process:
            async for text in TextReceiveStream(process.stdout):
                logger.log(level=stream_level, msg=text)
                lines.extend(text.rstrip().split("\n"))

            await process.wait()
            if process.returncode:
                stderr = "\n".join(
                    [text async for text in TextReceiveStream(process.stderr)]
                )
                if not stderr and lines:
                    stderr = f"{lines[-1]}\n"
                msg = f"Command failed with exit code {process.returncode}:\n{stderr}"
                raise RuntimeError(msg)
    finally:
        if os.path.exists(tmp.name):
            os.remove(tmp.name)

    line = lines[-1] if lines else ""
    return lines if return_all else line


@command_app.command("watch")
async def command(
    command: str,
    cwd: str = typer.Option(None, help="Working directory for the flow"),
):
    """
    Watch the execution of a command by executing it as a Prefect flow
    """
    # Call the shell_run_command flow with provided arguments
    await shell_run_command(command, cwd=cwd)


# @command_app.command("serve")
# async def serve(
#     command: str,
#     name: str = typer.Option(..., "--name", help="Name of the flow to serve."),
#     cwd: Optional[str] = typer.Option(None, help="Working directory for the flow."),
#     interval: Optional[str] = typer.Option(
#         None,
#         help="Interval at which to run the flow, as a string parseable into a timedelta.",
#     ),
#     cron: Optional[str] = typer.Option(
#         None, help="CRON expression for scheduling the flow."
#     ),
#     rrule: Optional[str] = typer.Option(
#         None, help="RRULE expression for complex scheduling."
#     ),
#     schedule: Optional[ScheduleType] = typer.Option(
#         None, help="Custom scheduling type."
#     ),
#     is_schedule_active: Optional[bool] = typer.Option(
#         None, help="Flag to activate or deactivate scheduling."
#     ),
#     # triggers: Optional[List[DeploymentTrigger]] = typer.Option(
#     #     None, help="List of triggers for flow deployment."
#     # ),
#     parameters: Optional[dict] = typer.Option(
#         None, help="Dictionary of parameters to pass to the flow."
#     ),
#     description: Optional[str] = typer.Option(None, help="Description of the flow."),
#     tags: Optional[List[str]] = typer.Option(
#         None, help="List of tags associated with the flow."
#     ),
#     version: Optional[str] = typer.Option(None, help="Version of the flow."),
#     enforce_parameter_schema: bool = typer.Option(
#         False, help="Flag to enforce parameter schema."
#     ),
#     pause_on_shutdown: bool = typer.Option(
#         True, help="Flag to pause the flow on shutdown."
#     ),
#     print_starting_message: bool = typer.Option(
#         True, help="Flag to print a starting message."
#     ),
#     limit: Optional[int] = typer.Option(
#         None, help="Limit the number of concurrent runs."
#     ),
#     webserver: bool = typer.Option(
#         False, help="Flag to start a webserver for the flow."
#     ),
# ):
#     """
#     Serve the execution of a command by executing it as a Prefect flow
#     """
#     from prefect.runner import Runner

#     # Handling for my_flow.serve(__file__)
#     # Will set name to name of file where my_flow.serve() without the extension
#     # Non filepath strings will pass through unchanged
#     name = Path(name).stem
#     # Parse and convert the schedule string to the correct schedule type
#     parsed_schedule = None
#     if schedule:
#         if schedule == ScheduleType.INTERVAL:
#             parsed_schedule = IntervalSchedule()
#         elif schedule == ScheduleType.CRON:
#             parsed_schedule = CronSchedule()
#         elif schedule == ScheduleType.RRULE:
#             parsed_schedule = RRuleSchedule()
#         elif schedule == ScheduleType.NOSCHEDULE:
#             parsed_schedule = NoSchedule()

#     runner = Runner(name=name, limit=limit)
#     deployment_id = await runner.add_flow(
#         flow=await shell_run_command(command=command, cwd=cwd),
#         name=name,
#         triggers=triggers,
#         interval=interval,
#         cron=cron,
#         rrule=rrule,
#         schedule=parsed_schedule,
#         is_schedule_active=is_schedule_active,
#         parameters=parameters,
#         description=description,
#         tags=tags,
#         version=version,
#         enforce_parameter_schema=enforce_parameter_schema,
#     )
#     if print_starting_message:
#         help_message = (
#             f"[green]Your flow {name!r} is being served and polling for"
#             " scheduled runs!\n[/]\nTo trigger a run for this flow, use the"
#             " following command:\n[blue]\n\t$ prefect deployment run"
#             f" '{name}/{name}'\n[/]"
#         )
#         if PREFECT_UI_URL:
#             help_message += (
#                 "\nYou can also run your flow via the Prefect UI:"
#                 f" [blue]{PREFECT_UI_URL.value()}/deployments/deployment/{deployment_id}[/]\n"
#             )

#         app.console.print(Panel(help_message))
#     await runner.start(webserver=webserver)
