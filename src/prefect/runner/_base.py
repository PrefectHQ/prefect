"""
Base runner class with shared orchestration logic.
"""

from __future__ import annotations

import abc
import asyncio
import datetime
import inspect
import logging
import shutil
import signal
import sys
import tempfile
import threading
import uuid
from contextlib import AsyncExitStack
from functools import partial
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Coroutine,
    Generic,
    Iterable,
    List,
    Optional,
    TypeVar,
    Union,
)
from uuid import UUID, uuid4

import anyio
import anyio.abc
from cachetools import LRUCache
from typing_extensions import Self

from prefect._experimental.bundles import (
    SerializedBundle,
    extract_flow_from_bundle,
)
from prefect._internal.concurrency.api import create_call, from_sync
from prefect.client.orchestration import PrefectClient, get_client
from prefect.client.schemas.objects import (
    ConcurrencyLimitConfig,
    State,
    StateType,
)
from prefect.client.schemas.objects import Flow as APIFlow
from prefect.events import DeploymentTriggerTypes, TriggerTypes
from prefect.events.clients import EventsClient, get_events_client
from prefect.events.related import tags_as_related_resources
from prefect.events.schemas.events import Event, RelatedResource, Resource
from prefect.exceptions import Abort, ObjectNotFound
from prefect.flows import Flow, FlowStateHook, load_flow_from_flow_run
from prefect.logging.loggers import PrefectLogAdapter, flow_run_logger, get_logger
from prefect.runner._observers import FlowRunCancellingObserver
from prefect.runner.storage import RunnerStorage
from prefect.schedules import Schedule
from prefect.settings import (
    PREFECT_API_URL,
    PREFECT_RUNNER_SERVER_ENABLE,
    get_current_settings,
)
from prefect.states import (
    Crashed,
    Pending,
    exception_to_failed_state,
)
from prefect.types._datetime import now
from prefect.types.entrypoint import EntrypointType
from prefect.utilities.annotations import NotSet
from prefect.utilities.asyncutils import (
    is_async_fn,
    sync_compatible,
)
from prefect.utilities.engine import propose_state
from prefect.utilities.services import (
    critical_service_loop,
    start_client_metrics_server,
)
from prefect.utilities.slugify import slugify

if TYPE_CHECKING:
    import concurrent.futures

    from prefect.client.schemas.objects import FlowRun
    from prefect.client.schemas.responses import DeploymentResponse
    from prefect.client.types.flexible_schedule_list import FlexibleScheduleList
    from prefect.deployments.runner import RunnerDeployment


# Type variable for execution handles (PID, task handle, etc.)
ExecutionHandleT = TypeVar("ExecutionHandleT")


class BaseRunner(Generic[ExecutionHandleT], abc.ABC):
    """Abstract base class for runners with shared orchestration logic."""

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
        Base runner initialization with shared configuration.

        Args:
            name: The name of the runner. If not provided, a random one
                will be generated. If provided, it cannot contain '/' or '%'.
            query_seconds: The number of seconds to wait between querying for
                scheduled flow runs; defaults to `PREFECT_RUNNER_POLL_FREQUENCY`
            prefetch_seconds: The number of seconds to prefetch flow runs for.
            heartbeat_seconds: The number of seconds to wait between emitting
                flow run heartbeats. The runner will not emit heartbeats if the value is None.
                Defaults to `PREFECT_RUNNER_HEARTBEAT_FREQUENCY`.
            limit: The maximum number of flow runs this runner should be running at. Provide `None` for no limit.
                If not provided, the runner will use the value of `PREFECT_RUNNER_PROCESS_LIMIT`.
            pause_on_shutdown: A boolean for whether or not to automatically pause
                deployment schedules on shutdown; defaults to `True`
            webserver: a boolean flag for whether to start a webserver for this runner
        """
        settings = get_current_settings()

        if name and ("/" in name or "%" in name):
            raise ValueError("Runner name cannot contain '/' or '%'")
        self.name: str = Path(name).stem if name is not None else f"runner-{uuid4()}"
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
        self.heartbeat_seconds: float | None = (
            heartbeat_seconds or settings.runner.heartbeat_frequency
        )
        if self.heartbeat_seconds is not None and self.heartbeat_seconds < 30:
            raise ValueError("Heartbeat must be 30 seconds or greater.")
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._events_client: EventsClient = get_events_client(checkpoint_every=1)

        self._exit_stack = AsyncExitStack()
        self._limiter: anyio.CapacityLimiter | None = None
        self._cancelling_observer: FlowRunCancellingObserver | None = None
        self._client: PrefectClient = get_client()
        self._submitting_flow_run_ids: set[UUID] = set()
        self._cancelling_flow_run_ids: set[UUID] = set()
        self._scheduled_task_scopes: set[anyio.abc.CancelScope] = set()
        self._deployment_ids: set[UUID] = set()
        self.__execution_map_lock: asyncio.Lock | None = None

        self._tmp_dir: Path = (
            Path(tempfile.gettempdir()) / "runner_storage" / str(uuid4())
        )
        self._storage_objs: list[RunnerStorage] = []
        self._deployment_storage_map: dict[UUID, RunnerStorage] = {}

        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # Caching
        self._deployment_cache: LRUCache[UUID, "DeploymentResponse"] = LRUCache(
            maxsize=100
        )
        self._flow_cache: LRUCache[UUID, "APIFlow"] = LRUCache(maxsize=100)

        # Keep track of added flows so we can run them directly
        self._deployment_flow_map: dict[UUID, "Flow[Any, Any]"] = dict()
        self._flow_run_bundle_map: dict[UUID, SerializedBundle] = dict()

    @property
    def _execution_map_lock(self) -> asyncio.Lock:
        """Lock for managing execution tracking."""
        if self.__execution_map_lock is None:
            self.__execution_map_lock = asyncio.Lock()
        return self.__execution_map_lock

    # Abstract methods that must be implemented by subclasses

    @abc.abstractmethod
    async def _add_execution_entry(
        self, flow_run: "FlowRun", handle: ExecutionHandleT
    ) -> None:
        """Add an execution tracking entry."""
        ...

    @abc.abstractmethod
    async def _remove_execution_entry(self, flow_run_id: UUID) -> None:
        """Remove an execution tracking entry."""
        ...

    @abc.abstractmethod
    async def _cancel_execution(self, flow_run: "FlowRun") -> None:
        """Cancel a running execution."""
        ...

    @abc.abstractmethod
    async def _execute_flow_run_impl(
        self,
        flow_run: "FlowRun",
        task_status: anyio.abc.TaskStatus[ExecutionHandleT],
        entrypoint: str | None = None,
        command: str | None = None,
        cwd: Path | str | None = None,
        env: dict[str, str | None] | None = None,
        stream_output: bool = True,
    ) -> Optional[int]:
        """
        Execute a flow run and return exit code (or None if not applicable).

        This is the core execution method that must be implemented by subclasses.
        """
        ...

    @abc.abstractmethod
    async def _get_all_execution_entries(self) -> list[tuple[UUID, "FlowRun"]]:
        """Get all active execution entries as (flow_run_id, flow_run) tuples."""
        ...

    # Shared orchestration methods

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
        apply_coro = deployment.apply()
        if TYPE_CHECKING:
            assert inspect.isawaitable(apply_coro)
        deployment_id = await apply_coro
        storage = deployment.storage
        if storage is not None:
            add_storage_coro = self._add_storage(storage)
            if TYPE_CHECKING:
                assert inspect.isawaitable(add_storage_coro)
            storage = await add_storage_coro
            self._deployment_storage_map[deployment_id] = storage
        self._deployment_ids.add(deployment_id)

        return deployment_id

    @sync_compatible
    async def add_flow(
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
        """
        api = PREFECT_API_URL.value()
        if any([interval, cron, rrule, schedule, schedules]) and not api:
            self._logger.warning(
                "Cannot schedule flows on an ephemeral server; run `prefect server"
                " start` to start the scheduler."
            )
        name = self.name if name is None else name

        to_deployment_coro = flow.to_deployment(
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
        if TYPE_CHECKING:
            assert inspect.isawaitable(to_deployment_coro)
        deployment = await to_deployment_coro

        add_deployment_coro = self.add_deployment(deployment)
        if TYPE_CHECKING:
            assert inspect.isawaitable(add_deployment_coro)
        deployment_id = await add_deployment_coro

        # Only add the flow to the map if it is not loaded from storage
        if not getattr(flow, "_storage", None):
            self._deployment_flow_map[deployment_id] = flow
        return deployment_id

    @sync_compatible
    async def _add_storage(self, storage: RunnerStorage) -> RunnerStorage:
        """
        Adds a storage object to the runner.
        """
        if storage not in self._storage_objs:
            from copy import deepcopy

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
        """Gracefully shuts down the runner when a SIGTERM is received."""
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
            webserver: a boolean for whether to start a webserver for this runner.
        """
        from prefect.runner.server import start_webserver

        if threading.current_thread() is threading.main_thread():
            signal.signal(signal.SIGTERM, self.handle_sigterm)

        webserver = webserver if webserver is not None else self.webserver

        if webserver or PREFECT_RUNNER_SERVER_ENABLE.value():
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
            async with self._loops_task_group as loops_task_group:
                for storage in self._storage_objs:
                    if storage.pull_interval:
                        loops_task_group.start_soon(
                            partial(
                                critical_service_loop,
                                workload=storage.pull_code,
                                interval=storage.pull_interval,
                                run_once=run_once,
                                jitter_range=0.3,
                            )
                        )
                    else:
                        loops_task_group.start_soon(storage.pull_code)
                loops_task_group.start_soon(
                    partial(
                        critical_service_loop,
                        workload=runner._get_and_submit_flow_runs,
                        interval=self.query_seconds,
                        run_once=run_once,
                        jitter_range=0.3,
                    )
                )

    def execute_in_background(
        self, func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> "concurrent.futures.Future[Any]":
        """Executes a function in the background."""
        if TYPE_CHECKING:
            assert self._loop is not None

        return asyncio.run_coroutine_threadsafe(func(*args, **kwargs), self._loop)

    async def cancel_all(self) -> None:
        """Cancel all running flow runs."""
        runs_to_cancel: list["FlowRun"] = []

        for _, flow_run in await self._get_all_execution_entries():
            runs_to_cancel.append(flow_run)

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

    def _get_flow_run_logger(self, flow_run: "FlowRun") -> PrefectLogAdapter:
        """Get a logger for a specific flow run."""
        return flow_run_logger(flow_run=flow_run).getChild(
            "runner",
            extra={
                "runner_name": self.name,
            },
        )

    async def _get_flow_and_deployment(
        self, flow_run: "FlowRun"
    ) -> tuple[Optional["APIFlow"], Optional["DeploymentResponse"]]:
        """Get flow and deployment information for a flow run."""
        deployment: Optional["DeploymentResponse"] = (
            self._deployment_cache.get(flow_run.deployment_id)
            if flow_run.deployment_id
            else None
        )
        flow: Optional["APIFlow"] = self._flow_cache.get(flow_run.flow_id)
        if not deployment and flow_run.deployment_id is not None:
            try:
                deployment = await self._client.read_deployment(flow_run.deployment_id)
                self._deployment_cache[flow_run.deployment_id] = deployment
            except ObjectNotFound:
                deployment = None
        if not flow:
            try:
                flow = await self._client.read_flow(flow_run.flow_id)
                self._flow_cache[flow_run.flow_id] = flow
            except ObjectNotFound:
                flow = None
        return flow, deployment

    async def _emit_flow_run_heartbeats(self):
        """Emit heartbeats for all running flow runs."""
        coros: list[Coroutine[Any, Any, Any]] = []
        for _, flow_run in await self._get_all_execution_entries():
            coros.append(self._emit_flow_run_heartbeat(flow_run))
        await asyncio.gather(*coros)

    async def _emit_flow_run_heartbeat(self, flow_run: "FlowRun"):
        """Emit a heartbeat event for a flow run."""
        from prefect import __version__

        related: list[RelatedResource] = []
        tags: list[str] = []

        flow, deployment = await self._get_flow_and_deployment(flow_run)
        if deployment:
            related.append(deployment.as_related_resource())
            tags.extend(deployment.tags)
        if flow:
            related.append(
                RelatedResource(
                    {
                        "prefect.resource.id": f"prefect.flow.{flow.id}",
                        "prefect.resource.role": "flow",
                        "prefect.resource.name": flow.name,
                    }
                )
            )
        tags.extend(flow_run.tags)

        related = [RelatedResource.model_validate(r) for r in related]
        related += tags_as_related_resources(set(tags))

        await self._events_client.emit(
            Event(
                event="prefect.flow-run.heartbeat",
                resource=Resource(
                    {
                        "prefect.resource.id": f"prefect.flow-run.{flow_run.id}",
                        "prefect.resource.name": flow_run.name,
                        "prefect.version": __version__,
                    }
                ),
                related=related,
            )
        )

    def _event_resource(self):
        """Get the event resource for this runner."""
        from prefect import __version__

        return {
            "prefect.resource.id": f"prefect.runner.{slugify(self.name)}",
            "prefect.resource.name": self.name,
            "prefect.version": __version__,
        }

    async def _emit_flow_run_cancelled_event(
        self,
        flow_run: "FlowRun",
        flow: "Optional[APIFlow]",
        deployment: "Optional[DeploymentResponse]",
    ):
        """Emit a cancellation event for a flow run."""
        related: list[RelatedResource] = []
        tags: list[str] = []
        if deployment:
            related.append(deployment.as_related_resource())
            tags.extend(deployment.tags)
        if flow:
            related.append(
                RelatedResource(
                    {
                        "prefect.resource.id": f"prefect.flow.{flow.id}",
                        "prefect.resource.role": "flow",
                        "prefect.resource.name": flow.name,
                    }
                )
            )
        related.append(
            RelatedResource(
                {
                    "prefect.resource.id": f"prefect.flow-run.{flow_run.id}",
                    "prefect.resource.role": "flow-run",
                    "prefect.resource.name": flow_run.name,
                }
            )
        )
        tags.extend(flow_run.tags)

        related = [RelatedResource.model_validate(r) for r in related]
        related += tags_as_related_resources(set(tags))

        await self._events_client.emit(
            Event(
                event="prefect.runner.cancelled-flow-run",
                resource=Resource(self._event_resource()),
                related=related,
            )
        )
        self._logger.debug(f"Emitted flow run heartbeat event for {flow_run.id}")

    async def _get_scheduled_flow_runs(
        self,
    ) -> list["FlowRun"]:
        """Retrieve scheduled flow runs for this runner."""
        scheduled_before = now("UTC") + datetime.timedelta(
            seconds=int(self._prefetch_seconds)
        )
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
            bool: True if the limit has not been reached, False otherwise.
        """
        if not self._limiter:
            return False
        return self._limiter.available_tokens > 0

    def _acquire_limit_slot(self, flow_run_id: UUID) -> bool:
        """
        Enforces flow run limit set on runner.

        Returns:
            bool: True if a slot was acquired, False otherwise.
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
            if TYPE_CHECKING:
                assert self._limiter is not None
            self._logger.debug(
                f"Flow run limit reached; {self._limiter.borrowed_tokens} flow runs"
                " in progress. You can control this limit by adjusting the "
                "PREFECT_RUNNER_PROCESS_LIMIT setting."
            )
            return False

    def _release_limit_slot(self, flow_run_id: UUID) -> None:
        """Frees up a slot taken by the given flow run id."""
        if self._limiter:
            self._limiter.release_on_behalf_of(flow_run_id)
            self._logger.debug("Limit slot released for flow run '%s'", flow_run_id)

    async def _get_and_submit_flow_runs(self):
        """Query for and submit scheduled flow runs."""
        if self.stopping:
            return
        runs_response = await self._get_scheduled_flow_runs()
        self.last_polled: datetime.datetime = now("UTC")
        return await self._submit_scheduled_flow_runs(flow_run_response=runs_response)

    async def _cancel_run(
        self, flow_run: "FlowRun | uuid.UUID", state_msg: Optional[str] = None
    ):
        """Cancel a running flow run."""
        if isinstance(flow_run, uuid.UUID):
            flow_run = await self._client.read_flow_run(flow_run)
        run_logger = self._get_flow_run_logger(flow_run)

        try:
            await self._cancel_execution(flow_run)
        except RuntimeError as exc:
            self._logger.warning(f"{exc} Marking flow run as cancelled.")
            if flow_run.state:
                await self._run_on_cancellation_hooks(flow_run, flow_run.state)
            await self._mark_flow_run_as_cancelled(flow_run)
        except Exception:
            run_logger.exception(
                "Encountered exception while cancelling flow run "
                f"'{flow_run.id}'. Flow run may not be cancelled."
            )
            self._cancelling_flow_run_ids.discard(flow_run.id)
        else:
            if flow_run.state:
                await self._run_on_cancellation_hooks(flow_run, flow_run.state)
            await self._mark_flow_run_as_cancelled(
                flow_run,
                state_updates={
                    "message": state_msg or "Flow run was cancelled successfully."
                },
            )

            flow, deployment = await self._get_flow_and_deployment(flow_run)
            await self._emit_flow_run_cancelled_event(
                flow_run=flow_run, flow=flow, deployment=deployment
            )
            run_logger.info(f"Cancelled flow run '{flow_run.name}'!")

    async def _submit_scheduled_flow_runs(
        self,
        flow_run_response: list["FlowRun"],
        entrypoints: list[str] | None = None,
    ) -> list["FlowRun"]:
        """
        Takes a list of FlowRuns and submits the referenced flow runs
        for execution by the runner.
        """
        submittable_flow_runs = sorted(
            flow_run_response,
            key=lambda run: run.next_scheduled_start_time or datetime.datetime.max,
        )

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
                        entrypoint=entrypoints[i] if entrypoints else None,
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
        """Submits a given flow run for execution by the runner."""
        run_logger = self._get_flow_run_logger(flow_run)

        ready_to_submit = await self._propose_pending_state(flow_run)

        if ready_to_submit:
            readiness_result: (
                ExecutionHandleT | Exception
            ) = await self._runs_task_group.start(
                partial(
                    self._submit_run_and_capture_errors,
                    flow_run=flow_run,
                    entrypoint=entrypoint,
                ),
            )

            if readiness_result and not isinstance(readiness_result, Exception):
                await self._add_execution_entry(flow_run, readiness_result)

            # Heartbeats are opt-in and only emitted if a heartbeat frequency is set
            if self.heartbeat_seconds is not None:
                await self._emit_flow_run_heartbeat(flow_run)

            run_logger.info(f"Completed submission of flow run '{flow_run.id}'")
        else:
            # If the run is not ready to submit, release the concurrency slot
            self._release_limit_slot(flow_run.id)

        self._submitting_flow_run_ids.discard(flow_run.id)

    async def _submit_run_and_capture_errors(
        self,
        flow_run: "FlowRun",
        task_status: anyio.abc.TaskStatus[ExecutionHandleT | Exception],
        entrypoint: str | None = None,
        command: str | None = None,
        cwd: Path | str | None = None,
        env: dict[str, str | None] | None = None,
        stream_output: bool = True,
    ) -> Union[Optional[int], Exception]:
        """Submit a run and capture any errors that occur."""
        run_logger = self._get_flow_run_logger(flow_run)

        try:
            exit_code = await self._execute_flow_run_impl(
                flow_run=flow_run,
                task_status=task_status,
                entrypoint=entrypoint,
                command=command,
                cwd=cwd,
                env=env,
                stream_output=stream_output,
            )

            # Subclasses can handle exit code interpretation
            await self._handle_execution_result(flow_run, exit_code)

        except Exception as exc:
            if not task_status._future.done():  # type: ignore
                run_logger.exception(
                    f"Failed to start execution for flow run '{flow_run.id}'."
                )
                task_status.started(exc)
                message = f"Flow run execution could not be started:\n{exc!r}"
                await self._propose_crashed_state(flow_run, message)
            else:
                run_logger.exception(
                    f"An error occurred while monitoring flow run '{flow_run.id}'. "
                    "The flow run will not be marked as failed, but an issue may have "
                    "occurred."
                )
            return exc
        finally:
            self._release_limit_slot(flow_run.id)
            await self._remove_execution_entry(flow_run.id)

        return exit_code

    async def _handle_execution_result(
        self, flow_run: "FlowRun", exit_code: Optional[int]
    ) -> None:
        """
        Handle the result of flow run execution.

        Subclasses can override this to interpret exit codes or handle completion.
        Default implementation does nothing - useful for async runners where there
        may be no exit code.
        """
        pass

    async def _propose_pending_state(self, flow_run: "FlowRun") -> bool:
        """Propose a pending state for a flow run."""
        run_logger = self._get_flow_run_logger(flow_run)
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
        """Propose a failed state for a flow run."""
        run_logger = self._get_flow_run_logger(flow_run)
        try:
            await propose_state(
                self._client,
                await exception_to_failed_state(message="Submission failed.", exc=exc),
                flow_run_id=flow_run.id,
            )
        except Abort:
            pass
        except Exception:
            run_logger.error(
                f"Failed to update state of flow run '{flow_run.id}'",
                exc_info=True,
            )

    async def _propose_crashed_state(
        self, flow_run: "FlowRun", message: str
    ) -> State[Any] | None:
        """Propose a crashed state for a flow run."""
        run_logger = self._get_flow_run_logger(flow_run)
        state = None
        try:
            state = await propose_state(
                self._client,
                Crashed(message=message),
                flow_run_id=flow_run.id,
            )
        except Abort:
            pass
        except Exception:
            run_logger.exception(f"Failed to update state of flow run '{flow_run.id}'")
        else:
            if state.is_crashed():
                run_logger.info(
                    f"Reported flow run '{flow_run.id}' as crashed: {message}"
                )
        return state

    async def _mark_flow_run_as_cancelled(
        self, flow_run: "FlowRun", state_updates: Optional[dict[str, Any]] = None
    ) -> None:
        """Mark a flow run as cancelled."""
        state_updates = state_updates or {}
        state_updates.setdefault("name", "Cancelled")
        state_updates.setdefault("type", StateType.CANCELLED)
        state = (
            flow_run.state.model_copy(update=state_updates) if flow_run.state else None
        )
        if not state:
            self._logger.warning(
                f"Could not find state for flow run {flow_run.id} and cancellation cannot be guaranteed."
            )
            return

        await self._client.set_flow_run_state(flow_run.id, state, force=True)

    async def _run_on_cancellation_hooks(
        self,
        flow_run: "FlowRun",
        state: State,
    ) -> None:
        """Run the cancellation hooks for a flow."""
        run_logger = self._get_flow_run_logger(flow_run)
        if state.is_cancelling():
            try:
                if flow_run.id in self._flow_run_bundle_map:
                    flow = extract_flow_from_bundle(
                        self._flow_run_bundle_map[flow_run.id]
                    )
                elif flow_run.deployment_id and self._deployment_flow_map.get(
                    flow_run.deployment_id
                ):
                    flow = self._deployment_flow_map[flow_run.deployment_id]
                else:
                    run_logger.info("Loading flow to check for on_cancellation hooks")
                    flow = await load_flow_from_flow_run(
                        flow_run, storage_base_path=str(self._tmp_dir)
                    )
                hooks = flow.on_cancellation_hooks or []

                await _run_hooks(hooks, flow_run, flow, state)
            except Exception:
                run_logger.warning(
                    f"Runner failed to retrieve flow to execute on_cancellation hooks for flow run {flow_run.id!r}.",
                    exc_info=True,
                )

    async def _run_on_crashed_hooks(
        self,
        flow_run: "FlowRun",
        state: State,
    ) -> None:
        """Run the crashed hooks for a flow."""
        run_logger = self._get_flow_run_logger(flow_run)
        if state.is_crashed():
            try:
                if flow_run.id in self._flow_run_bundle_map:
                    flow = extract_flow_from_bundle(
                        self._flow_run_bundle_map[flow_run.id]
                    )
                elif flow_run.deployment_id and self._deployment_flow_map.get(
                    flow_run.deployment_id
                ):
                    flow = self._deployment_flow_map[flow_run.deployment_id]
                else:
                    run_logger.info("Loading flow to check for on_crashed hooks")
                    flow = await load_flow_from_flow_run(
                        flow_run, storage_base_path=str(self._tmp_dir)
                    )
                hooks = flow.on_crashed_hooks or []

                await _run_hooks(hooks, flow_run, flow, state)
            except Exception:
                run_logger.warning(
                    f"Runner failed to retrieve flow to execute on_crashed hooks for flow run {flow_run.id!r}.",
                    exc_info=True,
                )

    async def _pause_schedules(self):
        """Pauses all deployment schedules."""
        self._logger.info("Pausing all deployments...")
        for deployment_id in self._deployment_ids:
            await self._client.pause_deployment(deployment_id)
            self._logger.debug(f"Paused deployment '{deployment_id}'")

        self._logger.info("All deployments have been paused!")

    async def __aenter__(self) -> Self:
        """Enter the async context."""
        self._logger.debug("Starting runner...")
        self._client = get_client()
        self._tmp_dir.mkdir(parents=True, exist_ok=True)

        self._limiter = anyio.CapacityLimiter(self.limit) if self.limit else None

        if not hasattr(self, "_loop") or not self._loop:
            self._loop = asyncio.get_event_loop()

        self._cancelling_observer = await self._exit_stack.enter_async_context(
            FlowRunCancellingObserver(
                on_cancelling=lambda flow_run_id: self._runs_task_group.start_soon(
                    self._cancel_run, flow_run_id
                ),
                polling_interval=self.query_seconds,
            )
        )
        await self._exit_stack.enter_async_context(self._client)
        await self._exit_stack.enter_async_context(self._events_client)

        if not hasattr(self, "_runs_task_group") or not self._runs_task_group:
            self._runs_task_group: anyio.abc.TaskGroup = anyio.create_task_group()
        await self._exit_stack.enter_async_context(self._runs_task_group)

        if not hasattr(self, "_loops_task_group") or not self._loops_task_group:
            self._loops_task_group: anyio.abc.TaskGroup = anyio.create_task_group()

        if self.heartbeat_seconds is not None:
            self._heartbeat_task = asyncio.create_task(
                critical_service_loop(
                    workload=self._emit_flow_run_heartbeats,
                    interval=self.heartbeat_seconds,
                    jitter_range=0.3,
                )
            )

        self.started = True
        return self

    async def __aexit__(self, *exc_info: Any) -> None:
        """Exit the async context."""
        self._logger.debug("Stopping runner...")
        if self.pause_on_shutdown:
            await self._pause_schedules()
        self.started = False

        for scope in self._scheduled_task_scopes:
            scope.cancel()

        await self._exit_stack.__aexit__(*exc_info)

        shutil.rmtree(str(self._tmp_dir), ignore_errors=True)
        del self._runs_task_group, self._loops_task_group

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"


async def _run_hooks(
    hooks: list[FlowStateHook[Any, Any]],
    flow_run: "FlowRun",
    flow: "Flow[..., Any]",
    state: State,
):
    """Run flow state hooks."""
    from prefect._internal.concurrency.api import from_async

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
