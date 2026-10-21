"""
Runners are responsible for managing the execution of all deployments.

When creating a deployment using either `flow.serve` or the `serve` utility,
they also will poll for scheduled runs.

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

from __future__ import annotations

import asyncio
import datetime
import logging
import shutil
import signal
import sys
import tempfile
import threading
import uuid
import warnings
from contextlib import AsyncExitStack
from copy import deepcopy
from functools import partial
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Iterable,
    List,
    Optional,
    TypedDict,
    Union,
)
from uuid import UUID, uuid4

import anyio
import anyio.abc
from typing_extensions import Self

from prefect._internal.compatibility.async_dispatch import async_dispatch
from prefect._internal.compatibility.deprecated import (
    PrefectDeprecationWarning,
    generate_deprecation_message,
)
from prefect._internal.concurrency.api import (
    create_call,
    from_sync,
)
from prefect._internal.observers import FlowRunCancellingObserver
from prefect.client.orchestration import get_client
from prefect.client.schemas.objects import (
    ConcurrencyLimitConfig,
)
from prefect.events import DeploymentTriggerTypes, TriggerTypes
from prefect.events.clients import (  # noqa: F401 (patch target)
    EventsClient,
    get_events_client,
)
from prefect.flows import Flow, load_flow_from_flow_run
from prefect.logging.loggers import get_logger
from prefect.runner._cancellation_manager import CancellationManager
from prefect.runner._control_channel import ControlChannel
from prefect.runner._deployment_registry import DeploymentRegistry
from prefect.runner._event_emitter import EventEmitter
from prefect.runner._flow_run_executor import ProcessStarter
from prefect.runner._hook_runner import HookRunner
from prefect.runner._limit_manager import LimitManager
from prefect.runner._process_manager import ProcessManager
from prefect.runner._scheduled_run_poller import ScheduledRunPoller
from prefect.runner._starter_direct import DirectSubprocessStarter
from prefect.runner._starter_engine import EngineCommandStarter
from prefect.runner._state_proposer import StateProposer
from prefect.runner.storage import RunnerStorage
from prefect.schedules import Schedule
from prefect.settings import (
    PREFECT_API_URL,
    PREFECT_RUNNER_SERVER_ENABLE,
    get_current_settings,
)
from prefect.types.entrypoint import EntrypointType
from prefect.utilities.annotations import NotSet
from prefect.utilities.services import (
    start_client_metrics_server,
)

if TYPE_CHECKING:
    import concurrent.futures

    from prefect.client.schemas.objects import FlowRun
    from prefect.client.types.flexible_schedule_list import FlexibleScheduleList
    from prefect.deployments.runner import RunnerDeployment


__all__ = ["Runner"]


class _ProcessMapEntry(TypedDict):
    flow_run: "FlowRun"
    pid: int


def __getattr__(name: str) -> Any:
    # `ProcessMapEntry` described entries in the process map that the removed
    # `Runner.execute_flow_run` path kept. It stays importable for one
    # deprecation period.
    if name == "ProcessMapEntry":
        warnings.warn(
            generate_deprecation_message(
                name="prefect.runner.runner.ProcessMapEntry",
                start_date="Oct 2026",
                help="`Runner` no longer keeps a process map of these entries.",
            ),
            PrefectDeprecationWarning,
            stacklevel=2,
        )
        return _ProcessMapEntry
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


class Runner:
    def __init__(
        self,
        name: Optional[str] = None,
        query_seconds: Optional[float] = None,
        prefetch_seconds: float = 10,
        heartbeat_seconds: Optional[float] = None,
        limit: int | type[NotSet] | None = NotSet,
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
            heartbeat_seconds: The number of seconds between heartbeat events emitted
                by flow runs managed by this runner. If not provided, the value of
                `PREFECT_FLOWS_HEARTBEAT_FREQUENCY` will be used. Heartbeats are used
                to detect crashed flow runs.
            limit: The maximum number of flow runs this runner should be running at. Provide `None` for no limit.
                If not provided, the runner will use the value of `PREFECT_RUNNER_PROCESS_LIMIT`.
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

                if __name__ == "__main__":
                    runner = Runner(name="my-runner")

                    # Will be runnable via the API
                    runner.add_flow(hello_flow)

                    # Run on a cron schedule
                    runner.add_flow(goodbye_flow, schedule={"cron": "0 * * * *"})

                    asyncio.run(runner.start())
                ```
        """
        self._heartbeat_seconds = heartbeat_seconds

        settings = get_current_settings()

        if name and ("/" in name or "%" in name):
            raise ValueError("Runner name cannot contain '/' or '%'")
        if name is None:
            self.name: str = f"runner-{uuid4()}"
        else:
            # Only strip the suffix when a filename was actually passed; a `.` is
            # legal in a runner name and `Path().stem` would otherwise treat
            # everything after the last one as a file extension. Mirrors
            # `RunnerDeployment.validate_name`.
            self.name = Path(name).stem if name.endswith(".py") else name
        self._logger: "logging.Logger" = get_logger("runner")

        self.started: bool = False
        self.stopping: bool = False
        self.pause_on_shutdown: bool = pause_on_shutdown
        self.limit: int | None = (
            settings.runner.process_limit
            if limit is NotSet or isinstance(limit, type)
            else limit
        )
        self.webserver: bool = webserver

        self.query_seconds: float = query_seconds or settings.runner.poll_frequency
        self._prefetch_seconds: float = prefetch_seconds

        self._exit_stack = AsyncExitStack()
        self._cancelling_observer: FlowRunCancellingObserver | None = None
        self._scheduled_task_scopes: set[anyio.abc.CancelScope] = set()

        self._tmp_dir: Path = (
            Path(tempfile.gettempdir()) / "runner_storage" / str(uuid4())
        )
        self._storage_objs: list[RunnerStorage] = []

        self._loop: Optional[asyncio.AbstractEventLoop] = None

        self._last_polled_fallback: datetime.datetime | None = None

        # --- Services (client-independent, constructed eagerly) ---
        self._deployment_registry = DeploymentRegistry()
        self._process_manager = ProcessManager()
        self._limit_manager = LimitManager(limit=self.limit)
        # HookRunner is constructed in __aenter__ once the client is available,
        # so we can build a storage-aware flow resolver closure.
        self._hook_runner: HookRunner | None = None
        self._state_proposer: StateProposer
        # Cross-platform IPC channel for delivering control intent (cancel
        # today; suspend in a follow-up) into child subprocesses; see
        # prefect.runner._control_channel.
        self._control_channel: ControlChannel = ControlChannel()

        # --- Facade-owned mutable containers (exposed via @property) ---
        self.__cancelling_flow_run_ids_internal: set[UUID] = set()

    @property
    def _cancelling_flow_run_ids(self) -> set[UUID]:
        return self.__cancelling_flow_run_ids_internal

    @property
    def last_polled(self) -> datetime.datetime | None:
        if hasattr(self, "_scheduled_run_poller"):
            return self._scheduled_run_poller.last_polled
        return self._last_polled_fallback

    @last_polled.setter
    def last_polled(self, value: datetime.datetime | None) -> None:
        if hasattr(self, "_scheduled_run_poller"):
            self._scheduled_run_poller.last_polled = value
        else:
            self._last_polled_fallback = value

    @property
    def _limiter(self) -> anyio.CapacityLimiter | None:
        # Test line 291: assert runner._limiter is None (before __aenter__)
        # LimitManager._limiter is None before __aenter__; property delegates correctly
        return self._limit_manager._limiter

    @property
    def _events_client(self) -> EventsClient:
        """Backward-compatible delegate — returns the EventEmitter's inner client."""
        return self._event_emitter._events_client

    async def aadd_deployment(
        self,
        deployment: "RunnerDeployment",
    ) -> UUID:
        """
        Registers the deployment with the Prefect API and will monitor for work once
        the runner is started. Async version.

        Args:
            deployment: A deployment for the runner to register.
        """
        deployment_id = await deployment.aapply()
        storage = deployment.storage
        if storage is not None:
            storage = self._add_storage(storage)
            self._deployment_registry.register_storage(deployment_id, storage)
        self._deployment_registry.register_deployment(deployment_id, deployment.name)

        return deployment_id

    @async_dispatch(aadd_deployment)
    def add_deployment(
        self,
        deployment: "RunnerDeployment",
    ) -> UUID:
        """
        Registers the deployment with the Prefect API and will monitor for work once
        the runner is started.

        Args:
            deployment: A deployment for the runner to register.
        """
        return from_sync.call_soon_in_loop_thread(
            create_call(self.aadd_deployment, deployment)
        ).result()

    async def aadd_flow(
        self,
        flow: Flow[Any, Any],
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
        schedule: Optional[Schedule] = None,
        schedules: Optional["FlexibleScheduleList"] = None,
        concurrency_limit: Optional[Union[int, ConcurrencyLimitConfig, None]] = None,
        parameters: Optional[dict[str, Any]] = None,
        triggers: Optional[List[Union[DeploymentTriggerTypes, TriggerTypes]]] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        version: Optional[str] = None,
        enforce_parameter_schema: bool = True,
        entrypoint_type: EntrypointType = EntrypointType.FILE_PATH,
    ) -> UUID:
        """
        Provides a flow to the runner to be run based on the provided configuration.
        Async version.

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
            schedule: A schedule object defining when to execute runs of this deployment.
                Used to provide additional scheduling options like `timezone` or `parameters`.
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
        if any([interval, cron, rrule, schedule, schedules]) and not api:
            self._logger.warning(
                "Cannot schedule flows on an ephemeral server; run `prefect server"
                " start` to start the scheduler."
            )
        name = self.name if name is None else name

        deployment = await flow.ato_deployment(
            name=name,
            interval=interval,
            cron=cron,
            rrule=rrule,
            schedule=schedule,
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

        # Explicitly mark work pool fields as set so _update() includes them
        # in the payload. This clears any existing work pool config on the
        # server, ensuring runs execute locally instead of on a remote worker.
        deployment.work_pool_name = None
        deployment.work_queue_name = None

        deployment_id = await self.aadd_deployment(deployment)

        # Only add the flow to the map if it is not loaded from storage
        # Further work is needed to support directly running flows created using `flow.from_source`
        if not getattr(flow, "_storage", None):
            self._deployment_registry.register_flow(deployment_id, flow)
        return deployment_id

    @async_dispatch(aadd_flow)
    def add_flow(
        self,
        flow: Flow[Any, Any],
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
        schedule: Optional[Schedule] = None,
        schedules: Optional["FlexibleScheduleList"] = None,
        concurrency_limit: Optional[Union[int, ConcurrencyLimitConfig, None]] = None,
        parameters: Optional[dict[str, Any]] = None,
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
            schedule: A schedule object defining when to execute runs of this deployment.
                Used to provide additional scheduling options like `timezone` or `parameters`.
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
        return from_sync.call_soon_in_loop_thread(
            create_call(
                self.aadd_flow,
                flow,
                name=name,
                interval=interval,
                cron=cron,
                rrule=rrule,
                paused=paused,
                schedule=schedule,
                schedules=schedules,
                concurrency_limit=concurrency_limit,
                parameters=parameters,
                triggers=triggers,
                description=description,
                tags=tags,
                version=version,
                enforce_parameter_schema=enforce_parameter_schema,
                entrypoint_type=entrypoint_type,
            )
        ).result()

    def _add_storage(self, storage: RunnerStorage) -> RunnerStorage:
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

    def handle_sigterm(self, *args: Any, **kwargs: Any) -> None:
        """
        Gracefully shuts down the runner when a SIGTERM is received.
        """
        self._logger.info("SIGTERM received, initiating graceful shutdown...")
        self.stop()

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

                if __name__ == "__main__":
                    runner = Runner(name="my-runner")

                    # Will be runnable via the API
                    runner.add_flow(hello_flow)

                    # Run on a cron schedule
                    runner.add_flow(goodbye_flow, schedule={"cron": "0 * * * *"})

                    asyncio.run(runner.start())
                ```
        """
        from prefect.runner.server import start_webserver

        if threading.current_thread() is threading.main_thread():
            signal.signal(signal.SIGTERM, self.handle_sigterm)

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

        async with self:
            # This task group isn't included in the exit stack because we want to
            # stay in this function until the runner is told to stop
            async with self._loops_task_group:
                if run_once:
                    # Pull storage once before polling (run_once skips storage loops)
                    for storage in self._storage_objs:
                        await storage.pull_code()
                    await self._scheduled_run_poller.run_once()
                else:
                    self._loops_task_group.start_soon(self._scheduled_run_poller.run)

    def execute_in_background(
        self, func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> "concurrent.futures.Future[Any]":
        """
        Executes a function in the background.
        """
        if TYPE_CHECKING:
            assert self._loop is not None

        return asyncio.run_coroutine_threadsafe(func(*args, **kwargs), self._loop)

    async def cancel_all(self) -> None:
        await self._cancellation_manager.cancel_all()

    async def astop(self) -> None:
        """Stops the runner's polling cycle. Async version."""
        if not self.started:
            raise RuntimeError(
                "Runner has not yet started. Please start the runner by calling"
                " .start()"
            )

        self.started = False
        self.stopping = True
        if hasattr(self, "_scheduled_run_poller") and self._scheduled_run_poller:
            self._scheduled_run_poller.stopping = True
        await self.cancel_all()
        try:
            self._loops_task_group.cancel_scope.cancel()
        except Exception:
            self._logger.exception(
                "Exception encountered while shutting down", exc_info=True
            )

    @async_dispatch(astop)
    def stop(self):
        """Stops the runner's polling cycle."""
        from_sync.call_soon_in_loop_thread(create_call(self.astop)).result()

    async def _pause_schedules(self):
        """
        Pauses all deployment schedules.
        """
        self._logger.info("Pausing all deployments...")
        for deployment_id in self._deployment_registry.get_deployment_ids():
            await self._client.pause_deployment(deployment_id)
            self._logger.debug(f"Paused deployment '{deployment_id}'")

        self._logger.info("All deployments have been paused!")

    async def _get_and_submit_flow_runs(self):
        if self.stopping:
            return
        await self._scheduled_run_poller._get_and_submit_flow_runs()

    async def _cancel_run(
        self, flow_run: "FlowRun | uuid.UUID", state_msg: Optional[str] = None
    ):
        if isinstance(flow_run, uuid.UUID):
            if flow_run in self._cancelling_flow_run_ids:
                return
            flow_run = await self._client.read_flow_run(flow_run)
        else:
            if flow_run.id in self._cancelling_flow_run_ids:
                return

        process_handle = self._process_manager.get(flow_run.id)
        if not process_handle or not process_handle.pid:
            return

        self._cancelling_flow_run_ids.add(flow_run.id)
        try:
            await self._cancellation_manager.cancel(flow_run, state_msg)
        finally:
            self._cancelling_flow_run_ids.discard(flow_run.id)

    def has_slots_available(self) -> bool:
        """
        Determine if the flow run limit has been reached.

        Returns:
            - bool: True if the limit has not been reached, False otherwise.
        """
        return self._limit_manager.has_slots_available()

    async def _handle_cancellation_observer_failure(self) -> None:
        """Handle failure of the cancellation observer.

        This is called when both the websocket and polling mechanisms for detecting
        cancellation events have failed. Without cancellation observing, flow runs
        cannot be cancelled and may run indefinitely.

        When `PREFECT_RUNNER_CRASH_ON_CANCELLATION_FAILURE` is enabled, the runner
        stops submitting new flow runs.
        """
        if get_current_settings().runner.crash_on_cancellation_failure:
            self.stopping = True

    async def __aenter__(self) -> Self:
        """Dependency order (LIFO teardown is exact reverse):

        1. client          — exits last (needed by all services)
        2. process_manager — exits 5th (kills survivors after runs complete)
        3. limit_manager   — exits 4th (release tokens after runs complete)
        4. event_emitter   — exits 3rd (flush events before client closes)
        5. runs_task_group — exits 2nd (wait for in-flight runs)
        6. FlowRunCancellingObserver — exits first
        """
        self._logger.debug("Starting runner...")
        self._tmp_dir.mkdir(parents=True, exist_ok=True)
        if not self._loop:
            self._loop = asyncio.get_event_loop()

        self._client = get_client()

        # Step 1: client
        try:
            await self._exit_stack.enter_async_context(self._client)
        except Exception as err:
            raise RuntimeError(f"Runner failed to start: client \u2014 {err}") from err

        # Instantiate the observer early so we can bind its methods as
        # callbacks to ProcessManager.  The observer OBJECT is created here
        # but its CONTEXT MANAGER is entered last (step 6) because it needs
        # runs_task_group.
        self._cancelling_observer = FlowRunCancellingObserver(
            on_cancelling=lambda flow_run_id: self._runs_task_group.start_soon(
                self._cancel_run, flow_run_id
            ),
            on_failure=lambda _: self._runs_task_group.start_soon(
                self._handle_cancellation_observer_failure
            ),
            polling_interval=self.query_seconds,
        )

        # Define async wrapper callbacks for observer's sync methods
        async def _on_process_add(flow_run_id: UUID) -> None:
            self._cancelling_observer.add_in_flight_flow_run_id(flow_run_id)

        async def _on_process_remove(flow_run_id: UUID) -> None:
            self._cancelling_observer.remove_in_flight_flow_run_id(flow_run_id)
            self._control_channel.unregister(flow_run_id)

        # Reconstruct ProcessManager with observer callbacks (replaces the
        # callback-less placeholder from __init__)
        self._process_manager = ProcessManager(
            on_add=_on_process_add,
            on_remove=_on_process_remove,
        )

        # Steps 2-3: process_manager, limit_manager
        for _svc_name, _svc in [
            ("process_manager", self._process_manager),
            ("limit_manager", self._limit_manager),
        ]:
            try:
                await self._exit_stack.enter_async_context(_svc)
            except Exception as err:
                raise RuntimeError(
                    f"Runner failed to start: {_svc_name} \u2014 {err}"
                ) from err

        # Step 4: Construct client-dependent services after client is started

        # Build a storage-aware flow resolver: deployment flow map →
        # load_flow_from_flow_run(storage_base_path=...).
        async def _resolve_flow_for_hooks(flow_run: "FlowRun") -> Flow:
            if flow_run.deployment_id and self._deployment_registry.get_flow(
                flow_run.deployment_id
            ):
                return self._deployment_registry.get_flow(flow_run.deployment_id)
            return await load_flow_from_flow_run(
                flow_run, storage_base_path=str(self._tmp_dir)
            )

        self._hook_runner = HookRunner(resolve_flow=_resolve_flow_for_hooks)
        self._state_proposer = StateProposer(client=self._client)
        self._event_emitter = EventEmitter(
            runner_name=self.name,
            client=self._client,
            get_events_client=lambda: get_events_client(checkpoint_every=1),
        )
        try:
            await self._exit_stack.enter_async_context(self._event_emitter)
        except Exception as err:
            raise RuntimeError(
                f"Runner failed to start: event_emitter \u2014 {err}"
            ) from err

        # Control channel: TCP loopback listener used to deliver control
        # intent (cancel today; suspend in a follow-up) into child
        # subprocesses before the runner kills them. Must be bound before
        # any starter spawns a child so the port is available for the child
        # env injection.
        try:
            await self._exit_stack.enter_async_context(self._control_channel)
        except Exception as err:
            raise RuntimeError(
                f"Runner failed to start: control_channel \u2014 {err}"
            ) from err

        self._cancellation_manager = CancellationManager(
            process_manager=self._process_manager,
            hook_runner=self._hook_runner,
            state_proposer=self._state_proposer,
            event_emitter=self._event_emitter,
            client=self._client,
            control_channel=self._control_channel,
        )

        # Step 5: runs_task_group
        self._runs_task_group = anyio.create_task_group()
        try:
            await self._exit_stack.enter_async_context(self._runs_task_group)
        except Exception as err:
            raise RuntimeError(
                f"Runner failed to start: runs_task_group \u2014 {err}"
            ) from err

        # Build resolve_starter factory closing over _deployment_registry
        def _resolve_starter(flow_run: "FlowRun") -> ProcessStarter:
            # If we have an in-memory flow for this deployment (add_flow path),
            # run it directly in a subprocess — no need to spawn
            # `python -m prefect.engine` to re-import the code.
            if flow_run.deployment_id is not None:
                flow = self._deployment_registry.get_flow(flow_run.deployment_id)
                if flow is not None:
                    return DirectSubprocessStarter(
                        flow=flow,
                        deployment_name=self._deployment_registry.get_deployment_name(
                            flow_run.deployment_id
                        ),
                        heartbeat_seconds=self._heartbeat_seconds,
                        control_channel=self._control_channel,
                    )
            storage = self._deployment_registry.get_storage(flow_run.deployment_id)
            return EngineCommandStarter(
                tmp_dir=self._tmp_dir,
                storage=storage,
                deployment_name=(
                    self._deployment_registry.get_deployment_name(
                        flow_run.deployment_id
                    )
                    if flow_run.deployment_id
                    else None
                ),
                heartbeat_seconds=self._heartbeat_seconds,
                control_channel=self._control_channel,
            )

        self._scheduled_run_poller = ScheduledRunPoller(
            query_seconds=self.query_seconds,
            prefetch_seconds=self._prefetch_seconds,
            client=self._client,
            limit_manager=self._limit_manager,
            deployment_registry=self._deployment_registry,
            resolve_starter=_resolve_starter,
            runs_task_group=self._runs_task_group,
            storage_objs=self._storage_objs,
            process_manager=self._process_manager,
            state_proposer=self._state_proposer,
            hook_runner=self._hook_runner,
            cancellation_manager=self._cancellation_manager,
            get_attempt_conclusion=self._control_channel.get_conclusion,
        )

        # Step 6: Enter observer context manager last
        self._cancelling_observer = await self._exit_stack.enter_async_context(
            self._cancelling_observer
        )

        if not hasattr(self, "_loops_task_group") or not self._loops_task_group:
            self._loops_task_group: anyio.abc.TaskGroup = anyio.create_task_group()

        self.started = True
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        self._logger.debug("Stopping runner...")
        if self.pause_on_shutdown:
            await self._pause_schedules()
        self.started = False

        for scope in self._scheduled_task_scopes:
            scope.cancel()

        await self._exit_stack.__aexit__(*exc_info)

        # Be tolerant to already-removed temp directories
        shutil.rmtree(str(self._tmp_dir), ignore_errors=True)
        if hasattr(self, "_runs_task_group"):
            del self._runs_task_group
        if hasattr(self, "_loops_task_group"):
            del self._loops_task_group

    def __repr__(self) -> str:
        return f"Runner(name={self.name!r})"


# ---------------------------------------------------------------------------
# Module-level re-exports
# The names below are imported at the top of this file and used here.
# They MUST remain as module-level attributes so that tests can patch them:
#   patch("prefect.runner.runner.load_flow_from_flow_run", ...)
#   mock.patch("prefect.runner.runner.threading.Thread")
# Do NOT remove these imports or relocate them inside functions.
# ---------------------------------------------------------------------------
# get_events_client     (from prefect.events.clients -- imported above)
# load_flow_from_flow_run (from prefect.flows -- imported above)
# _run_hooks            (defined above in this module)
# threading             (stdlib -- import threading must stay at module level)
