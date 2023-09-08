"""
Runners are responsible for managing the execution of deployments created and managed by
either `flow.serve` or the `serve` utility.

Example:
    ```python
    import time
    from prefect import flow, serve


    @flow
    def slow_flow(sleep: int = 60):
        "Sleepy flow - sleeps the provided amount of time (in seconds)."
        time.sleep(sleep)


    @flow
    def fast_flow():
        "Fastest flow this side of the Mississippi."
        return


    if __name__ == "__main__":
        slow_deploy = slow_flow.to_deployment(name="sleeper", interval=45)
        fast_deploy = fast_flow.to_deployment(name="fast")

        # serve generates a Runner instance
        serve(slow_deploy, fast_deploy)
    ```

"""
import datetime
import inspect
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Set, Union
from uuid import UUID, uuid4

import anyio
import anyio.abc
import pendulum
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table

from prefect.client.orchestration import get_client
from prefect.client.schemas.filters import (
    DeploymentFilter,
    DeploymentFilterId,
    FlowRunFilter,
    FlowRunFilterId,
    FlowRunFilterNextScheduledStartTime,
    FlowRunFilterState,
    FlowRunFilterStateName,
    FlowRunFilterStateType,
)
from prefect.client.schemas.objects import StateType
from prefect.client.schemas.schedules import SCHEDULE_TYPES
from prefect.deployments.runner import RunnerDeployment
from prefect.engine import propose_state
from prefect.events.schemas import DeploymentTrigger
from prefect.exceptions import (
    Abort,
)
from prefect.flows import Flow
from prefect.logging.loggers import PrefectLogAdapter, flow_run_logger, get_logger
from prefect.settings import (
    PREFECT_API_URL,
    PREFECT_RUNNER_PROCESS_LIMIT,
    PREFECT_UI_URL,
    get_current_settings,
)
from prefect.states import Crashed, Pending, exception_to_failed_state
from prefect.utilities.asyncutils import sync_compatible
from prefect.utilities.services import critical_service_loop

if TYPE_CHECKING:
    from prefect.client.schemas.objects import FlowRun

import asyncio
import os
import signal
import subprocess
import sys

import anyio
import anyio.abc
import sniffio

from prefect.utilities.processutils import run_process

__all__ = ["Runner", "serve"]


class Runner:
    def __init__(
        self,
        name: Optional[str] = None,
        query_seconds: float = 10,
        prefetch_seconds: float = 10,
        limit: Optional[int] = None,
        pause_on_shutdown: bool = True,
    ):
        """
        Responsible for managing the execution of remotely initiated flow runs.

        Args:
            name: The name of the runner. If not provided, a random one
                will be generated. If provided, it cannot contain '/' or '%'.
            query_seconds: The number of seconds to wait between querying for
                scheduled flow runs.
            prefetch_seconds: The number of seconds to prefetch flow runs for.
            limit: The maximum number of flow runs this runner should be running at
            pause_on_shutdown: A boolean for whether or not to automatically pause
                deployment schedules on shutdown; defaults to `True`

        Examples:
            Set up a Runner to manage the execute of scheduled flow runs for two flows:
                ```python
                from prefect import flow, Runner

                @flow
                def hello_flow(name):
                    print(f"hello {name}")

                @flow
                def goodbye_flow(name):
                    print(f"goodbye {name}")

                if __name__ == "__main__"
                    runner = Runner(name="my-runner")

                    # Will be runnable via the API
                    runner.add_flow(hello_flow)

                    # Run on a cron schedule
                    runner.add_flow(goodbye_flow, schedule={"cron": "0 * * * *"})

                    runner.start()
                ```
        """
        if name and ("/" in name or "%" in name):
            raise ValueError("Runner name cannot contain '/' or '%'")
        self.name = Path(name).stem if name is not None else f"runner-{uuid4()}"
        self._logger = get_logger("runner")

        self.started = False
        self.pause_on_shutdown = pause_on_shutdown
        self.limit = limit or PREFECT_RUNNER_PROCESS_LIMIT.value()
        self._query_seconds = query_seconds
        self._prefetch_seconds = prefetch_seconds

        self._runs_task_group: anyio.abc.TaskGroup = anyio.create_task_group()
        self._loops_task_group: anyio.abc.TaskGroup = anyio.create_task_group()

        self._limiter: Optional[anyio.CapacityLimiter] = anyio.CapacityLimiter(
            self.limit
        )
        self._client = get_client()
        self._submitting_flow_run_ids = set()
        self._cancelling_flow_run_ids = set()
        self._scheduled_task_scopes = set()
        self._deployment_ids: Set[UUID] = set()
        self._flow_run_process_map = dict()

    @sync_compatible
    async def add_deployment(
        self,
        deployment: RunnerDeployment,
    ) -> UUID:
        """
        Registers the deployment with the Prefect API and will monitor for work once
        the runner is started.

        Args:
            deployment: A deployment for the runner to register.
        """
        deployment_id = await deployment.apply()
        self._deployment_ids.add(deployment_id)

        return deployment_id

    @sync_compatible
    async def add_flow(
        self,
        flow: Flow,
        name: str = None,
        interval: Optional[Union[int, float, datetime.timedelta]] = None,
        cron: Optional[str] = None,
        rrule: Optional[str] = None,
        schedule: Optional[SCHEDULE_TYPES] = None,
        parameters: Optional[dict] = None,
        triggers: Optional[List[DeploymentTrigger]] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        version: Optional[str] = None,
    ) -> UUID:
        """
        Provides a flow to the runner to be run based on the provided configuration.

        Will create a deployment for the provided flow and register the deployment
        with the runner.

        Args:
            flow: A flow for the runner to run.
            name: The name to give the created deployment. Will default to the name
                of the runner.
            interval: An interval on which to execute the current flow. Accepts either a number
                or a timedelta object. If a number is given, it will be interpreted as seconds.
            cron: A cron schedule of when to execute runs of this flow.
            rrule: An rrule schedule of when to execute runs of this flow.
            schedule: A schedule object of when to execute runs of this flow. Used for
                advanced scheduling options like timezone.
            triggers: A list of triggers that should kick of a run of this flow.
            parameters: A dictionary of default parameter values to pass to runs of this flow.
            description: A description for the created deployment. Defaults to the flow's
                description if not provided.
            tags: A list of tags to associate with the created deployment for organizational
                purposes.
            version: A version for the created deployment. Defaults to the flow's version.
        """
        # TODO: expose a filesystem interface with hot reloading
        # will need to create a separate method for deployment creation
        api = PREFECT_API_URL.value()
        if any([interval, cron, rrule]) and not api:
            self._logger.warning(
                "Cannot schedule flows on an ephemeral server; run `prefect server"
                " start` to start the scheduler."
            )
        name = self.name if name is None else name

        deployment = flow.to_deployment(
            name=name,
            interval=interval,
            cron=cron,
            rrule=rrule,
            schedule=schedule,
            triggers=triggers,
            parameters=parameters,
            description=description,
            tags=tags,
            version=version,
        )
        return await self.add_deployment(deployment)

    @sync_compatible
    async def start(self, run_once: bool = False):
        """
        Starts a runner.

        The runner will begin monitoring for and executing any scheduled work for all added flows.

        Args:
            run_once: If True, the runner will through one query loop and then exit.

        Examples:
            Initialize a Runner, add two flows, and serve them by starting the Runner:

            ```python
            from prefect import flow, Runner

            @flow
            def hello_flow(name):
                print(f"hello {name}")

            @flow
            def goodbye_flow(name):
                print(f"goodbye {name}")

            if __name__ == "__main__"
                runner = Runner(name="my-runner")

                # Will be runnable via the API
                runner.add_flow(hello_flow)

                # Run on a cron schedule
                runner.add_flow(goodbye_flow, schedule={"cron": "0 * * * *"})

                runner.start()
            ```
        """
        async with self as runner:
            async with self._loops_task_group as tg:
                tg.start_soon(
                    partial(
                        critical_service_loop,
                        workload=runner._get_and_submit_flow_runs,
                        interval=self._query_seconds,
                        run_once=run_once,
                        jitter_range=0.3,
                    )
                )
                tg.start_soon(
                    partial(
                        critical_service_loop,
                        workload=runner._check_for_cancelled_flow_runs,
                        interval=self._query_seconds * 2,
                        run_once=run_once,
                        jitter_range=0.3,
                    )
                )

    def stop(self):
        """Stops the runner's polling cycle."""
        if not self.started:
            raise RuntimeError(
                "Runner has not yet started. Please start the runner by calling"
                " .start()"
            )
        self._loops_task_group.cancel_scope.cancel()

    async def execute_flow_run(self, flow_run_id: UUID):
        """
        Executes a single flow run with the given ID.

        Execution will wait to monitor for cancellation requests. Exits once
        the flow run process has exited.
        """
        async with self:
            if not self._acquire_limit_slot(flow_run_id):
                return

            async with anyio.create_task_group() as tg:
                with anyio.CancelScope():
                    self._submitting_flow_run_ids.add(flow_run_id)
                    flow_run = await self._client.read_flow_run(flow_run_id)

                    pid = await self._runs_task_group.start(
                        self._submit_run_and_capture_errors, flow_run
                    )

                    self._flow_run_process_map[flow_run.id] = pid

                    workload = partial(
                        self._check_for_cancelled_flow_runs,
                        on_nothing_to_watch=tg.cancel_scope.cancel,
                    )

                    tg.start_soon(
                        partial(
                            critical_service_loop,
                            workload=workload,
                            interval=self._query_seconds,
                            jitter_range=0.3,
                        )
                    )

    def _get_flow_run_logger(self, flow_run: "FlowRun") -> PrefectLogAdapter:
        return flow_run_logger(flow_run=flow_run).getChild(
            "runner",
            extra={
                "runner_name": self.name,
            },
        )

    async def _run_process(
        self,
        flow_run: "FlowRun",
        task_status: Optional[anyio.abc.TaskStatus] = None,
    ):
        """
        Runs the given flow run in a subprocess.

        Args:
            flow_run: Flow run to execute via process. The ID of this flow run
                is stored in the PREFECT__FLOW_RUN_ID environment variable to
                allow the engine to retrieve the corresponding flow's code and
                begin execution.
            task_status: anyio task status used to send a message to the caller
                than the flow run process has started.
        """
        command = f"{sys.executable} -m prefect.engine"

        flow_run_logger = self._get_flow_run_logger(flow_run)

        # We must add creationflags to a dict so it is only passed as a function
        # parameter on Windows, because the presence of creationflags causes
        # errors on Unix even if set to None
        kwargs: Dict[str, object] = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

        _use_threaded_child_watcher()
        flow_run_logger.info("Opening process...")

        env = get_current_settings().to_environment_variables(exclude_unset=True)
        env.update({"PREFECT__FLOW_RUN_ID": flow_run.id.hex})
        env.update(**os.environ)  # is this really necessary??

        process = await run_process(
            command.split(" "),
            stream_output=True,
            task_status=task_status,
            env=env,
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

        return process.returncode

    async def _kill_process(
        self,
        pid: int,
        grace_seconds: int = 30,
    ):
        """
        Kills a given flow run process.

        Args:
            pid: ID of the process to kill
            grace_seconds: Number of seconds to wait for the process to end.
        """
        # In a non-windows environment first send a SIGTERM, then, after
        # `grace_seconds` seconds have passed subsequent send SIGKILL. In
        # Windows we use CTRL_BREAK_EVENT as SIGTERM is useless:
        # https://bugs.python.org/issue26350
        if sys.platform == "win32":
            try:
                os.kill(pid, signal.CTRL_BREAK_EVENT)
            except (ProcessLookupError, WindowsError):
                raise RuntimeError(
                    f"Unable to kill process {pid!r}: The process was not found."
                )
        else:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                raise RuntimeError(
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

    async def _pause_schedules(self):
        """
        Pauses all deployment schedules.
        """
        self._logger.info("Pausing schedules for all deployments...")
        for deployment_id in self._deployment_ids:
            self._logger.debug(f"Pausing schedule for deployment '{deployment_id}'")
            await self._client.update_schedule(deployment_id, active=False)
        self._logger.info("All deployment schedules have been paused!")

    async def _get_and_submit_flow_runs(self):
        runs_response = await self._get_scheduled_flow_runs()

        return await self._submit_scheduled_flow_runs(flow_run_response=runs_response)

    async def _check_for_cancelled_flow_runs(
        self, on_nothing_to_watch: Callable = lambda: None
    ):
        if not self.started:
            raise RuntimeError(
                "Runner is not set up. Please make sure you are running this runner "
                "as an async context manager."
            )

        # To stop loop service checking for cancelled runs.
        # Need to find a better way to stop runner spawned by
        # a worker.
        if not self._flow_run_process_map and not self._deployment_ids:
            self._logger.debug(
                "Runner has no active flow runs or deployments. Sending message to loop"
                " service that no further cancellation checks are needed."
            )
            on_nothing_to_watch()

        self._logger.debug("Checking for cancelled flow runs...")

        named_cancelling_flow_runs = await self._client.read_flow_runs(
            flow_run_filter=FlowRunFilter(
                state=FlowRunFilterState(
                    type=FlowRunFilterStateType(any_=[StateType.CANCELLED]),
                    name=FlowRunFilterStateName(any_=["Cancelling"]),
                ),
                # Avoid duplicate cancellation calls
                id=FlowRunFilterId(
                    any_=list(
                        self._flow_run_process_map.keys()
                        - self._cancelling_flow_run_ids
                    )
                ),
            ),
        )

        typed_cancelling_flow_runs = await self._client.read_flow_runs(
            flow_run_filter=FlowRunFilter(
                state=FlowRunFilterState(
                    type=FlowRunFilterStateType(any_=[StateType.CANCELLING]),
                ),
                # Avoid duplicate cancellation calls
                id=FlowRunFilterId(
                    any_=list(
                        self._flow_run_process_map.keys()
                        - self._cancelling_flow_run_ids
                    )
                ),
            ),
        )

        cancelling_flow_runs = named_cancelling_flow_runs + typed_cancelling_flow_runs

        if cancelling_flow_runs:
            self._logger.info(
                f"Found {len(cancelling_flow_runs)} flow runs awaiting cancellation."
            )

        for flow_run in cancelling_flow_runs:
            self._cancelling_flow_run_ids.add(flow_run.id)
            self._runs_task_group.start_soon(self._cancel_run, flow_run)

        return cancelling_flow_runs

    async def _cancel_run(self, flow_run: "FlowRun"):
        run_logger = self._get_flow_run_logger(flow_run)

        pid = self._flow_run_process_map.get(flow_run.id)
        if not pid:
            await self._mark_flow_run_as_cancelled(
                flow_run,
                state_updates={
                    "message": (
                        "Could not find process ID for flow run"
                        " and cancellation cannot be guaranteed."
                    )
                },
            )
            return

        try:
            await self._kill_process(pid)
        except RuntimeError as exc:
            self._logger.warning(f"{exc} Marking flow run as cancelled.")
            await self._mark_flow_run_as_cancelled(flow_run)
        except Exception:
            run_logger.exception(
                "Encountered exception while killing process for flow run "
                f"'{flow_run.id}'. Flow run may not be cancelled."
            )
            # We will try again on generic exceptions
            self._cancelling_flow_run_ids.remove(flow_run.id)
            return
        else:
            await self._mark_flow_run_as_cancelled(flow_run)
            run_logger.info(f"Cancelled flow run '{flow_run.id}'!")

    async def _get_scheduled_flow_runs(
        self,
    ) -> List["FlowRun"]:
        """
        Retrieve scheduled flow runs for this runner.
        """
        scheduled_before = pendulum.now("utc").add(seconds=int(self._prefetch_seconds))
        self._logger.debug(
            f"Querying for flow runs scheduled before {scheduled_before}"
        )

        scheduled_flow_runs = await self._client.read_flow_runs(
            deployment_filter=DeploymentFilter(
                id=DeploymentFilterId(any_=list(self._deployment_ids))
            ),
            flow_run_filter=FlowRunFilter(
                next_scheduled_start_time=FlowRunFilterNextScheduledStartTime(
                    before_=scheduled_before
                ),
                state=FlowRunFilterState(
                    type=FlowRunFilterStateType(any_=[StateType.SCHEDULED]),
                ),
                # possible unnecessary
                id=FlowRunFilterId(not_any_=list(self._submitting_flow_run_ids)),
            ),
        )
        self._logger.debug(f"Discovered {len(scheduled_flow_runs)} scheduled_flow_runs")
        return scheduled_flow_runs

    def _acquire_limit_slot(self, flow_run_id: str) -> bool:
        """
        Enforces flow run limit set on runner.

        Returns:
            - bool: True if a slot was acquired, False otherwise.
        """
        try:
            if self._limiter:
                self._limiter.acquire_on_behalf_of_nowait(flow_run_id)
            return True
        except anyio.WouldBlock:
            self._logger.info(
                f"Flow run limit reached; {self._limiter.borrowed_tokens} flow runs"
                " in progress. You can control this limit by adjusting the"
                " PREFECT_RUNNER_PROCESS_LIMIT setting."
            )
            return False

    def _release_limit_slot(self, flow_run_id: str) -> None:
        """
        Frees up a slot taken by the given flow run id.
        """
        if self._limiter:
            self._limiter.release_on_behalf_of(flow_run_id)

    async def _submit_scheduled_flow_runs(
        self, flow_run_response: List["FlowRun"]
    ) -> List["FlowRun"]:
        """
        Takes a list of FlowRuns and submits the referenced flow runs
        for execution by the runner.
        """
        submittable_flow_runs = flow_run_response
        submittable_flow_runs.sort(key=lambda run: run.next_scheduled_start_time)
        for flow_run in submittable_flow_runs:
            if flow_run.id in self._submitting_flow_run_ids:
                continue

            if self._acquire_limit_slot(flow_run.id):
                run_logger = self._get_flow_run_logger(flow_run)
                run_logger.info(
                    f"Runner '{self.name}' submitting flow run '{flow_run.id}'"
                )
                self._submitting_flow_run_ids.add(flow_run.id)
                self._runs_task_group.start_soon(
                    self._submit_run,
                    flow_run,
                )
            else:
                break

        return list(
            filter(
                lambda run: run.id in self._submitting_flow_run_ids,
                submittable_flow_runs,
            )
        )

    async def _submit_run(self, flow_run: "FlowRun") -> None:
        """
        Submits a given flow run for execution by the runner.
        """
        run_logger = self._get_flow_run_logger(flow_run)

        ready_to_submit = await self._propose_pending_state(flow_run)

        if ready_to_submit:
            readiness_result = await self._runs_task_group.start(
                self._submit_run_and_capture_errors, flow_run
            )

            if readiness_result and not isinstance(readiness_result, Exception):
                self._flow_run_process_map[flow_run.id] = readiness_result

            run_logger.info(f"Completed submission of flow run '{flow_run.id}'")
        else:
            # If the run is not ready to submit, release the concurrency slot
            self._release_limit_slot(flow_run.id)

        self._submitting_flow_run_ids.remove(flow_run.id)

    async def _submit_run_and_capture_errors(
        self, flow_run: "FlowRun", task_status: anyio.abc.TaskStatus = None
    ) -> Union[Optional[int], Exception]:
        run_logger = self._get_flow_run_logger(flow_run)

        try:
            status_code = await self._run_process(
                flow_run=flow_run,
                task_status=task_status,
            )
        except Exception as exc:
            if not task_status._future.done():
                # This flow run was being submitted and did not start successfully
                run_logger.exception(
                    f"Failed to start process for flow run '{flow_run.id}'."
                )
                # Mark the task as started to prevent agent crash
                task_status.started(exc)
                await self._propose_crashed_state(
                    flow_run, "Flow run process could not be started"
                )
            else:
                run_logger.exception(
                    f"An error occurred while monitoring flow run '{flow_run.id}'. "
                    "The flow run will not be marked as failed, but an issue may have "
                    "occurred."
                )
            return exc
        finally:
            self._release_limit_slot(flow_run.id)
            self._flow_run_process_map.pop(flow_run.id, None)

        if status_code != 0:
            await self._propose_crashed_state(
                flow_run,
                f"Flow run process exited with non-zero status code {status_code}.",
            )

        return status_code

    async def _propose_pending_state(self, flow_run: "FlowRun") -> bool:
        run_logger = self._get_flow_run_logger(flow_run)
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
        run_logger = self._get_flow_run_logger(flow_run)
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
        run_logger = self._get_flow_run_logger(flow_run)
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

        These tasks will be run immediately when the runner exits instead of waiting.

        The function may be async or sync. Async functions will be awaited.
        """

        async def wrapper(task_status):
            # If we are shutting down, do not sleep; otherwise sleep until the scheduled
            # time or shutdown
            if self.started:
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
        self._logger.debug("Starting runner...")
        self._client = get_client()
        await self._client.__aenter__()
        await self._runs_task_group.__aenter__()

        self.started = True
        return self

    async def __aexit__(self, *exc_info):
        self._logger.debug("Stopping runner...")
        if self.pause_on_shutdown:
            await self._pause_schedules()
        self.started = False
        for scope in self._scheduled_task_scopes:
            scope.cancel()
        if self._runs_task_group:
            await self._runs_task_group.__aexit__(*exc_info)
        if self._client:
            await self._client.__aexit__(*exc_info)

    def __repr__(self):
        return f"Runner(name={self.name!r})"


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


@sync_compatible
async def serve(
    *args: RunnerDeployment,
    pause_on_shutdown: bool = True,
    print_starting_message: bool = True,
    **kwargs,
):
    """
    Serve the provided list of deployments.

    Args:
        *args: A list of deployments to serve.
        pause_on_shutdown: A boolean for whether or not to automatically pause
            deployment schedules on shutdown.
        **kwargs: Additional keyword arguments to pass to the runner.

    Examples:
        Prepare two deployments and serve them:

        ```python
        import datetime

        from prefect import flow, serve

        @flow
        def my_flow(name):
            print(f"hello {name}")

        @flow
        def my_other_flow(name):
            print(f"goodbye {name}")

        if __name__ == "__main__":
            # Run once a day
            hello_deploy = my_flow.to_deployment(
                "hello", tags=["dev"], interval=datetime.timedelta(days=1)
            )

            # Run every Sunday at 4:00 AM
            bye_deploy = my_other_flow.to_deployment(
                "goodbye", tags=["dev"], cron="0 4 * * sun"
            )

            serve(hello_deploy, bye_deploy)
        ```
    """
    runner = Runner(pause_on_shutdown=pause_on_shutdown, **kwargs)
    for deployment in args:
        await runner.add_deployment(deployment)

    if print_starting_message:
        help_message_top = (
            "[green]Your deployments are being served and polling for"
            " scheduled runs!\n[/]"
        )

        table = Table(title="Deployments", show_header=False)

        table.add_column(style="blue", no_wrap=True)

        for deployment in args:
            table.add_row(f"{deployment.flow_name}/{deployment.name}")

        help_message_bottom = (
            "\nTo trigger any of these deployments, use the"
            " following command:\n[blue]\n\t$ prefect deployment run"
            " [DEPLOYMENT_NAME]\n[/]"
        )
        if PREFECT_UI_URL:
            help_message_bottom += (
                "\nYou can also trigger your deployments via the Prefect UI:"
                f" [blue]{PREFECT_UI_URL.value()}/deployments[/]\n"
            )

        console = Console()
        console.print(Panel(Group(help_message_top, table, help_message_bottom)))

    await runner.start()
