"""
DEPRECATION WARNING:

This module is deprecated as of March 2024 and will not be available after September 2024.
It has been replaced by the process worker from the `prefect.workers` module, which offers enhanced functionality and better performance.

For upgrade instructions, see https://docs.prefect.io/latest/guides/upgrade-guide-agents-to-workers/.
"""

import contextlib
import os
import shlex
import signal
import socket
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, Tuple, Union

import anyio
import anyio.abc

from prefect._internal.compatibility.deprecated import deprecated_class
from prefect._internal.pydantic import HAS_PYDANTIC_V2

if HAS_PYDANTIC_V2:
    from pydantic.v1 import Field
else:
    from pydantic import Field

from typing_extensions import Literal

from prefect.exceptions import InfrastructureNotAvailable, InfrastructureNotFound
from prefect.infrastructure.base import Infrastructure, InfrastructureResult
from prefect.utilities.asyncutils import sync_compatible
from prefect.utilities.processutils import get_sys_executable, run_process

if sys.platform == "win32":
    # exit code indicating that the process was terminated by Ctrl+C or Ctrl+Break
    STATUS_CONTROL_C_EXIT = 0xC000013A


def _infrastructure_pid_from_process(process: anyio.abc.Process) -> str:
    hostname = socket.gethostname()
    return f"{hostname}:{process.pid}"


def _parse_infrastructure_pid(infrastructure_pid: str) -> Tuple[str, int]:
    hostname, pid = infrastructure_pid.split(":")
    return hostname, int(pid)


@deprecated_class(
    start_date="Mar 2024",
    help="Use the process worker instead."
    " Refer to the upgrade guide for more information:"
    " https://docs.prefect.io/latest/guides/upgrade-guide-agents-to-workers/.",
)
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
        stream_output: Whether to stream output to local stdout.
        working_dir: Working directory where the process should be opened. If not set,
            a tmp directory will be used.
    """

    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/356e6766a91baf20e1d08bbe16e8b5aaef4d8643-48x48.png"
    _documentation_url = "https://docs.prefect.io/concepts/infrastructure/#process"

    type: Literal["process"] = Field(
        default="process", description="The type of infrastructure."
    )
    stream_output: bool = Field(
        default=True,
        description=(
            "If set, output will be streamed from the process to local standard output."
        ),
    )
    working_dir: Union[str, Path, None] = Field(
        default=None,
        description=(
            "If set, the process will open within the specified path as the working"
            " directory. Otherwise, a temporary directory will be created."
        ),
    )  # Underlying accepted types are str, bytes, PathLike[str], None

    @sync_compatible
    async def run(
        self,
        task_status: anyio.abc.TaskStatus = None,
    ) -> "ProcessResult":
        if not self.command:
            raise ValueError("Process cannot be run with empty command.")

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
                f"Process{display_name} running command: {' '.join(self.command)} in"
                f" {working_dir}"
            )

            # We must add creationflags to a dict so it is only passed as a function
            # parameter on Windows, because the presence of creationflags causes
            # errors on Unix even if set to None
            kwargs: Dict[str, object] = {}
            if sys.platform == "win32":
                kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

            process = await run_process(
                self.command,
                stream_output=self.stream_output,
                task_status=task_status,
                task_status_handler=_infrastructure_pid_from_process,
                env=self._get_environment_variables(),
                cwd=working_dir,
                **kwargs,
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
            elif (
                sys.platform == "win32" and process.returncode == STATUS_CONTROL_C_EXIT
            ):
                help_message = (
                    "Process was terminated due to a Ctrl+C or Ctrl+Break signal. "
                    "Typically, this is caused by manual cancellation."
                )

            self.logger.error(
                f"Process{display_name} exited with status code: {process.returncode}"
                + (f"; {help_message}" if help_message else "")
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
                f"Unable to kill process {pid!r}: The process is running on a different"
                f" host {hostname!r}."
            )

        # In a non-windows environment first send a SIGTERM, then, after
        # `grace_seconds` seconds have passed subsequent send SIGKILL. In
        # Windows we use CTRL_BREAK_EVENT as SIGTERM is useless:
        # https://bugs.python.org/issue26350
        if sys.platform == "win32":
            try:
                os.kill(pid, signal.CTRL_BREAK_EVENT)
            except (ProcessLookupError, WindowsError):
                raise InfrastructureNotFound(
                    f"Unable to kill process {pid!r}: The process was not found."
                )
        else:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                raise InfrastructureNotFound(
                    f"Unable to kill process {pid!r}: The process was not found."
                )

            # Throttle how often we check if the process is still alive to keep
            # from making too many system calls in a short period of time.
            check_interval = max(grace_seconds / 10, 1)

            with anyio.move_on_after(grace_seconds):
                while True:
                    await anyio.sleep(check_interval)

                    # Detect if the process is still alive. If not do an early
                    # return as the process respected the SIGTERM from above.
                    try:
                        os.kill(pid, 0)
                    except ProcessLookupError:
                        return

            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                # We shouldn't ever end up here, but it's possible that the
                # process ended right after the check above.
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
        return [get_sys_executable(), "-m", "prefect.engine"]

    def get_corresponding_worker_type(self):
        return "process"

    async def generate_work_pool_base_job_template(self):
        from prefect.workers.utilities import (
            get_default_base_job_template_for_infrastructure_type,
        )

        base_job_template = await get_default_base_job_template_for_infrastructure_type(
            self.get_corresponding_worker_type(),
        )
        assert (
            base_job_template is not None
        ), "Failed to generate default base job template for Process worker."
        for key, value in self.dict(exclude_unset=True, exclude_defaults=True).items():
            if key == "command":
                base_job_template["variables"]["properties"]["command"][
                    "default"
                ] = shlex.join(value)
            elif key in [
                "type",
                "block_type_slug",
                "_block_document_id",
                "_block_document_name",
                "_is_anonymous",
            ]:
                continue
            elif key in base_job_template["variables"]["properties"]:
                base_job_template["variables"]["properties"][key]["default"] = value
            else:
                self.logger.warning(
                    f"Variable {key!r} is not supported by Process work pools."
                    " Skipping."
                )

        return base_job_template


class ProcessResult(InfrastructureResult):
    """Contains information about the final state of a completed process"""
