"""Tasks for interacting with shell commands"""

import logging
import os
import sys
import tempfile
from typing import List, Optional, Union

import anyio
import typer
from anyio.streams.text import TextReceiveStream
from pydantic import VERSION as PYDANTIC_VERSION

from prefect import flow
from prefect.cli._types import PrefectTyper
from prefect.cli.root import app
from prefect.client.schemas.schedules import CronSchedule
from prefect.logging import get_run_logger

if PYDANTIC_VERSION.startswith("2."):
    pass
else:
    pass

command_app = PrefectTyper(name="command", help="Commands for working with commands.")
app.add_typer(command_app)


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


@command_app.command("serve")
async def serve(
    command: str,
    name: str = typer.Option(help="Name of the flow to serve"),
    cwd: str = typer.Option(None, help="Working directory for the flow"),
    cron_schedule: str = typer.Option(None, help="Cron schedule for the flow"),
):
    """
    Serve the execution of a command by executing it as a Prefect flow
    """
    CronSchedule(cron_schedule) if cron_schedule else None
    # Call the shell_run_command flow with provided arguments
    await shell_run_command.serve(
        name=name,
        parameters={"command": command, "cwd": cwd},
    )
