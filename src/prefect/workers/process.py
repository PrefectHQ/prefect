"""
Module containing the Process worker used for executing flow runs as subprocesses.

To start a Process worker, run the following command:

```bash
prefect worker start --pool 'my-work-pool' --type process
```

Replace `my-work-pool` with the name of the work pool you want the worker
to poll for flow runs.

For more information about work pools and workers,
checkout out the [Prefect docs](/concepts/work-pools/).
"""

import contextlib
import os
import signal
import socket
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional, Tuple

import anyio
import anyio.abc
from pydantic import Field, field_validator

from prefect._internal.schemas.validators import validate_command
from prefect.client.schemas import FlowRun
from prefect.exceptions import InfrastructureNotAvailable, InfrastructureNotFound
from prefect.utilities.processutils import get_sys_executable, run_process
from prefect.workers.base import (
    BaseJobConfiguration,
    BaseVariables,
    BaseWorker,
    BaseWorkerResult,
)

if TYPE_CHECKING:
    from prefect.client.schemas.objects import Flow
    from prefect.client.schemas.responses import DeploymentResponse

if sys.platform == "win32":
    # exit code indicating that the process was terminated by Ctrl+C or Ctrl+Break
    STATUS_CONTROL_C_EXIT = 0xC000013A


def _infrastructure_pid_from_process(process: anyio.abc.Process) -> str:
    hostname = socket.gethostname()
    return f"{hostname}:{process.pid}"


def _parse_infrastructure_pid(infrastructure_pid: str) -> Tuple[str, int]:
    hostname, pid = infrastructure_pid.split(":")
    return hostname, int(pid)


class ProcessJobConfiguration(BaseJobConfiguration):
    stream_output: bool = Field(default=True)
    working_dir: Optional[Path] = Field(default=None)

    @field_validator("working_dir")
    @classmethod
    def validate_command(cls, v):
        return validate_command(v)

    def prepare_for_flow_run(
        self,
        flow_run: "FlowRun",
        deployment: Optional["DeploymentResponse"] = None,
        flow: Optional["Flow"] = None,
    ):
        super().prepare_for_flow_run(flow_run, deployment, flow)

        self.env = {**os.environ, **self.env}
        self.command = (
            f"{get_sys_executable()} -m prefect.engine"
            if self.command == self._base_flow_run_command()
            else self.command
        )

    def _base_flow_run_command(self) -> str:
        """
        Override the base flow run command because enhanced cancellation doesn't
        work with the process worker.
        """
        return "python -m prefect.engine"


class ProcessVariables(BaseVariables):
    stream_output: bool = Field(
        default=True,
        description=(
            "If enabled, workers will stream output from flow run processes to "
            "local standard output."
        ),
    )
    working_dir: Optional[Path] = Field(
        default=None,
        title="Working Directory",
        description=(
            "If provided, workers will open flow run processes within the "
            "specified path as the working directory. Otherwise, a temporary "
            "directory will be created."
        ),
    )


class ProcessWorkerResult(BaseWorkerResult):
    """Contains information about the final state of a completed process"""


class ProcessWorker(BaseWorker):
    type = "process"
    job_configuration = ProcessJobConfiguration
    job_configuration_variables = ProcessVariables

    _description = (
        "Execute flow runs as subprocesses on a worker. Works well for local execution"
        " when first getting started."
    )
    _display_name = "Process"
    _documentation_url = (
        "https://docs.prefect.io/latest/api-ref/prefect/workers/process/"
    )
    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/356e6766a91baf20e1d08bbe16e8b5aaef4d8643-48x48.png"

    async def run(
        self,
        flow_run: FlowRun,
        configuration: ProcessJobConfiguration,
        task_status: Optional[anyio.abc.TaskStatus] = None,
    ):
        command = configuration.command
        if not command:
            command = f"{get_sys_executable()} -m prefect.engine"

        flow_run_logger = self.get_flow_run_logger(flow_run)

        # We must add creationflags to a dict so it is only passed as a function
        # parameter on Windows, because the presence of creationflags causes
        # errors on Unix even if set to None
        kwargs: Dict[str, object] = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

        flow_run_logger.info("Opening process...")

        working_dir_ctx = (
            tempfile.TemporaryDirectory(suffix="prefect")
            if not configuration.working_dir
            else contextlib.nullcontext(configuration.working_dir)
        )
        with working_dir_ctx as working_dir:
            flow_run_logger.debug(
                f"Process running command: {command} in {working_dir}"
            )
            process = await run_process(
                command.split(" "),
                stream_output=configuration.stream_output,
                task_status=task_status,
                task_status_handler=_infrastructure_pid_from_process,
                cwd=working_dir,
                env=configuration.env,
                **kwargs,
            )

        # Use the pid for display if no name was given
        display_name = f" {process.pid}"

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

            flow_run_logger.error(
                f"Process{display_name} exited with status code: {process.returncode}"
                + (f"; {help_message}" if help_message else "")
            )
        else:
            flow_run_logger.info(f"Process{display_name} exited cleanly.")

        return ProcessWorkerResult(
            status_code=process.returncode, identifier=str(process.pid)
        )

    async def kill_infrastructure(
        self,
        infrastructure_pid: str,
        configuration: ProcessJobConfiguration,
        grace_seconds: int = 30,
    ):
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
