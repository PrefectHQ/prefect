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
import threading
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict, Optional, Tuple

import anyio
import anyio.abc
from pydantic import Field, field_validator

from prefect._internal.schemas.validators import validate_command
from prefect.client.schemas import FlowRun
from prefect.client.schemas.filters import (
    FlowRunFilter,
    FlowRunFilterId,
    FlowRunFilterState,
    FlowRunFilterStateName,
    FlowRunFilterStateType,
    WorkPoolFilter,
    WorkPoolFilterName,
    WorkQueueFilter,
    WorkQueueFilterName,
)
from prefect.client.schemas.objects import StateType
from prefect.events.utilities import emit_event
from prefect.exceptions import (
    InfrastructureNotAvailable,
    InfrastructureNotFound,
    ObjectNotFound,
)
from prefect.settings import PREFECT_WORKER_QUERY_SECONDS
from prefect.utilities.processutils import get_sys_executable, run_process
from prefect.utilities.services import critical_service_loop
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
    _documentation_url = "https://docs.prefect.io/latest/get-started/quickstart"
    _logo_url = "https://cdn.sanity.io/images/3ugk85nk/production/356e6766a91baf20e1d08bbe16e8b5aaef4d8643-48x48.png"

    async def start(
        self,
        run_once: bool = False,
        with_healthcheck: bool = False,
        printer: Callable[..., None] = print,
    ):
        """
        Starts the worker and runs the main worker loops.

        By default, the worker will run loops to poll for scheduled/cancelled flow
        runs and sync with the Prefect API server.

        If `run_once` is set, the worker will only run each loop once and then return.

        If `with_healthcheck` is set, the worker will start a healthcheck server which
        can be used to determine if the worker is still polling for flow runs and restart
        the worker if necessary.

        Args:
            run_once: If set, the worker will only run each loop once then return.
            with_healthcheck: If set, the worker will start a healthcheck server.
            printer: A `print`-like function where logs will be reported.
        """
        healthcheck_server = None
        healthcheck_thread = None
        try:
            async with self as worker:
                # wait for an initial heartbeat to configure the worker
                await worker.sync_with_backend()
                # schedule the scheduled flow run polling loop
                async with anyio.create_task_group() as loops_task_group:
                    loops_task_group.start_soon(
                        partial(
                            critical_service_loop,
                            workload=self.get_and_submit_flow_runs,
                            interval=PREFECT_WORKER_QUERY_SECONDS.value(),
                            run_once=run_once,
                            jitter_range=0.3,
                            backoff=4,  # Up to ~1 minute interval during backoff
                        )
                    )
                    # schedule the sync loop
                    loops_task_group.start_soon(
                        partial(
                            critical_service_loop,
                            workload=self.sync_with_backend,
                            interval=self.heartbeat_interval_seconds,
                            run_once=run_once,
                            jitter_range=0.3,
                            backoff=4,
                        )
                    )
                    loops_task_group.start_soon(
                        partial(
                            critical_service_loop,
                            workload=self.check_for_cancelled_flow_runs,
                            interval=PREFECT_WORKER_QUERY_SECONDS.value() * 2,
                            run_once=run_once,
                            jitter_range=0.3,
                            backoff=4,
                        )
                    )

                    self._started_event = await self._emit_worker_started_event()

                    if with_healthcheck:
                        from prefect.workers.server import build_healthcheck_server

                        # we'll start the ASGI server in a separate thread so that
                        # uvicorn does not block the main thread
                        healthcheck_server = build_healthcheck_server(
                            worker=worker,
                            query_interval_seconds=PREFECT_WORKER_QUERY_SECONDS.value(),
                        )
                        healthcheck_thread = threading.Thread(
                            name="healthcheck-server-thread",
                            target=healthcheck_server.run,
                            daemon=True,
                        )
                        healthcheck_thread.start()
                    printer(f"Worker {worker.name!r} started!")
        finally:
            if healthcheck_server and healthcheck_thread:
                self._logger.debug("Stopping healthcheck server...")
                healthcheck_server.should_exit = True
                healthcheck_thread.join()
                self._logger.debug("Healthcheck server stopped.")

        printer(f"Worker {worker.name!r} stopped!")

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

    async def kill_process(
        self,
        infrastructure_pid: str,
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

    async def check_for_cancelled_flow_runs(self):
        if not self.is_setup:
            raise RuntimeError(
                "Worker is not set up. Please make sure you are running this worker "
                "as an async context manager."
            )

        self._logger.debug("Checking for cancelled flow runs...")

        work_queue_filter = (
            WorkQueueFilter(name=WorkQueueFilterName(any_=list(self._work_queues)))
            if self._work_queues
            else None
        )

        named_cancelling_flow_runs = await self._client.read_flow_runs(
            flow_run_filter=FlowRunFilter(
                state=FlowRunFilterState(
                    type=FlowRunFilterStateType(any_=[StateType.CANCELLED]),
                    name=FlowRunFilterStateName(any_=["Cancelling"]),
                ),
                # Avoid duplicate cancellation calls
                id=FlowRunFilterId(not_any_=list(self._cancelling_flow_run_ids)),
            ),
            work_pool_filter=WorkPoolFilter(
                name=WorkPoolFilterName(any_=[self._work_pool_name])
            ),
            work_queue_filter=work_queue_filter,
        )

        typed_cancelling_flow_runs = await self._client.read_flow_runs(
            flow_run_filter=FlowRunFilter(
                state=FlowRunFilterState(
                    type=FlowRunFilterStateType(any_=[StateType.CANCELLING]),
                ),
                # Avoid duplicate cancellation calls
                id=FlowRunFilterId(not_any_=list(self._cancelling_flow_run_ids)),
            ),
            work_pool_filter=WorkPoolFilter(
                name=WorkPoolFilterName(any_=[self._work_pool_name])
            ),
            work_queue_filter=work_queue_filter,
        )

        cancelling_flow_runs = named_cancelling_flow_runs + typed_cancelling_flow_runs

        if cancelling_flow_runs:
            self._logger.info(
                f"Found {len(cancelling_flow_runs)} flow runs awaiting cancellation."
            )

        for flow_run in cancelling_flow_runs:
            self._cancelling_flow_run_ids.add(flow_run.id)
            self._runs_task_group.start_soon(self.cancel_run, flow_run)

        return cancelling_flow_runs

    async def cancel_run(self, flow_run: "FlowRun"):
        run_logger = self.get_flow_run_logger(flow_run)

        try:
            configuration = await self._get_configuration(flow_run)
        except ObjectNotFound:
            self._logger.warning(
                f"Flow run {flow_run.id!r} cannot be cancelled by this worker:"
                f" associated deployment {flow_run.deployment_id!r} does not exist."
            )
            await self._mark_flow_run_as_cancelled(
                flow_run,
                state_updates={
                    "message": (
                        "This flow run is missing infrastructure configuration information"
                        " and cancellation cannot be guaranteed."
                    )
                },
            )
            return
        else:
            if configuration.is_using_a_runner:
                self._logger.info(
                    f"Skipping cancellation because flow run {str(flow_run.id)!r} is"
                    " using enhanced cancellation. A dedicated runner will handle"
                    " cancellation."
                )
                return

        if not flow_run.infrastructure_pid:
            run_logger.error(
                f"Flow run '{flow_run.id}' does not have an infrastructure pid"
                " attached. Cancellation cannot be guaranteed."
            )
            await self._mark_flow_run_as_cancelled(
                flow_run,
                state_updates={
                    "message": (
                        "This flow run is missing infrastructure tracking information"
                        " and cancellation cannot be guaranteed."
                    )
                },
            )
            return

        try:
            await self.kill_process(
                infrastructure_pid=flow_run.infrastructure_pid,
            )
        except NotImplementedError:
            self._logger.error(
                f"Worker type {self.type!r} does not support killing created "
                "infrastructure. Cancellation cannot be guaranteed."
            )
        except InfrastructureNotFound as exc:
            self._logger.warning(f"{exc} Marking flow run as cancelled.")
            await self._mark_flow_run_as_cancelled(flow_run)
        except InfrastructureNotAvailable as exc:
            self._logger.warning(f"{exc} Flow run cannot be cancelled by this worker.")
        except Exception:
            run_logger.exception(
                "Encountered exception while killing infrastructure for flow run "
                f"'{flow_run.id}'. Flow run may not be cancelled."
            )
            # We will try again on generic exceptions
            self._cancelling_flow_run_ids.remove(flow_run.id)
            return
        else:
            self._emit_flow_run_cancelled_event(
                flow_run=flow_run, configuration=configuration
            )
            await self._mark_flow_run_as_cancelled(flow_run)
            run_logger.info(f"Cancelled flow run '{flow_run.id}'!")

    def _emit_flow_run_cancelled_event(
        self, flow_run: "FlowRun", configuration: BaseJobConfiguration
    ):
        related = self._event_related_resources(configuration=configuration)

        for resource in related:
            if resource.role == "flow-run":
                resource["prefect.infrastructure.identifier"] = str(
                    flow_run.infrastructure_pid
                )

        emit_event(
            event="prefect.worker.cancelled-flow-run",
            resource=self._event_resource(),
            related=related,
        )
