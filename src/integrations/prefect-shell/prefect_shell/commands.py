"""Tasks for interacting with shell commands"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import subprocess
import sys
import tempfile
import threading
from contextlib import AsyncExitStack, ExitStack, contextmanager
from contextvars import copy_context
from typing import IO, Any, Generator, Optional, Union

import anyio
from anyio.abc import Process
from anyio.streams.text import TextReceiveStream
from pydantic import DirectoryPath, Field, PrivateAttr

from prefect import task
from prefect._internal.compatibility.async_dispatch import async_dispatch
from prefect.blocks.abstract import JobBlock, JobRun
from prefect.logging import get_run_logger
from prefect.utilities.processutils import command_from_string, open_process

_SHELL_TERMINATE_GRACE_SECONDS = 5.0


def _is_powershell_executable(token: str) -> bool:
    name = os.path.splitext(os.path.basename(token))[0].lower()
    return name in ("powershell", "pwsh")


def _argv_has_execution_policy_flag(argv: list[str]) -> bool:
    return any("executionpolicy" in arg.lower() for arg in argv)


def _argv_to_run_script_file(
    shell: str | None, extension: str, script_path: str
) -> list[str]:
    """Build argv to execute a temporary script (PowerShell uses -File)."""
    is_ps1 = extension == ".ps1"
    if shell is None:
        if sys.platform == "win32" or is_ps1:
            return [
                "powershell",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                script_path,
            ]
        return ["bash", script_path]

    argv = command_from_string(shell)
    if not argv:
        return [shell, script_path]

    use_powershell = is_ps1 or _is_powershell_executable(argv[0])
    if use_powershell:
        if not _argv_has_execution_policy_flag(argv):
            argv = [argv[0], "-ExecutionPolicy", "Bypass", *argv[1:]]
        return [*argv, "-File", script_path]
    return [*argv, script_path]


def _process_isolation_kwargs() -> dict[str, Any]:
    """Kwargs that place the spawned shell in its own process group.

    Isolating the shell in a new session lets us signal the whole process
    tree on cleanup instead of only the shell, so descendants like
    `sleep 9999` don't outlive a cancelled flow run (GH #20979).

    POSIX-only; Windows has a different process model and is not affected
    by the bug this guards against.
    """
    if sys.platform == "win32":
        return {}
    return {"start_new_session": True}


def _signal_process_tree(
    process: Union[Process, subprocess.Popen[bytes]],
    sig: int,
) -> None:
    """Send `sig` to the process and any descendants in its POSIX process group.

    No-op on Windows — the process-group isolation in
    `_process_isolation_kwargs` is POSIX-only, so there is no matching tree
    to signal on Windows. Windows cleanup relies on the direct
    `subprocess.Popen.kill` / `terminate` on the caller side.
    """
    if sys.platform == "win32":
        return

    pid = process.pid
    if not isinstance(pid, int):
        # Includes `None` and mocked processes used in tests.
        return

    try:
        pgid = os.getpgid(pid)
    except ProcessLookupError:
        # Leader already gone; any remaining descendants still share this pgid
        # because we spawned with `start_new_session=True`.
        pgid = pid
    except PermissionError:
        return

    try:
        os.killpg(pgid, sig)
    except (ProcessLookupError, PermissionError):
        pass


def _close_sync_process_tree(process: subprocess.Popen[bytes]) -> None:
    """Synchronously terminate the process (tree on POSIX) and wait for exit.

    POSIX: signal the process group with SIGTERM regardless of whether the
    shell itself has already exited — detached descendants (e.g. `sleep 120 &`)
    can outlive the shell and still share its process group. If the shell is
    still running, wait up to `_SHELL_TERMINATE_GRACE_SECONDS`, then escalate
    to SIGKILL on the group if it has not exited.

    Windows: `process.kill()` + `process.wait()` if the process is still
    running; no-op otherwise.
    """
    if sys.platform == "win32":
        if process.returncode is None:
            process.kill()
            process.wait()
        return

    _signal_process_tree(process, signal.SIGTERM)
    if process.returncode is None:
        try:
            process.wait(timeout=_SHELL_TERMINATE_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            _signal_process_tree(process, signal.SIGKILL)
            process.wait()


@task
async def shell_run_command(
    command: str,
    env: dict[str, str] | None = None,
    helper_command: str | None = None,
    shell: str | None = None,
    extension: str | None = None,
    return_all: bool = False,
    stream_level: int = logging.INFO,
    cwd: str | bytes | os.PathLike[str] | None = None,
) -> list[str] | str:
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
        shell = "powershell" if sys.platform == "win32" else "bash"

    shell_argv = command_from_string(shell)
    exe_token = shell_argv[0] if shell_argv else shell
    extension = ".ps1" if _is_powershell_executable(exe_token) else extension

    tmp = tempfile.NamedTemporaryFile(prefix="prefect-", suffix=extension, delete=False)
    try:
        if helper_command:
            tmp.write(helper_command.encode())
            tmp.write(os.linesep.encode())
        tmp.write(command.encode())
        shell_command = _argv_to_run_script_file(shell, extension or ".sh", tmp.name)
        if shell_command and _is_powershell_executable(shell_command[0]):
            tmp.write("\r\nExit $LastExitCode".encode())
        tmp.close()

        lines: list[str] = []
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


class ShellProcess(JobRun[list[str]]):
    """
    A class representing a shell process.

    Supports both async (anyio.abc.Process) and sync (subprocess.Popen) processes.
    """

    def __init__(
        self,
        shell_operation: "ShellOperation",
        process: Union[Process, subprocess.Popen[bytes]],
    ):
        self._shell_operation = shell_operation
        self._process = process
        self._output: list[str] = []

    @property
    def pid(self) -> int:
        """
        The PID of the process.

        Returns:
            The PID of the process.
        """
        return self._process.pid

    @property
    def return_code(self) -> int | None:
        """
        The return code of the process.

        Returns:
            The return code of the process, or `None` if the process is still running.
        """
        return self._process.returncode

    async def _capture_output(self, source: Any):
        """
        Capture output from source (async version for anyio Process).
        """
        async for output in TextReceiveStream(source):
            text = output.rstrip()
            if self._shell_operation.stream_output:
                self.logger.info(f"PID {self.pid} stream output:{os.linesep}{text}")
            self._output.extend(text.split(os.linesep))

    def _capture_output_sync(
        self,
        source: IO[bytes],
        output_label: str,
        include_in_output: bool,
    ) -> None:
        """
        Capture output from source (sync version for subprocess pipes).
        """
        for line in iter(source.readline, b""):
            text = line.decode(errors="replace").rstrip()
            if not text:
                continue
            if self._shell_operation.stream_output:
                self.logger.info(f"PID {self.pid} {output_label}:{os.linesep}{text}")
            if include_in_output:
                self._output.extend(text.split(os.linesep))

    async def await_for_completion(self) -> None:
        """
        Wait for the shell command to complete after a process is triggered (async version).
        """
        if isinstance(self._process, subprocess.Popen):
            raise RuntimeError(
                "Cannot use async await_for_completion with a sync subprocess.Popen. "
                "Use wait_for_completion instead."
            )

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

    @async_dispatch(await_for_completion)
    def wait_for_completion(self) -> None:
        """
        Wait for the shell command to complete after a process is triggered (sync version).
        """
        if not isinstance(self._process, subprocess.Popen):
            raise RuntimeError(
                "Cannot use sync wait_for_completion with an async Process. "
                "Use await_for_completion instead."
            )

        self.logger.debug(f"Waiting for PID {self.pid} to complete.")

        output_threads: list[threading.Thread] = []

        # Each thread needs its own copied Context. Reusing the same Context for
        # both `Context.run(...)` calls raises `RuntimeError` once one thread enters it.
        if self._process.stdout is not None:
            stdout_context = copy_context()
            output_threads.append(
                threading.Thread(
                    target=stdout_context.run,
                    args=(
                        self._capture_output_sync,
                        self._process.stdout,
                        "stream output",
                        True,
                    ),
                    daemon=True,
                )
            )

        if self._process.stderr is not None:
            stderr_context = copy_context()
            output_threads.append(
                threading.Thread(
                    target=stderr_context.run,
                    args=(
                        self._capture_output_sync,
                        self._process.stderr,
                        "stderr",
                        False,
                    ),
                    daemon=True,
                )
            )

        for output_thread in output_threads:
            output_thread.start()

        for output_thread in output_threads:
            output_thread.join()

        self._process.wait()

        if self.return_code != 0:
            raise RuntimeError(
                f"PID {self.pid} failed with return code {self.return_code}."
            )
        self.logger.info(
            f"PID {self.pid} completed with return code {self.return_code}."
        )

    async def afetch_result(self) -> list[str]:
        """
        Retrieve the output of the shell operation (async version).

        Returns:
            The lines output from the shell operation as a list.
        """
        if self._process.returncode is None:
            self.logger.info("Process is still running, result may be incomplete.")
        return self._output

    @async_dispatch(afetch_result)
    def fetch_result(self) -> list[str]:
        """
        Retrieve the output of the shell operation (sync version).

        Returns:
            The lines output from the shell operation as a list.
        """
        if self._process.returncode is None:
            self.logger.info("Process is still running, result may be incomplete.")
        return self._output


class ShellOperation(JobBlock[list[str]]):
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
    _documentation_url = "https://docs.prefect.io/integrations/prefect-shell"  # noqa

    commands: list[str] = Field(
        default=..., description="A list of commands to execute sequentially."
    )
    stream_output: bool = Field(default=True, description="Whether to stream output.")
    env: dict[str, str] = Field(
        default_factory=dict,
        title="Environment Variables",
        description="Environment variables to use for the subprocess.",
    )
    working_dir: Optional[DirectoryPath] = Field(
        default=None,
        title="Working Directory",
        description=(
            "The absolute path to the working directory "
            "the command will be executed within."
        ),
    )
    shell: Optional[str] = Field(
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
    _sync_exit_stack: ExitStack = PrivateAttr(
        default_factory=ExitStack,
    )
    _sync_temp_files: list[str] = PrivateAttr(default_factory=list)

    @contextmanager
    def _prep_trigger_command(self) -> Generator[list[str], None, None]:
        """
        Write the commands to a temporary file, handling all the details of
        creating the file and cleaning it up afterwards. Then, return the command
        to run the temporary file.
        """
        temp_file = None
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

            trigger_command = _argv_to_run_script_file(
                self.shell,
                extension,
                temp_file.name,
            )
            if trigger_command and _is_powershell_executable(trigger_command[0]):
                temp_file.write("\r\nExit $LastExitCode".encode())
            temp_file.close()

            yield trigger_command
        finally:
            if temp_file is not None and os.path.exists(temp_file.name):
                os.remove(temp_file.name)

    def _compile_kwargs(self, **open_kwargs: dict[str, Any]) -> dict[str, Any]:
        """
        Helper method to compile the kwargs for `open_process` so it's not repeated
        across the run and trigger methods (async version).
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
            **_process_isolation_kwargs(),
            **open_kwargs,
        )
        return input_open_kwargs

    def _compile_kwargs_sync(self, **open_kwargs: dict[str, Any]) -> dict[str, Any]:
        """
        Helper method to compile the kwargs for `subprocess.Popen` (sync version).
        """
        trigger_command = self._sync_exit_stack.enter_context(
            self._prep_trigger_command()
        )
        input_env = os.environ.copy()
        input_env.update(self.env)
        input_open_kwargs = dict(
            args=trigger_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=input_env,
            cwd=self.working_dir,
            **_process_isolation_kwargs(),
            **open_kwargs,
        )
        return input_open_kwargs

    async def atrigger(self, **open_kwargs: dict[str, Any]) -> ShellProcess:
        """
        Triggers a shell command and returns the shell command run object
        to track the execution of the run (async version). This method is ideal
        for long-lasting shell commands; for short-lasting shell commands, it is
        recommended to use the `run` method instead.

        Args:
            **open_kwargs: Additional keyword arguments to pass to `open_process`.

        Returns:
            A `ShellProcess` object.

        Examples:
            Sleep for 5 seconds and then print "Hello, world!":
            ```python
            from prefect_shell import ShellOperation

            async with ShellOperation(
                commands=["sleep 5", "echo 'Hello, world!'"],
            ) as shell_operation:
                shell_process = await shell_operation.atrigger()
                await shell_process.await_for_completion()
                shell_output = await shell_process.afetch_result()
            ```
        """
        input_open_kwargs = self._compile_kwargs(**open_kwargs)
        process = await self._exit_stack.enter_async_context(
            open_process(**input_open_kwargs)
        )
        # Signal the shell's descendants before `open_process` unwinds, so its
        # `process.terminate()` + `aclose()` cleanup doesn't leave descendants
        # behind. Registered LIFO so it runs before `open_process.__aexit__`.
        self._exit_stack.callback(_signal_process_tree, process, signal.SIGTERM)
        num_commands = len(self.commands)
        self.logger.info(
            f"PID {process.pid} triggered with {num_commands} commands running "
            f"inside the {(self.working_dir or '.')!r} directory."
        )
        return ShellProcess(shell_operation=self, process=process)

    @async_dispatch(atrigger)
    def trigger(self, **open_kwargs: dict[str, Any]) -> ShellProcess:
        """
        Triggers a shell command and returns the shell command run object
        to track the execution of the run (sync version). This method is ideal
        for long-lasting shell commands; for short-lasting shell commands, it is
        recommended to use the `run` method instead.

        Args:
            **open_kwargs: Additional keyword arguments to pass to subprocess.Popen.

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
        input_open_kwargs = self._compile_kwargs_sync(**open_kwargs)
        process = subprocess.Popen(**input_open_kwargs)
        # Ensure `close()` (and the `__exit__` that calls it) reclaims the
        # subprocess tree instead of leaking it when a user exits the context
        # without `wait_for_completion()`.
        self._sync_exit_stack.callback(_close_sync_process_tree, process)
        num_commands = len(self.commands)
        self.logger.info(
            f"PID {process.pid} triggered with {num_commands} commands running "
            f"inside the {(self.working_dir or '.')!r} directory."
        )
        return ShellProcess(shell_operation=self, process=process)

    async def arun(self, **open_kwargs: dict[str, Any]) -> list[str]:
        """
        Runs a shell command (async version), but unlike the trigger method,
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

            shell_output = await ShellOperation(
                commands=["sleep 5", "echo 'Hello, world!'"]
            ).arun()
            ```
        """
        input_open_kwargs = self._compile_kwargs(**open_kwargs)
        async with open_process(**input_open_kwargs) as process:
            try:
                shell_process = ShellProcess(shell_operation=self, process=process)
                num_commands = len(self.commands)
                self.logger.info(
                    f"PID {process.pid} triggered with {num_commands} commands running "
                    f"inside the {(self.working_dir or '.')!r} directory."
                )
                await shell_process.await_for_completion()
                result = await shell_process.afetch_result()
            finally:
                # Signal descendants of the shell to terminate. The enclosing
                # `open_process` context manager handles the wait on the direct
                # process during its own cleanup.
                _signal_process_tree(process, signal.SIGTERM)

        return result

    @async_dispatch(arun)
    def run(self, **open_kwargs: dict[str, Any]) -> list[str]:
        """
        Runs a shell command (sync version), but unlike the trigger method,
        additionally waits and fetches the result directly, automatically managing
        the context. This method is ideal for short-lasting shell commands;
        for long-lasting shell commands, it is
        recommended to use the `trigger` method instead.

        Args:
            **open_kwargs: Additional keyword arguments to pass to subprocess.Popen.

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
        input_open_kwargs = self._compile_kwargs_sync(**open_kwargs)
        process = subprocess.Popen(**input_open_kwargs)
        try:
            shell_process = ShellProcess(shell_operation=self, process=process)
            num_commands = len(self.commands)
            self.logger.info(
                f"PID {process.pid} triggered with {num_commands} commands running "
                f"inside the {(self.working_dir or '.')!r} directory."
            )
            shell_process.wait_for_completion()
            result = shell_process.fetch_result()
        finally:
            # Ensure the whole process tree is cleaned up, not just the shell.
            _close_sync_process_tree(process)

        return result

    async def aclose(self):
        """
        Close the job block (async version).
        """
        await self._exit_stack.aclose()
        self.logger.info("Successfully closed all open processes.")

    @async_dispatch(aclose)
    def close(self):
        """
        Close the job block (sync version).
        """
        self._sync_exit_stack.close()
        self.logger.info("Successfully closed all open processes.")

    async def __aenter__(self) -> "ShellOperation":
        """
        Asynchronous version of the enter method.
        """
        return self

    async def __aexit__(self, *exc_info: Any):
        """
        Asynchronous version of the exit method.
        """
        await self.aclose()

    def __enter__(self) -> "ShellOperation":
        """
        Enter the context of the job block.
        """
        return self

    def __exit__(self, *exc_info: Any):
        """
        Exit the context of the job block.
        """
        self.close()
