import asyncio
import socket
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, Optional, Tuple, Union

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


def _parse_infrastructure_pid(infrastructure_pid: str) -> Tuple[str, int]:
    hostname, pid = infrastructure_pid.split(":")
    return hostname, int(pid)


PROCESS_WORKER_BASE_TEMPLATE = {
    "job_configuration": {
        "command": "{{ command }}",
        "steam_output": "{{ steam_output }}",
        "working_dir": "{{ working_dir }}",
    },
    "variables": {
        "command": {"type": "array", "items": {"type": "string"}, "default": []},
        "steam_output": {"type": "boolean", "default": True},
        "working_dir": {
            "type": "string",
            "default": "",
        },
    },
    "required_variables": [],
}


class ProcessWorkerResult(BaseWorkerResult):
    """Contains information about the final state of a completed process"""


class ProcessJobConfiguration(BaseJobConfiguration):
    stream_output: bool = Field(template="{{ stream_output }}")
    working_dir: Union[str, Path, None] = Field(template="{{ working_dir }}")


class ProcessVariables(BaseVariables):
    stream_output: bool
    working_dir: Union[str, Path, None]


class ProcessWorker(BaseWorker):
    type = "process"
    job_configuration = ProcessJobConfiguration
    job_configuration_variables = ProcessVariables

    async def verify_submitted_deployment(self, deployment: Deployment):
        return True

    async def run(
        self, flow_run: FlowRun, task_status: Optional[anyio.abc.TaskStatus] = None
    ):

        deployment = await self._client.read_deployment(flow_run.deployment_id)
        configuration = ProcessJobConfiguration.from_configuration(
            base_template=self.worker_pool.base_job_template,
            deployment_overrides=deployment.infra_overrides,
        )

        command = configuration.command
        if not command:
            command = [sys.executable, "-m", "prefect.engine"]
        _use_threaded_child_watcher()
        self.logger.info("Opening process...")
        with tempfile.TemporaryDirectory(suffix="prefect") as working_dir:
            self.logger.debug(
                f"Process running command: {' '.join(command)} in {working_dir}"
            )

            # We must add creationflags to a dict so it is only passed as a function
            # parameter on Windows, because the presence of creationflags causes
            # errors on Unix even if set to None
            kwargs: Dict[str, object] = {}
            if sys.platform == "win32":
                kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

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

            self.logger.error(
                f"Process{display_name} exited with status code: "
                f"{process.returncode}" + (f"; {help_message}" if help_message else "")
            )
        else:
            self.logger.info(f"Process{display_name} exited cleanly.")

        return ProcessWorkerResult(
            status_code=process.returncode, identifier=str(process.pid)
        )
