import asyncio
import contextlib
import socket
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, Optional, Union

import anyio
import anyio.abc
import sniffio
from pydantic import Field

from prefect.client.schemas import FlowRun
from prefect.deployments import Deployment
from prefect.experimental.workers.base import (
    BaseJobConfiguration,
    BaseVariables,
    BaseWorker,
    BaseWorkerResult,
)
from prefect.utilities.processutils import run_process

if sys.platform == "win32":
    # exit code indicating that the process was terminated by Ctrl+C or Ctrl+Break
    STATUS_CONTROL_C_EXIT = 0xC000013A


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


class ProcessJobConfiguration(BaseJobConfiguration):
    stream_output: bool = Field(template="{{ stream_output }}")
    working_dir: Optional[Union[str, Path]] = Field(template="{{ working_dir }}")


class ProcessVariables(BaseVariables):
    stream_output: bool = True
    working_dir: Optional[Union[str, Path]] = None


class ProcessWorkerResult(BaseWorkerResult):
    """Contains information about the final state of a completed process"""


class ProcessWorker(BaseWorker):
    type = "process"
    job_configuration = ProcessJobConfiguration
    job_configuration_variables = ProcessVariables

    _description = "Worker that executes flow runs within processes."
    _logo_url = "https://images.ctfassets.net/gm98wzqotmnx/39WQhVu4JK40rZWltGqhuC/d15be6189a0cb95949a6b43df00dcb9b/image5.png?h=250"

    async def verify_submitted_deployment(self, deployment: Deployment):
        # TODO: Implement deployment verification for `ProcessWorker`
        pass

    # TODO: Add additional parameters to allow for the customization of behavior
    async def run(
        self,
        flow_run: FlowRun,
        configuration: ProcessJobConfiguration,
        task_status: Optional[anyio.abc.TaskStatus] = None,
    ):
        command = configuration.command
        if not command:
            command = [sys.executable, "-m", "prefect.engine"]

        # We must add creationflags to a dict so it is only passed as a function
        # parameter on Windows, because the presence of creationflags causes
        # errors on Unix even if set to None
        kwargs: Dict[str, object] = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

        _use_threaded_child_watcher()
        self._logger.info("Opening process...")

        working_dir_ctx = (
            tempfile.TemporaryDirectory(suffix="prefect")
            if not configuration.working_dir
            else contextlib.nullcontext(configuration.working_dir)
        )
        with working_dir_ctx as working_dir:
            self._logger.debug(
                f"Process running command: {' '.join(command)} in {working_dir}"
            )
            process = await run_process(
                command,
                stream_output=configuration.stream_output,
                task_status=task_status,
                task_status_handler=_infrastructure_pid_from_process,
                env={"PREFECT__FLOW_RUN_ID": flow_run.id.hex},
                cwd=working_dir,
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

            self._logger.error(
                f"Process{display_name} exited with status code: "
                f"{process.returncode}" + (f"; {help_message}" if help_message else "")
            )
        else:
            self._logger.info(f"Process{display_name} exited cleanly.")

        return ProcessWorkerResult(
            status_code=process.returncode, identifier=str(process.pid)
        )
