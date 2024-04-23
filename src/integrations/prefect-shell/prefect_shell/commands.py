"""Tasks for interacting with shell commands"""

import asyncio
import logging
import os
import subprocess
import sys
import tempfile
from contextlib import AsyncExitStack, contextmanager
from typing import Any, Dict, Generator, List, Optional, Union

import anyio
from anyio.abc import Process
from anyio.streams.text import TextReceiveStream
from pydantic import VERSION as PYDANTIC_VERSION

from prefect import task
from prefect.blocks.abstract import JobBlock, JobRun
from prefect.logging import get_run_logger
from prefect.utilities.asyncutils import sync_compatible
from prefect.utilities.processutils import open_process

if PYDANTIC_VERSION.startswith("2."):
    from pydantic.v1 import DirectoryPath, Field, PrivateAttr
else:
    from pydantic import DirectoryPath, Field, PrivateAttr


@task
async def shell_run_command(
    command: str,
    env: Optional[dict] = None,
    helper_command: Optional[str] = None,
    shell: Optional[str] = None,
    extension: Optional[str] = None,
    return_all: bool = False,
    stream_level: int = logging.INFO,
    cwd: Union[str, bytes, os.PathLike, None] = None,
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
                msg = (
                    f"Command failed with exit code {process.returncode}:\n" f"{stderr}"
                )
                raise RuntimeError(msg)
    finally:
        if os.path.exists(tmp.name):
            os.remove(tmp.name)

    line = lines[-1] if lines else ""
    return lines if return_all else line


class ShellProcess(JobRun):
    """
    A class representing a shell process.
    """

    def __init__(self, shell_operation: "ShellOperation", process: Process):
        self._shell_operation = shell_operation
        self._process = process
        self._output = []

    @property
    def pid(self) -> int:
        """
        The PID of the process.

        Returns:
            The PID of the process.
        """
        return self._process.pid

    @property
    def return_code(self) -> Optional[int]:
        """
        The return code of the process.

        Returns:
            The return code of the process, or `None` if the process is still running.
        """
        return self._process.returncode

    async def _capture_output(self, source):
        """
        Capture output from source.
        """
        async for output in TextReceiveStream(source):
            text = output.rstrip()
            if self._shell_operation.stream_output:
                self.logger.info(f"PID {self.pid} stream output:{os.linesep}{text}")
            self._output.extend(text.split(os.linesep))

    @sync_compatible
    async def wait_for_completion(self) -> None:
        """
        Wait for the shell command to complete after a process is triggered.
        """
        self.logger.debug(f"Waiting for PID {self.pid} to complete.")

        await asyncio.gather(
            self._capture_output(self._process.stdout),
            self._capture_output(self._process.stderr),
        )
        await self._process.wait()

        if self.return_code != 0:
            raise RuntimeError(
                f"PID {self.pid} failed with return code {self.return_code}."
            )
        self.logger.info(
            f"PID {self.pid} completed with return code {self.return_code}."
        )

    @sync_compatible
    async def fetch_result(self) -> List[str]:
        """
        Retrieve the output of the shell operation.

        Returns:
            The lines output from the shell operation as a list.
        """
        if self._process.returncode is None:
            self.logger.info("Process is still running, result may be incomplete.")
        return self._output


class ShellOperation(JobBlock):
    """
    A block representing a shell operation, containing multiple commands.

    For long-lasting operations, use the trigger method and utilize the block as a
    context manager for automatic closure of processes when context is exited.
    If not, manually call the close method to close processes.

    For short-lasting operations, use the run method. Context is automatically managed
    with this method.

    Attributes:
        commands: A list of commands to execute sequentially.
        stream_output: Whether to stream output.
        env: A dictionary of environment variables to set for the shell operation.
        working_dir: The working directory context the commands
            will be executed within.
        shell: The shell to use to execute the commands.
        extension: The extension to use for the temporary file.
            if unset defaults to `.ps1` on Windows and `.sh` on other platforms.

    Examples:
        Load a configured block:
        ```python
        from prefect_shell import ShellOperation

        shell_operation = ShellOperation.load("BLOCK_NAME")
        ```
    """

    _block_type_name = "Shell Operation"
    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/0b47a017e1b40381de770c17647c49cdf6388d1c-250x250.png"  # noqa: E501
    _documentation_url = "https://prefecthq.github.io/prefect-shell/commands/#prefect_shell.commands.ShellOperation"  # noqa: E501

    commands: List[str] = Field(
        default=..., description="A list of commands to execute sequentially."
    )
    stream_output: bool = Field(default=True, description="Whether to stream output.")
    env: Dict[str, str] = Field(
        default_factory=dict,
        title="Environment Variables",
        description="Environment variables to use for the subprocess.",
    )
    working_dir: DirectoryPath = Field(
        default=None,
        title="Working Directory",
        description=(
            "The absolute path to the working directory "
            "the command will be executed within."
        ),
    )
    shell: str = Field(
        default=None,
        description=(
            "The shell to run the command with; if unset, "
            "defaults to `powershell` on Windows and `bash` on other platforms."
        ),
    )
    extension: Optional[str] = Field(
        default=None,
        description=(
            "The extension to use for the temporary file; if unset, "
            "defaults to `.ps1` on Windows and `.sh` on other platforms."
        ),
    )

    _exit_stack: AsyncExitStack = PrivateAttr(
        default_factory=AsyncExitStack,
    )

    @contextmanager
    def _prep_trigger_command(self) -> Generator[str, None, None]:
        """
        Write the commands to a temporary file, handling all the details of
        creating the file and cleaning it up afterwards. Then, return the command
        to run the temporary file.
        """
        try:
            extension = self.extension or (".ps1" if sys.platform == "win32" else ".sh")
            temp_file = tempfile.NamedTemporaryFile(
                prefix="prefect-",
                suffix=extension,
                delete=False,
            )

            joined_commands = os.linesep.join(self.commands)
            self.logger.debug(
                f"Writing the following commands to "
                f"{temp_file.name!r}:{os.linesep}{joined_commands}"
            )
            temp_file.write(joined_commands.encode())

            if self.shell is None and sys.platform == "win32" or extension == ".ps1":
                shell = "powershell"
            elif self.shell is None:
                shell = "bash"
            else:
                shell = self.shell.lower()

            if shell == "powershell":
                # if powershell, set exit code to that of command
                temp_file.write("\r\nExit $LastExitCode".encode())
            temp_file.close()

            trigger_command = [shell, temp_file.name]
            yield trigger_command
        finally:
            if os.path.exists(temp_file.name):
                os.remove(temp_file.name)

    def _compile_kwargs(self, **open_kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Helper method to compile the kwargs for `open_process` so it's not repeated
        across the run and trigger methods.
        """
        trigger_command = self._exit_stack.enter_context(self._prep_trigger_command())
        input_env = os.environ.copy()
        input_env.update(self.env)
        input_open_kwargs = dict(
            command=trigger_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=input_env,
            cwd=self.working_dir,
            **open_kwargs,
        )
        return input_open_kwargs

    @sync_compatible
    async def trigger(self, **open_kwargs: Dict[str, Any]) -> ShellProcess:
        """
        Triggers a shell command and returns the shell command run object
        to track the execution of the run. This method is ideal for long-lasting
        shell commands; for short-lasting shell commands, it is recommended
        to use the `run` method instead.

        Args:
            **open_kwargs: Additional keyword arguments to pass to `open_process`.

        Returns:
            A `ShellProcess` object.

        Examples:
            Sleep for 5 seconds and then print "Hello, world!":
            ```python
            from prefect_shell import ShellOperation

            with ShellOperation(
                commands=["sleep 5", "echo 'Hello, world!'"],
            ) as shell_operation:
                shell_process = shell_operation.trigger()
                shell_process.wait_for_completion()
                shell_output = shell_process.fetch_result()
            ```
        """
        input_open_kwargs = self._compile_kwargs(**open_kwargs)
        process = await self._exit_stack.enter_async_context(
            open_process(**input_open_kwargs)
        )
        num_commands = len(self.commands)
        self.logger.info(
            f"PID {process.pid} triggered with {num_commands} commands running "
            f"inside the {(self.working_dir or '.')!r} directory."
        )
        return ShellProcess(shell_operation=self, process=process)

    @sync_compatible
    async def run(self, **open_kwargs: Dict[str, Any]) -> List[str]:
        """
        Runs a shell command, but unlike the trigger method,
        additionally waits and fetches the result directly, automatically managing
        the context. This method is ideal for short-lasting shell commands;
        for long-lasting shell commands, it is
        recommended to use the `trigger` method instead.

        Args:
            **open_kwargs: Additional keyword arguments to pass to `open_process`.

        Returns:
            The lines output from the shell command as a list.

        Examples:
            Sleep for 5 seconds and then print "Hello, world!":
            ```python
            from prefect_shell import ShellOperation

            shell_output = ShellOperation(
                commands=["sleep 5", "echo 'Hello, world!'"]
            ).run()
            ```
        """
        input_open_kwargs = self._compile_kwargs(**open_kwargs)
        async with open_process(**input_open_kwargs) as process:
            shell_process = ShellProcess(shell_operation=self, process=process)
            num_commands = len(self.commands)
            self.logger.info(
                f"PID {process.pid} triggered with {num_commands} commands running "
                f"inside the {(self.working_dir or '.')!r} directory."
            )
            await shell_process.wait_for_completion()
            result = await shell_process.fetch_result()

        return result

    @sync_compatible
    async def close(self):
        """
        Close the job block.
        """
        await self._exit_stack.aclose()
        self.logger.info("Successfully closed all open processes.")

    async def aclose(self):
        """
        Asynchronous version of the close method.
        """
        await self.close()

    async def __aenter__(self) -> "ShellOperation":
        """
        Asynchronous version of the enter method.
        """
        return self

    async def __aexit__(self, *exc_info):
        """
        Asynchronous version of the exit method.
        """
        await self.close()

    def __enter__(self) -> "ShellOperation":
        """
        Enter the context of the job block.
        """
        return self

    def __exit__(self, *exc_info):
        """
        Exit the context of the job block.
        """
        self.close()
