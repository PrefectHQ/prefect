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

import asyncio
import datetime
import inspect
import logging
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
from copy import deepcopy
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict, Iterable, List, Optional, Set, Union
from uuid import UUID, uuid4

import anyio
import anyio.abc
import pendulum

from prefect._internal.concurrency.api import (
    create_call,
    from_async,
    from_sync,
)
from prefect.client.orchestration import get_client
from prefect.client.schemas.filters import (
    FlowRunFilter,
    FlowRunFilterId,
    FlowRunFilterState,
    FlowRunFilterStateName,
    FlowRunFilterStateType,
)
from prefect.client.schemas.objects import Flow as APIFlow
from prefect.client.schemas.objects import FlowRun, State, StateType
from prefect.concurrency.asyncio import (
    AcquireConcurrencySlotTimeoutError,
    ConcurrencySlotAcquisitionError,
    concurrency,
)
from prefect.events import DeploymentTriggerTypes, TriggerTypes
from prefect.events.related import tags_as_related_resources
from prefect.events.schemas.events import RelatedResource
from prefect.events.utilities import emit_event
from prefect.exceptions import Abort, ObjectNotFound
from prefect.flows import Flow, load_flow_from_flow_run
from prefect.logging.loggers import PrefectLogAdapter, flow_run_logger, get_logger
from prefect.runner.storage import RunnerStorage
from prefect.settings import (
    PREFECT_API_URL,
    PREFECT_RUNNER_POLL_FREQUENCY,
    PREFECT_RUNNER_PROCESS_LIMIT,
    PREFECT_RUNNER_SERVER_ENABLE,
    get_current_settings,
)
from prefect.states import (
    AwaitingConcurrencySlot,
    Crashed,
    Pending,
    exception_to_failed_state,
)
from prefect.types.entrypoint import EntrypointType
from prefect.utilities.asyncutils import (
    asyncnullcontext,
    is_async_fn,
    sync_compatible,
)
from prefect.utilities.engine import propose_state
from prefect.utilities.processutils import (
    _register_signal,
    get_sys_executable,
    run_process,
)
from prefect.utilities.services import (
    critical_service_loop,
    start_client_metrics_server,
)
from prefect.utilities.slugify import slugify

if TYPE_CHECKING:
    from prefect.client.schemas.objects import Deployment
    from prefect.client.types.flexible_schedule_list import FlexibleScheduleList
    from prefect.deployments.runner import RunnerDeployment

__all__ = ["Runner"]


class Runner:
    def __init__(
        self,
        name: Optional[str] = None,
        query_seconds: Optional[float] = None,
        prefetch_seconds: float = 10,
        limit: Optional[int] = None,
        pause_on_shutdown: bool = True,
        webserver: bool = False,
    ):
        """
        Responsible for managing the execution of remotely initiated flow runs.

        Args:
            name: The name of the runner. If not provided, a random one
                will be generated. If provided, it cannot contain '/' or '%'.
            query_seconds: The number of seconds to wait between querying for
                scheduled flow runs; defaults to `PREFECT_RUNNER_POLL_FREQUENCY`
            prefetch_seconds: The number of seconds to prefetch flow runs for.
            limit: The maximum number of flow runs this runner should be running at
            pause_on_shutdown: A boolean for whether or not to automatically pause
                deployment schedules on shutdown; defaults to `True`
            webserver: a boolean flag for whether to start a webserver for this runner

        Examples:
            Set up a Runner to manage the execute of scheduled flow runs for two flows:
                ```python
                import asyncio
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

                    asyncio.run(runner.start())
                ```
        """
        if name and ("/" in name or "%" in name):
            raise ValueError("Runner name cannot contain '/' or '%'")
        self.name = Path(name).stem if name is not None else f"runner-{uuid4()}"
        self._logger = get_logger("runner")

        self.started = False
        self.stopping = False
        self.pause_on_shutdown = pause_on_shutdown
        self.limit = limit or PREFECT_RUNNER_PROCESS_LIMIT.value()
        self.webserver = webserver

        self.query_seconds = query_seconds or PREFECT_RUNNER_POLL_FREQUENCY.value()
        self._prefetch_seconds = prefetch_seconds

        self._limiter: Optional[anyio.CapacityLimiter] = None
        self._client = get_client()
        self._submitting_flow_run_ids = set()
        self._cancelling_flow_run_ids = set()
        self._scheduled_task_scopes = set()
        self._deployment_ids: Set[UUID] = set()
        self._flow_run_process_map: Dict[UUID, Dict] = dict()

        self._tmp_dir: Path = (
            Path(tempfile.gettempdir()) / "runner_storage" / str(uuid4())
        )
        self._storage_objs: List[RunnerStorage] = []
        self._deployment_storage_map: Dict[UUID, RunnerStorage] = {}

        self._loop: Optional[asyncio.AbstractEventLoop] = None

    @sync_compatible
    async def add_deployment(
        self,
        deployment: "RunnerDeployment",
    ) -> UUID:
        """
        Registers the deployment with the Prefect API and will monitor for work once
        the runner is started.

        Args:
            deployment: A deployment for the runner to register.
        """
        deployment_id = await deployment.apply()
        storage = deployment.storage
        if storage is not None:
            storage = await self._add_storage(storage)
            self._deployment_storage_map[deployment_id] = storage
        self._deployment_ids.add(deployment_id)

        return deployment_id

    @sync_compatible
    async def add_flow(
        self,
        flow: Flow,
        name: Optional[str] = None,
        interval: Optional[
            Union[
                Iterable[Union[int, float, datetime.timedelta]],
                int,
                float,
                datetime.timedelta,
            ]
        ] = None,
        cron: Optional[Union[Iterable[str], str]] = None,
        rrule: Optional[Union[Iterable[str], str]] = None,
        paused: Optional[bool] = None,
        schedules: Optional["FlexibleScheduleList"] = None,
        concurrency_limit: Optional[int] = None,
        parameters: Optional[dict] = None,
        triggers: Optional[List[Union[DeploymentTriggerTypes, TriggerTypes]]] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        version: Optional[str] = None,
        enforce_parameter_schema: bool = True,
        entrypoint_type: EntrypointType = EntrypointType.FILE_PATH,
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
            paused: Whether or not to set the created deployment as paused.
            schedules: A list of schedule objects defining when to execute runs of this flow.
                Used to define multiple schedules or additional scheduling options like `timezone`.
            concurrency_limit: The maximum number of concurrent runs of this flow to allow.
            triggers: A list of triggers that should kick of a run of this flow.
            parameters: A dictionary of default parameter values to pass to runs of this flow.
            description: A description for the created deployment. Defaults to the flow's
                description if not provided.
            tags: A list of tags to associate with the created deployment for organizational
                purposes.
            version: A version for the created deployment. Defaults to the flow's version.
            entrypoint_type: Type of entrypoint to use for the deployment. When using a module path
                entrypoint, ensure that the module will be importable in the execution environment.
        """
        api = PREFECT_API_URL.value()
        if any([interval, cron, rrule]) and not api:
            self._logger.warning(
                "Cannot schedule flows on an ephemeral server; run `prefect server"
                " start` to start the scheduler."
            )
        name = self.name if name is None else name

        deployment = await flow.to_deployment(
            name=name,
            interval=interval,
            cron=cron,
            rrule=rrule,
            schedules=schedules,
            paused=paused,
            triggers=triggers,
            parameters=parameters,
            description=description,
            tags=tags,
            version=version,
            enforce_parameter_schema=enforce_parameter_schema,
            entrypoint_type=entrypoint_type,
            concurrency_limit=concurrency_limit,
        )
        return await self.add_deployment(deployment)

    @sync_compatible
    async def _add_storage(self, storage: RunnerStorage) -> RunnerStorage:
        """
        Adds a storage object to the runner. The storage object will be used to pull
        code to the runner's working directory before the runner starts.

        Args:
            storage: The storage object to add to the runner.
        Returns:
            The updated storage object that was added to the runner.
        """
        if storage not in self._storage_objs:
            storage_copy = deepcopy(storage)
            storage_copy.set_base_path(self._tmp_dir)

            self._logger.debug(
                f"Adding storage {storage_copy!r} to runner at"
                f" {str(storage_copy.destination)!r}"
            )
            self._storage_objs.append(storage_copy)

            return storage_copy
        else:
            return next(s for s in self._storage_objs if s == storage)

    def handle_sigterm(self, signum, frame):
        """
        Gracefully shuts down the runner when a SIGTERM is received.
        """
        self._logger.info("SIGTERM received, initiating graceful shutdown...")
        from_sync.call_in_loop_thread(create_call(self.stop))

        sys.exit(0)

    async def start(
        self, run_once: bool = False, webserver: Optional[bool] = None
    ) -> None:
        """
        Starts a runner.

        The runner will begin monitoring for and executing any scheduled work for all added flows.

        Args:
            run_once: If True, the runner will through one query loop and then exit.
            webserver: a boolean for whether to start a webserver for this runner. If provided,
                overrides the default on the runner

        Examples:
            Initialize a Runner, add two flows, and serve them by starting the Runner:

            ```python
            import asyncio
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

                asyncio.run(runner.start())
            ```
        """
        from prefect.runner.server import start_webserver

        _register_signal(signal.SIGTERM, self.handle_sigterm)

        webserver = webserver if webserver is not None else self.webserver

        if webserver or PREFECT_RUNNER_SERVER_ENABLE.value():
            # we'll start the ASGI server in a separate thread so that
            # uvicorn does not block the main thread
            server_thread = threading.Thread(
                name="runner-server-thread",
                target=partial(
                    start_webserver,
                    runner=self,
                ),
                daemon=True,
            )
            server_thread.start()

        start_client_metrics_server()

        async with self as runner:
            async with self._loops_task_group as tg:
                for storage in self._storage_objs:
                    if storage.pull_interval:
                        tg.start_soon(
                            partial(
                                critical_service_loop,
                                workload=storage.pull_code,
                                interval=storage.pull_interval,
                                run_once=run_once,
                                jitter_range=0.3,
                            )
                        )
                    else:
                        tg.start_soon(storage.pull_code)
                tg.start_soon(
                    partial(
                        critical_service_loop,
                        workload=runner._get_and_submit_flow_runs,
                        interval=self.query_seconds,
                        run_once=run_once,
                        jitter_range=0.3,
                    )
                )
                tg.start_soon(
                    partial(
                        critical_service_loop,
                        workload=runner._check_for_cancelled_flow_runs,
                        interval=self.query_seconds * 2,
                        run_once=run_once,
                        jitter_range=0.3,
                    )
                )

    def execute_in_background(self, func, *args, **kwargs):
        """
        Executes a function in the background.
        """

        return asyncio.run_coroutine_threadsafe(func(*args, **kwargs), self._loop)

    async def cancel_all(self):
        runs_to_cancel = []

        # done to avoid dictionary size changing during iteration
        for info in self._flow_run_process_map.values():
            runs_to_cancel.append(info["flow_run"])
        if runs_to_cancel:
            for run in runs_to_cancel:
                try:
                    await self._cancel_run(run, state_msg="Runner is shutting down.")
                except Exception:
                    self._logger.exception(
                        f"Exception encountered while cancelling {run.id}",
                        exc_info=True,
                    )

    @sync_compatible
    async def stop(self):
        """Stops the runner's polling cycle."""
        if not self.started:
            raise RuntimeError(
                "Runner has not yet started. Please start the runner by calling"
                " .start()"
            )

        self.started = False
        self.stopping = True
        await self.cancel_all()
        try:
            self._loops_task_group.cancel_scope.cancel()
        except Exception:
            self._logger.exception(
                "Exception encountered while shutting down", exc_info=True
            )

    async def execute_flow_run(
        self, flow_run_id: UUID, entrypoint: Optional[str] = None
    ):
        """
        Executes a single flow run with the given ID.

        Execution will wait to monitor for cancellation requests. Exits once
        the flow run process has exited.
        """
        self.pause_on_shutdown = False
        context = self if not self.started else asyncnullcontext()

        async with context:
            if not self._acquire_limit_slot(flow_run_id):
                return

            async with anyio.create_task_group() as tg:
                with anyio.CancelScope():
                    self._submitting_flow_run_ids.add(flow_run_id)
                    flow_run = await self._client.read_flow_run(flow_run_id)

                    pid = await self._runs_task_group.start(
                        partial(
                            self._submit_run_and_capture_errors,
                            flow_run=flow_run,
                            entrypoint=entrypoint,
                        ),
                    )

                    self._flow_run_process_map[flow_run.id] = dict(
                        pid=pid, flow_run=flow_run
                    )

                    # We want this loop to stop when the flow run process exits
                    # so we'll check if the flow run process is still alive on
                    # each iteration and cancel the task group if it is not.
                    workload = partial(
                        self._check_for_cancelled_flow_runs,
                        should_stop=lambda: not self._flow_run_process_map,
                        on_stop=tg.cancel_scope.cancel,
                    )

                    tg.start_soon(
                        partial(
                            critical_service_loop,
                            workload=workload,
                            interval=self.query_seconds,
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
        entrypoint: Optional[str] = None,
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
        command = [get_sys_executable(), "-m", "prefect.engine"]

        flow_run_logger = self._get_flow_run_logger(flow_run)

        # We must add creationflags to a dict so it is only passed as a function
        # parameter on Windows, because the presence of creationflags causes
        # errors on Unix even if set to None
        kwargs: Dict[str, object] = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

        flow_run_logger.info("Opening process...")

        env = get_current_settings().to_environment_variables(exclude_unset=True)
        env.update(
            {
                **{
                    "PREFECT__FLOW_RUN_ID": str(flow_run.id),
                    "PREFECT__STORAGE_BASE_PATH": str(self._tmp_dir),
                    "PREFECT__ENABLE_CANCELLATION_AND_CRASHED_HOOKS": "false",
                },
                **({"PREFECT__FLOW_ENTRYPOINT": entrypoint} if entrypoint else {}),
            }
        )
        env.update(**os.environ)  # is this really necessary??

        storage = self._deployment_storage_map.get(flow_run.deployment_id)
        if storage and storage.pull_interval:
            # perform an adhoc pull of code before running the flow if an
            # adhoc pull hasn't been performed in the last pull_interval
            # TODO: Explore integrating this behavior with global concurrency.
            last_adhoc_pull = getattr(storage, "last_adhoc_pull", None)
            if (
                last_adhoc_pull is None
                or last_adhoc_pull
                < datetime.datetime.now()
                - datetime.timedelta(seconds=storage.pull_interval)
            ):
                self._logger.debug(
                    "Performing adhoc pull of code for flow run %s with storage %r",
                    flow_run.id,
                    storage,
                )
                await storage.pull_code()
                setattr(storage, "last_adhoc_pull", datetime.datetime.now())

        process = await run_process(
            command=command,
            stream_output=True,
            task_status=task_status,
            env=env,
            **kwargs,
            cwd=storage.destination if storage else None,
        )

        # Use the pid for display if no name was given

        if process.returncode:
            help_message = None
            level = logging.ERROR
            if process.returncode == -9:
                level = logging.INFO
                help_message = (
                    "This indicates that the process exited due to a SIGKILL signal. "
                    "Typically, this is either caused by manual cancellation or "
                    "high memory usage causing the operating system to "
                    "terminate the process."
                )
            if process.returncode == -15:
                level = logging.INFO
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
                level = logging.INFO
                help_message = (
                    "Process was terminated due to a Ctrl+C or Ctrl+Break signal. "
                    "Typically, this is caused by manual cancellation."
                )

            flow_run_logger.log(
                level,
                f"Process for flow run {flow_run.name!r} exited with status code:"
                f" {process.returncode}"
                + (f"; {help_message}" if help_message else ""),
            )
        else:
            flow_run_logger.info(
                f"Process for flow run {flow_run.name!r} exited cleanly."
            )

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
        self._logger.info("Pausing all deployments...")
        for deployment_id in self._deployment_ids:
            await self._client.set_deployment_paused_state(deployment_id, True)
            self._logger.debug(f"Paused deployment '{deployment_id}'")

        self._logger.info("All deployments have been paused!")

    async def _get_and_submit_flow_runs(self):
        if self.stopping:
            return
        runs_response = await self._get_scheduled_flow_runs()
        self.last_polled = pendulum.now("UTC")
        return await self._submit_scheduled_flow_runs(flow_run_response=runs_response)

    async def _check_for_cancelled_flow_runs(
        self, should_stop: Callable = lambda: False, on_stop: Callable = lambda: None
    ):
        """
        Checks for flow runs with CANCELLING a cancelling state and attempts to
        cancel them.

        Args:
            should_stop: A callable that returns a boolean indicating whether or not
                the runner should stop checking for cancelled flow runs.
            on_stop: A callable that is called when the runner should stop checking
                for cancelled flow runs.
        """
        if self.stopping:
            return
        if not self.started:
            raise RuntimeError(
                "Runner is not set up. Please make sure you are running this runner "
                "as an async context manager."
            )

        if should_stop():
            self._logger.debug(
                "Runner has no active flow runs or deployments. Sending message to loop"
                " service that no further cancellation checks are needed."
            )
            on_stop()

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

    async def _cancel_run(self, flow_run: "FlowRun", state_msg: Optional[str] = None):
        run_logger = self._get_flow_run_logger(flow_run)

        pid = self._flow_run_process_map.get(flow_run.id, {}).get("pid")
        if not pid:
            await self._run_on_cancellation_hooks(flow_run, flow_run.state)
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
            await self._run_on_cancellation_hooks(flow_run, flow_run.state)
            await self._mark_flow_run_as_cancelled(flow_run)
        except Exception:
            run_logger.exception(
                "Encountered exception while killing process for flow run "
                f"'{flow_run.id}'. Flow run may not be cancelled."
            )
            # We will try again on generic exceptions
            self._cancelling_flow_run_ids.remove(flow_run.id)
        else:
            await self._run_on_cancellation_hooks(flow_run, flow_run.state)
            await self._mark_flow_run_as_cancelled(
                flow_run,
                state_updates={
                    "message": state_msg or "Flow run was cancelled successfully."
                },
            )
            try:
                deployment = await self._client.read_deployment(flow_run.deployment_id)
            except ObjectNotFound:
                deployment = None
            try:
                flow = await self._client.read_flow(flow_run.flow_id)
            except ObjectNotFound:
                flow = None
            self._emit_flow_run_cancelled_event(
                flow_run=flow_run, flow=flow, deployment=deployment
            )
            run_logger.info(f"Cancelled flow run '{flow_run.name}'!")

    def _event_resource(self):
        from prefect import __version__

        return {
            "prefect.resource.id": f"prefect.runner.{slugify(self.name)}",
            "prefect.resource.name": self.name,
            "prefect.version": __version__,
        }

    def _emit_flow_run_cancelled_event(
        self,
        flow_run: "FlowRun",
        flow: "Optional[APIFlow]",
        deployment: "Optional[Deployment]",
    ):
        related = []
        tags = []
        if deployment:
            related.append(
                {
                    "prefect.resource.id": f"prefect.deployment.{deployment.id}",
                    "prefect.resource.role": "deployment",
                    "prefect.resource.name": deployment.name,
                }
            )
            tags.extend(deployment.tags)
        if flow:
            related.append(
                {
                    "prefect.resource.id": f"prefect.flow.{flow.id}",
                    "prefect.resource.role": "flow",
                    "prefect.resource.name": flow.name,
                }
            )
        related.append(
            {
                "prefect.resource.id": f"prefect.flow-run.{flow_run.id}",
                "prefect.resource.role": "flow-run",
                "prefect.resource.name": flow_run.name,
            }
        )
        tags.extend(flow_run.tags)

        related = [RelatedResource.model_validate(r) for r in related]
        related += tags_as_related_resources(set(tags))

        emit_event(
            event="prefect.runner.cancelled-flow-run",
            resource=self._event_resource(),
            related=related,
        )

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

        scheduled_flow_runs = (
            await self._client.get_scheduled_flow_runs_for_deployments(
                deployment_ids=list(self._deployment_ids),
                scheduled_before=scheduled_before,
            )
        )
        self._logger.debug(f"Discovered {len(scheduled_flow_runs)} scheduled_flow_runs")
        return scheduled_flow_runs

    def has_slots_available(self) -> bool:
        """
        Determine if the flow run limit has been reached.

        Returns:
            - bool: True if the limit has not been reached, False otherwise.
        """
        return self._limiter.available_tokens > 0

    def _acquire_limit_slot(self, flow_run_id: str) -> bool:
        """
        Enforces flow run limit set on runner.

        Returns:
            - bool: True if a slot was acquired, False otherwise.
        """
        try:
            if self._limiter:
                self._limiter.acquire_on_behalf_of_nowait(flow_run_id)
                self._logger.debug("Limit slot acquired for flow run '%s'", flow_run_id)
            return True
        except RuntimeError as exc:
            if (
                "this borrower is already holding one of this CapacityLimiter's tokens"
                in str(exc)
            ):
                self._logger.warning(
                    f"Duplicate submission of flow run '{flow_run_id}' detected. Runner"
                    " will not re-submit flow run."
                )
                return False
            else:
                raise
        except anyio.WouldBlock:
            self._logger.info(
                f"Flow run limit reached; {self._limiter.borrowed_tokens} flow runs"
                " in progress. You can control this limit by passing a `limit` value"
                " to `serve` or adjusting the PREFECT_RUNNER_PROCESS_LIMIT setting."
            )
            return False

    def _release_limit_slot(self, flow_run_id: str) -> None:
        """
        Frees up a slot taken by the given flow run id.
        """
        if self._limiter:
            self._limiter.release_on_behalf_of(flow_run_id)
            self._logger.debug("Limit slot released for flow run '%s'", flow_run_id)

    async def _submit_scheduled_flow_runs(
        self,
        flow_run_response: List["FlowRun"],
        entrypoints: Optional[List[str]] = None,
    ) -> List["FlowRun"]:
        """
        Takes a list of FlowRuns and submits the referenced flow runs
        for execution by the runner.
        """
        submittable_flow_runs = flow_run_response
        submittable_flow_runs.sort(key=lambda run: run.next_scheduled_start_time)

        for i, flow_run in enumerate(submittable_flow_runs):
            if flow_run.id in self._submitting_flow_run_ids:
                continue

            if self._acquire_limit_slot(flow_run.id):
                run_logger = self._get_flow_run_logger(flow_run)
                run_logger.info(
                    f"Runner '{self.name}' submitting flow run '{flow_run.id}'"
                )
                self._submitting_flow_run_ids.add(flow_run.id)
                self._runs_task_group.start_soon(
                    partial(
                        self._submit_run,
                        flow_run=flow_run,
                        entrypoint=(
                            entrypoints[i] if entrypoints else None
                        ),  # TODO: avoid relying on index
                    )
                )
            else:
                break

        return list(
            filter(
                lambda run: run.id in self._submitting_flow_run_ids,
                submittable_flow_runs,
            )
        )

    async def _submit_run(self, flow_run: "FlowRun", entrypoint: Optional[str] = None):
        """
        Submits a given flow run for execution by the runner.
        """
        run_logger = self._get_flow_run_logger(flow_run)

        ready_to_submit = await self._propose_pending_state(flow_run)

        if ready_to_submit:
            readiness_result = await self._runs_task_group.start(
                partial(
                    self._submit_run_and_capture_errors,
                    flow_run=flow_run,
                    entrypoint=entrypoint,
                ),
            )

            if readiness_result and not isinstance(readiness_result, Exception):
                self._flow_run_process_map[flow_run.id] = dict(
                    pid=readiness_result, flow_run=flow_run
                )

            run_logger.info(f"Completed submission of flow run '{flow_run.id}'")
        else:
            # If the run is not ready to submit, release the concurrency slot
            self._release_limit_slot(flow_run.id)

        self._submitting_flow_run_ids.discard(flow_run.id)

    async def _submit_run_and_capture_errors(
        self,
        flow_run: "FlowRun",
        task_status: Optional[anyio.abc.TaskStatus] = None,
        entrypoint: Optional[str] = None,
    ) -> Union[Optional[int], Exception]:
        run_logger = self._get_flow_run_logger(flow_run)

        if flow_run.deployment_id:
            deployment = await self._client.read_deployment(flow_run.deployment_id)
        if deployment and deployment.concurrency_limit:
            limit_name = f"deployment:{deployment.id}"
            concurrency_ctx = concurrency

            # ensure that the global concurrency limit is available
            # and up-to-date before attempting to acquire a slot
            await self._client.upsert_global_concurrency_limit_by_name(
                limit_name, deployment.concurrency_limit
            )
        else:
            limit_name = ""
            concurrency_ctx = asyncnullcontext

        try:
            async with concurrency_ctx(limit_name, max_retries=0, strict=True):
                status_code = await self._run_process(
                    flow_run=flow_run,
                    task_status=task_status,
                    entrypoint=entrypoint,
                )
        except (
            AcquireConcurrencySlotTimeoutError,
            ConcurrencySlotAcquisitionError,
        ) as exc:
            self._logger.info(
                (
                    "Deployment %s reached its concurrency limit when attempting to execute flow run %s. Will attempt to execute later."
                ),
                flow_run.deployment_id,
                flow_run.name,
            )
            await self._propose_scheduled_state(flow_run)

            if not task_status._future.done():
                task_status.started(exc)
            return exc
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

        api_flow_run = await self._client.read_flow_run(flow_run_id=flow_run.id)
        terminal_state = api_flow_run.state
        if terminal_state.is_crashed():
            await self._run_on_crashed_hooks(flow_run=flow_run, state=terminal_state)

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

    async def _propose_scheduled_state(self, flow_run: "FlowRun") -> None:
        run_logger = self._get_flow_run_logger(flow_run)
        try:
            state = await propose_state(
                self._client,
                AwaitingConcurrencySlot(),
                flow_run_id=flow_run.id,
            )
            self._logger.info(f"Flow run {flow_run.id} now has state {state.name}")
        except Abort as exc:
            run_logger.info(
                (
                    f"Aborted rescheduling of flow run '{flow_run.id}'. "
                    f"Server sent an abort signal: {exc}"
                ),
            )
            pass
        except Exception:
            run_logger.exception(f"Failed to update state of flow run '{flow_run.id}'")

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
        state = flow_run.state.model_copy(update=state_updates)

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

    async def _run_on_cancellation_hooks(
        self,
        flow_run: "FlowRun",
        state: State,
    ) -> None:
        """
        Run the hooks for a flow.
        """
        if state.is_cancelling():
            try:
                flow = await load_flow_from_flow_run(
                    flow_run, storage_base_path=str(self._tmp_dir)
                )
                hooks = flow.on_cancellation_hooks or []

                await _run_hooks(hooks, flow_run, flow, state)
            except ObjectNotFound:
                run_logger = self._get_flow_run_logger(flow_run)
                run_logger.warning(
                    f"Runner cannot retrieve flow to execute cancellation hooks for flow run {flow_run.id!r}."
                )

    async def _run_on_crashed_hooks(
        self,
        flow_run: "FlowRun",
        state: State,
    ) -> None:
        """
        Run the hooks for a flow.
        """
        if state.is_crashed():
            flow = await load_flow_from_flow_run(
                flow_run, storage_base_path=str(self._tmp_dir)
            )
            hooks = flow.on_crashed_hooks or []

            await _run_hooks(hooks, flow_run, flow, state)

    async def __aenter__(self):
        self._logger.debug("Starting runner...")
        self._client = get_client()
        self._tmp_dir.mkdir(parents=True)

        self._limiter = anyio.CapacityLimiter(self.limit)

        if not hasattr(self, "_loop") or not self._loop:
            self._loop = asyncio.get_event_loop()

        if not hasattr(self, "_runs_task_group") or not self._runs_task_group:
            self._runs_task_group: anyio.abc.TaskGroup = anyio.create_task_group()

        if not hasattr(self, "_loops_task_group") or not self._loops_task_group:
            self._loops_task_group: anyio.abc.TaskGroup = anyio.create_task_group()

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
        shutil.rmtree(str(self._tmp_dir))

    def __repr__(self):
        return f"Runner(name={self.name!r})"


if sys.platform == "win32":
    # exit code indicating that the process was terminated by Ctrl+C or Ctrl+Break
    STATUS_CONTROL_C_EXIT = 0xC000013A


async def _run_hooks(
    hooks: List[Callable[[Flow, "FlowRun", State], None]], flow_run, flow, state
):
    logger = flow_run_logger(flow_run, flow)
    for hook in hooks:
        try:
            logger.info(
                f"Running hook {hook.__name__!r} in response to entering state"
                f" {state.name!r}"
            )
            if is_async_fn(hook):
                await hook(flow=flow, flow_run=flow_run, state=state)
            else:
                await from_async.call_in_new_thread(
                    create_call(hook, flow=flow, flow_run=flow_run, state=state)
                )
        except Exception:
            logger.error(
                f"An error was encountered while running hook {hook.__name__!r}",
                exc_info=True,
            )
        else:
            logger.info(f"Hook {hook.__name__!r} finished running successfully")
