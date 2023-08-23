import inspect
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple, Union
from uuid import uuid4

import anyio
import anyio.abc
import pendulum
from pydantic import BaseModel, Field, PrivateAttr, validator

import prefect
from prefect.client.orchestration import PrefectClient, get_client
from prefect.client.schemas.actions import WorkPoolCreate, WorkPoolUpdate
from prefect.client.schemas.filters import (
    FlowRunFilter,
    FlowRunFilterId,
    FlowRunFilterState,
    FlowRunFilterStateName,
    FlowRunFilterStateType,
    WorkPoolFilter,
    WorkPoolFilterName,
)
from prefect.client.schemas.objects import StateType, WorkPool
from prefect.client.utilities import inject_client
from prefect.engine import propose_state
from prefect.exceptions import (
    Abort,
    InfrastructureNotAvailable,
    InfrastructureNotFound,
    ObjectNotFound,
)
from prefect.logging.loggers import PrefectLogAdapter, flow_run_logger, get_logger
from prefect.settings import PREFECT_WORKER_PREFETCH_SECONDS, get_current_settings
from prefect.states import Crashed, Pending, exception_to_failed_state
from prefect.utilities.templating import (
    apply_values,
    resolve_block_document_references,
    resolve_variables,
)

if TYPE_CHECKING:
    from prefect.client.schemas.objects import Flow, FlowRun
    from prefect.client.schemas.responses import (
        DeploymentResponse,
        WorkerFlowRunResponse,
    )

import asyncio
import contextlib
import os
import signal
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

import anyio
import anyio.abc
import sniffio

from prefect.utilities.filesystem import relative_path_to_current_platform
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


def prepare_environment(flow_run: "FlowRun") -> Dict[str, str]:
    env = get_current_settings().to_environment_variables(exclude_unset=True)
    env.update({"PREFECT__FLOW_RUN_ID": flow_run.id.hex})
    env.update(**os.environ)  # is this really necessary??
    return env


class ProcessWorkerResult(BaseModel):
    identifier: str
    status_code: int

    def __bool__(self):
        return self.status_code == 0


class Runner:
    def __init__(
        self,
        work_pool_name: str,
        name: Optional[str] = None,
        prefetch_seconds: Optional[float] = None,
        create_pool_if_not_found: bool = True,
        limit: Optional[int] = None,
    ):
        """
        Responsible for managing the execution of remotely initiated flow runs.

        Args:
            name: The name of the worker. If not provided, a random one
                will be generated. If provided, it cannot contain '/' or '%'.
                The name is used to identify the worker in the UI; if two
                processes have the same name, they will be treated as the same
                worker.
            work_pool_name: The name of the work pool to poll.
            prefetch_seconds: The number of seconds to prefetch flow runs for.
            create_pool_if_not_found: Whether to create the work pool
                if it is not found. Defaults to `True`, but can be set to `False` to
                ensure that work pools are not created accidentally.
            limit: The maximum number of flow runs this worker should be running at
                a given time.
        """
        if name and ("/" in name or "%" in name):
            raise ValueError("Worker name cannot contain '/' or '%'")
        self.name = name or f"{self.__class__.__name__} {uuid4()}"
        self._logger = get_logger()

        self.is_setup = False
        self._create_pool_if_not_found = create_pool_if_not_found
        self._work_pool_name = work_pool_name

        self._prefetch_seconds: float = (
            prefetch_seconds or PREFECT_WORKER_PREFETCH_SECONDS.value()
        )

        self._work_pool: Optional[WorkPool] = None
        self._runs_task_group: Optional[anyio.abc.TaskGroup] = None
        self._client: Optional[PrefectClient] = None
        self._last_polled_time: pendulum.DateTime = pendulum.now("utc")
        self._limit = limit
        self._limiter: Optional[anyio.CapacityLimiter] = None
        self._submitting_flow_run_ids = set()
        self._cancelling_flow_run_ids = set()
        self._scheduled_task_scopes = set()

    def get_flow_run_logger(self, flow_run: "FlowRun") -> PrefectLogAdapter:
        return flow_run_logger(flow_run=flow_run).getChild(
            "worker",
            extra={
                "worker_name": self.name,
            },
        )

    async def run(
        self,
        flow_run: FlowRun,
        task_status: Optional[anyio.abc.TaskStatus] = None,
    ):
        command = f"{sys.executable} -m prefect.engine"

        flow_run_logger = self.get_flow_run_logger(flow_run)

        # We must add creationflags to a dict so it is only passed as a function
        # parameter on Windows, because the presence of creationflags causes
        # errors on Unix even if set to None
        kwargs: Dict[str, object] = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

        _use_threaded_child_watcher()
        flow_run_logger.info("Opening process...")

        # TODO: expose working dir as configurable on the runner
        with tempfile.TemporaryDirectory(suffix="prefect") as working_dir:
            flow_run_logger.debug(
                f"Process running command: {command} in {working_dir}"
            )
            process = await run_process(
                command.split(" "),
                stream_output=True,
                task_status=task_status,
                task_status_handler=_infrastructure_pid_from_process,
                cwd=working_dir,
                env=prepare_environment(flow_run),
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
        grace_seconds: int = 30,
    ):
        hostname, pid = infrastructure_pid.split(":")
        pid = int(pid)

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

    @classmethod
    def __dispatch_key__(cls):
        if cls.__name__ == "BaseWorker":
            return None  # The base class is abstract
        return cls.type

    async def setup(self):
        """Prepares the worker to run."""
        self._logger.debug("Setting up worker...")
        self._runs_task_group = anyio.create_task_group()
        self._limiter = (
            anyio.CapacityLimiter(self._limit) if self._limit is not None else None
        )
        self._client = get_client()
        await self._client.__aenter__()
        await self._runs_task_group.__aenter__()

        self.is_setup = True

    async def teardown(self, *exc_info):
        """Cleans up resources after the worker is stopped."""
        self._logger.debug("Tearing down worker...")
        self.is_setup = False
        for scope in self._scheduled_task_scopes:
            scope.cancel()
        if self._runs_task_group:
            await self._runs_task_group.__aexit__(*exc_info)
        if self._client:
            await self._client.__aexit__(*exc_info)
        self._runs_task_group = None
        self._client = None

    def is_worker_still_polling(self, query_interval_seconds: int) -> bool:
        """
        This method is invoked by a webserver healthcheck handler
        and returns a boolean indicating if the worker has recorded a
        scheduled flow run poll within a variable amount of time.

        The `query_interval_seconds` is the same value that is used by
        the loop services - we will evaluate if the _last_polled_time
        was within that interval x 30 (so 10s -> 5m)

        The instance property `self._last_polled_time`
        is currently set/updated in `get_and_submit_flow_runs()`
        """
        threshold_seconds = query_interval_seconds * 30

        seconds_since_last_poll = (
            pendulum.now("utc") - self._last_polled_time
        ).in_seconds()

        is_still_polling = seconds_since_last_poll <= threshold_seconds

        if not is_still_polling:
            self._logger.error(
                f"Worker has not polled in the last {seconds_since_last_poll} seconds "
                "and should be restarted"
            )

        return is_still_polling

    async def get_and_submit_flow_runs(self):
        runs_response = await self._get_scheduled_flow_runs()

        self._last_polled_time = pendulum.now("utc")

        return await self._submit_scheduled_flow_runs(flow_run_response=runs_response)

    async def check_for_cancelled_flow_runs(self):
        if not self.is_setup:
            raise RuntimeError(
                "Worker is not set up. Please make sure you are running this worker "
                "as an async context manager."
            )

        self._logger.debug("Checking for cancelled flow runs...")

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
            await self.kill_infrastructure(
                infrastructure_pid=flow_run.infrastructure_pid
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
            await self._mark_flow_run_as_cancelled(flow_run)
            run_logger.info(f"Cancelled flow run '{flow_run.id}'!")

    async def _send_runner_heartbeat(self):
        """
        Will need to reconsider how to heartbeat a runner for crash detection.
        """
        pass

    async def sync_with_backend(self):
        """
        Updates the worker's local information about it's current work pool and
        queues. Sends a worker heartbeat to the API.
        """
        await self._send_runner_heartbeat()

        self._logger.debug("Worker synchronized with the Prefect API server.")

    async def _get_scheduled_flow_runs(
        self,
    ) -> List["WorkerFlowRunResponse"]:
        """
        Retrieve scheduled flow runs from the work pool's queues.
        """
        scheduled_before = pendulum.now("utc").add(seconds=int(self._prefetch_seconds))
        self._logger.debug(
            f"Querying for flow runs scheduled before {scheduled_before}"
        )
        try:
            scheduled_flow_runs = (
                await self._client.get_scheduled_flow_runs_for_work_pool(
                    work_pool_name=self._work_pool_name,
                    scheduled_before=scheduled_before,
                )
            )
            self._logger.debug(
                f"Discovered {len(scheduled_flow_runs)} scheduled_flow_runs"
            )
            return scheduled_flow_runs
        except ObjectNotFound:
            # the pool doesn't exist; it will be created on the next
            # heartbeat (or an appropriate warning will be logged)
            return []

    async def _submit_scheduled_flow_runs(
        self, flow_run_response: List["WorkerFlowRunResponse"]
    ) -> List["FlowRun"]:
        """
        Takes a list of WorkerFlowRunResponses and submits the referenced flow runs
        for execution by the worker.
        """
        submittable_flow_runs = [entry.flow_run for entry in flow_run_response]
        submittable_flow_runs.sort(key=lambda run: run.next_scheduled_start_time)
        for flow_run in submittable_flow_runs:
            if flow_run.id in self._submitting_flow_run_ids:
                continue

            try:
                if self._limiter:
                    self._limiter.acquire_on_behalf_of_nowait(flow_run.id)
            except anyio.WouldBlock:
                self._logger.info(
                    f"Flow run limit reached; {self._limiter.borrowed_tokens} flow runs"
                    " in progress."
                )
                break
            else:
                run_logger = self.get_flow_run_logger(flow_run)
                run_logger.info(
                    f"Worker '{self.name}' submitting flow run '{flow_run.id}'"
                )
                self._submitting_flow_run_ids.add(flow_run.id)
                self._runs_task_group.start_soon(
                    self._submit_run,
                    flow_run,
                )

        return list(
            filter(
                lambda run: run.id in self._submitting_flow_run_ids,
                submittable_flow_runs,
            )
        )

    async def _check_flow_run(self, flow_run: "FlowRun") -> None:
        """
        Performs a check on a submitted flow run to warn the user if the flow run
        was created from a deployment with a storage block.
        """
        if flow_run.deployment_id:
            deployment = await self._client.read_deployment(flow_run.deployment_id)
            if deployment.storage_document_id:
                raise ValueError(
                    f"Flow run {flow_run.id!r} was created from deployment"
                    f" {deployment.name!r} which is configured with a storage block."
                    " Workers currently only support local storage. Please use an"
                    " agent to execute this flow run."
                )

    async def _submit_run(self, flow_run: "FlowRun") -> None:
        """
        Submits a given flow run for execution by the worker.
        """
        run_logger = self.get_flow_run_logger(flow_run)

        try:
            await self._check_flow_run(flow_run)
        except (ValueError, ObjectNotFound):
            self._logger.exception(
                (
                    "Flow run %s did not pass checks and will not be submitted for"
                    " execution"
                ),
                flow_run.id,
            )
            self._submitting_flow_run_ids.remove(flow_run.id)
            return

        ready_to_submit = await self._propose_pending_state(flow_run)

        if ready_to_submit:
            readiness_result = await self._runs_task_group.start(
                self._submit_run_and_capture_errors, flow_run
            )

            if readiness_result and not isinstance(readiness_result, Exception):
                try:
                    await self._client.update_flow_run(
                        flow_run_id=flow_run.id,
                        infrastructure_pid=str(readiness_result),
                    )
                except Exception:
                    run_logger.exception(
                        "An error occurred while setting the `infrastructure_pid` on "
                        f"flow run {flow_run.id!r}. The flow run will "
                        "not be cancellable."
                    )

            run_logger.info(f"Completed submission of flow run '{flow_run.id}'")

        else:
            # If the run is not ready to submit, release the concurrency slot
            if self._limiter:
                self._limiter.release_on_behalf_of(flow_run.id)

        self._submitting_flow_run_ids.remove(flow_run.id)

    async def _submit_run_and_capture_errors(
        self, flow_run: "FlowRun", task_status: anyio.abc.TaskStatus = None
    ) -> Union[ProcessWorkerResult, Exception]:
        run_logger = self.get_flow_run_logger(flow_run)

        try:
            result = await self.run(
                flow_run=flow_run,
                task_status=task_status,
            )
        except Exception as exc:
            if not task_status._future.done():
                # This flow run was being submitted and did not start successfully
                run_logger.exception(
                    f"Failed to submit flow run '{flow_run.id}' to infrastructure."
                )
                # Mark the task as started to prevent agent crash
                task_status.started(exc)
                await self._propose_crashed_state(
                    flow_run, "Flow run could not be submitted to infrastructure"
                )
            else:
                run_logger.exception(
                    f"An error occurred while monitoring flow run '{flow_run.id}'. "
                    "The flow run will not be marked as failed, but an issue may have "
                    "occurred."
                )
            return exc
        finally:
            if self._limiter:
                self._limiter.release_on_behalf_of(flow_run.id)

        if not task_status._future.done():
            run_logger.error(
                f"Infrastructure returned without reporting flow run '{flow_run.id}' "
                "as started or raising an error. This behavior is not expected and "
                "generally indicates improper implementation of infrastructure. The "
                "flow run will not be marked as failed, but an issue may have occurred."
            )
            # Mark the task as started to prevent agent crash
            task_status.started()

        if result.status_code != 0:
            await self._propose_crashed_state(
                flow_run,
                (
                    "Flow run infrastructure exited with non-zero status code"
                    f" {result.status_code}."
                ),
            )

        return result

    def get_status(self):
        """
        Retrieves the status of the current worker including its name, current worker
        pool, the work pool queues it is polling, and its local settings.
        """
        return {
            "name": self.name,
            "settings": {
                "prefetch_seconds": self._prefetch_seconds,
            },
        }

    async def _propose_pending_state(self, flow_run: "FlowRun") -> bool:
        run_logger = self.get_flow_run_logger(flow_run)
        state = flow_run.state
        try:
            state = await propose_state(
                self._client, Pending(), flow_run_id=flow_run.id
            )
        except Abort as exc:
            run_logger.info(
                (
                    f"Aborted submission of flow run '{flow_run.id}'. "
                    f"Server sent an abort signal: {exc}"
                ),
            )
            return False
        except Exception:
            run_logger.exception(
                f"Failed to update state of flow run '{flow_run.id}'",
            )
            return False

        if not state.is_pending():
            run_logger.info(
                (
                    f"Aborted submission of flow run '{flow_run.id}': "
                    f"Server returned a non-pending state {state.type.value!r}"
                ),
            )
            return False

        return True

    async def _propose_failed_state(self, flow_run: "FlowRun", exc: Exception) -> None:
        run_logger = self.get_flow_run_logger(flow_run)
        try:
            await propose_state(
                self._client,
                await exception_to_failed_state(message="Submission failed.", exc=exc),
                flow_run_id=flow_run.id,
            )
        except Abort:
            # We've already failed, no need to note the abort but we don't want it to
            # raise in the agent process
            pass
        except Exception:
            run_logger.error(
                f"Failed to update state of flow run '{flow_run.id}'",
                exc_info=True,
            )

    async def _propose_crashed_state(self, flow_run: "FlowRun", message: str) -> None:
        run_logger = self.get_flow_run_logger(flow_run)
        try:
            state = await propose_state(
                self._client,
                Crashed(message=message),
                flow_run_id=flow_run.id,
            )
        except Abort:
            # Flow run already marked as failed
            pass
        except Exception:
            run_logger.exception(f"Failed to update state of flow run '{flow_run.id}'")
        else:
            if state.is_crashed():
                run_logger.info(
                    f"Reported flow run '{flow_run.id}' as crashed: {message}"
                )

    async def _mark_flow_run_as_cancelled(
        self, flow_run: "FlowRun", state_updates: Optional[dict] = None
    ) -> None:
        state_updates = state_updates or {}
        state_updates.setdefault("name", "Cancelled")
        state_updates.setdefault("type", StateType.CANCELLED)
        state = flow_run.state.copy(update=state_updates)

        await self._client.set_flow_run_state(flow_run.id, state, force=True)

        # Do not remove the flow run from the cancelling set immediately because
        # the API caches responses for the `read_flow_runs` and we do not want to
        # duplicate cancellations.
        await self._schedule_task(
            60 * 10, self._cancelling_flow_run_ids.remove, flow_run.id
        )

    async def _schedule_task(self, __in_seconds: int, fn, *args, **kwargs):
        """
        Schedule a background task to start after some time.

        These tasks will be run immediately when the worker exits instead of waiting.

        The function may be async or sync. Async functions will be awaited.
        """

        async def wrapper(task_status):
            # If we are shutting down, do not sleep; otherwise sleep until the scheduled
            # time or shutdown
            if self.is_setup:
                with anyio.CancelScope() as scope:
                    self._scheduled_task_scopes.add(scope)
                    task_status.started()
                    await anyio.sleep(__in_seconds)

                self._scheduled_task_scopes.remove(scope)
            else:
                task_status.started()

            result = fn(*args, **kwargs)
            if inspect.iscoroutine(result):
                await result

        await self._runs_task_group.start(wrapper)

    async def __aenter__(self):
        self._logger.debug("Entering worker context...")
        await self.setup()
        return self

    async def __aexit__(self, *exc_info):
        self._logger.debug("Exiting worker context...")
        await self.teardown(*exc_info)

    def __repr__(self):
        return f"Worker(pool={self._work_pool_name!r}, name={self.name!r})"
