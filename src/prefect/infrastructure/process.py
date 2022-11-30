import asyncio
import contextlib
import os
import signal
import socket
import sys
import tempfile
from pathlib import Path
from typing import Tuple, Union

import anyio
import anyio.abc
import sniffio
from pydantic import Field
from typing_extensions import Literal

from prefect.exceptions import InfrastructureNotAvailable, InfrastructureNotFound
from prefect.infrastructure.base import Infrastructure, InfrastructureResult
from prefect.utilities.asyncutils import sync_compatible
from prefect.utilities.processutils import run_process


def _use_threaded_child_watcher():
    if (
        sys.version_info < (3, 8)
        and sniffio.current_async_library() == "asyncio"
        and sys.platform != "win32"
    ):
        from prefect.utilities.compat import ThreadedChildWatcher

        # Python < 3.8 does not use a `ThreadedChildWatcher` by default which can
        # lead to errors in tests on unix as the previous default `SafeChildWatcher`
        # is not compatible with threaded event loops.
        asyncio.get_event_loop_policy().set_child_watcher(ThreadedChildWatcher())


def _infrastructure_pid_from_process(process: anyio.abc.Process) -> str:
    hostname = socket.gethostname()
    return f"{hostname}:{process.pid}"


def _parse_infrastructure_pid(infrastructure_pid: str) -> Tuple[str, int]:
    hostname, pid = infrastructure_pid.split(":")
    return hostname, int(pid)


class Process(Infrastructure):
    """
    Run a command in a new process.

    Current environment variables and Prefect settings will be included in the created
    process. Configured environment variables will override any current environment
    variables.

    Attributes:
        command: A list of strings specifying the command to run in the container to
            start the flow run. In most cases you should not override this.
        env: Environment variables to set for the new process.
        labels: Labels for the process. Labels are for metadata purposes only and
            cannot be attached to the process itself.
        name: A name for the process. For display purposes only.
    """

    _logo_url = "https://images.ctfassets.net/gm98wzqotmnx/39WQhVu4JK40rZWltGqhuC/d15be6189a0cb95949a6b43df00dcb9b/image5.png?h=250"

    type: Literal["process"] = Field(
        default="process", description="The type of infrastructure."
    )
    stream_output: bool = Field(
        default=True,
        description="If set, output will be streamed from the process to local standard output.",
    )
    working_dir: Union[str, Path, None] = Field(
        default=None,
        description="If set, the process will open within the specified path as the working directory."
        " Otherwise, a temporary directory will be created.",
    )  # Underlying accepted types are str, bytes, PathLike[str], None

    @sync_compatible
    async def run(
        self,
        task_status: anyio.abc.TaskStatus = None,
    ) -> "ProcessResult":
        if not self.command:
            raise ValueError("Process cannot be run with empty command.")

        _use_threaded_child_watcher()
        display_name = f" {self.name!r}" if self.name else ""

        # Open a subprocess to execute the flow run
        self.logger.info(f"Opening process{display_name}...")
        working_dir_ctx = (
            tempfile.TemporaryDirectory(suffix="prefect")
            if not self.working_dir
            else contextlib.nullcontext(self.working_dir)
        )
        with working_dir_ctx as working_dir:
            self.logger.debug(
                f"Process{display_name} running command: {' '.join(self.command)} in {working_dir}"
            )

            process = await run_process(
                self.command,
                stream_output=self.stream_output,
                task_status=task_status,
                task_status_handler=_infrastructure_pid_from_process,
                env=self._get_environment_variables(),
                cwd=working_dir,
            )

        # Use the pid for display if no name was given
        display_name = display_name or f" {process.pid}"

        if process.returncode:
            help_message = None
            if process.returncode == -9:
                help_message = (
                    "This indicates that the process exited due to a SIGKILL signal. "
                    "Typically, this is either caused by manual cancellation or "
                    "high memory usage causing the operating system to "
                    "terminate the process."
                )
            if process.returncode == -15:
                help_message = (
                    "This indicates that the process exited due to a SIGTERM signal. "
                    "Typically, this is caused by manual cancellation."
                )
            elif process.returncode == 247:
                help_message = (
                    "This indicates that the process was terminated due to high "
                    "memory usage."
                )

            self.logger.error(
                f"Process{display_name} exited with status code: "
                f"{process.returncode}" + (f"; {help_message}" if help_message else "")
            )
        else:
            self.logger.info(f"Process{display_name} exited cleanly.")

        return ProcessResult(
            status_code=process.returncode, identifier=str(process.pid)
        )

    async def kill(self, infrastructure_pid: str, grace_seconds: int = 30):
        hostname, pid = _parse_infrastructure_pid(infrastructure_pid)

        if hostname != socket.gethostname():
            raise InfrastructureNotAvailable(
                f"Unable to kill process {pid!r}: The process is running on a different host {hostname!r}."
            )

        # In a non-windows enviornment first send a SIGTERM, then, after
        # `grace_seconds` seconds have passed subsequent send SIGKILL. In
        # Windows we use CTRL_BREAK_EVENT as SIGTERM is useless:
        # https://bugs.python.org/issue26350
        if sys.platform == "win32":
            try:
                os.kill(pid, signal.CTRL_BREAK_EVENT)
            except ProcessLookupError:
                # The process exited before we were able to kill it.
                return
        else:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                raise InfrastructureNotFound(
                    f"Unable to kill process {pid!r}: The process was not found."
                )

            await anyio.sleep(grace_seconds)

            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                # The process likely exited due to the SIGTERM above.
                return

    def preview(self):
        environment = self._get_environment_variables(include_os_environ=False)
        return " \\\n".join(
            [f"{key}={value}" for key, value in environment.items()]
            + [" ".join(self.command)]
        )

    def _get_environment_variables(self, include_os_environ: bool = True):
        os_environ = os.environ if include_os_environ else {}
        # The base environment must override the current environment or
        # the Prefect settings context may not be respected
        env = {**os_environ, **self._base_environment(), **self.env}

        # Drop null values allowing users to "unset" variables
        return {key: value for key, value in env.items() if value is not None}

    def _base_flow_run_command(self):
        return [sys.executable, "-m", "prefect.engine"]


class ProcessResult(InfrastructureResult):
    """Contains information about the final state of a completed process"""
