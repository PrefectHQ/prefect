from __future__ import annotations

import asyncio
import logging
import time
import uuid
from contextlib import AsyncExitStack
from datetime import datetime
from typing import Any, Protocol

from prefect._flow_run_suspension import is_suspended_flow_run_state
from prefect.client.orchestration import PrefectClient, get_client
from prefect.client.schemas.filters import (
    FlowRunFilter,
    FlowRunFilterId,
    FlowRunFilterState,
    FlowRunFilterStateName,
    FlowRunFilterStateType,
)
from prefect.client.schemas.objects import State, StateType
from prefect.events.clients import PrefectEventSubscriber, get_events_subscriber
from prefect.events.filters import EventFilter, EventNameFilter
from prefect.exceptions import ObjectNotFound
from prefect.logging.loggers import get_logger
from prefect.utilities.services import critical_service_loop

# How long to wait before warning that a suspension transition is still not
# visible on the flow run, how often to look initially, and the retry cap after
# the warning.
SUSPENSION_CONFIRMATION_WARNING_AFTER = 30.0
SUSPENSION_CONFIRMATION_INTERVAL = 0.5
SUSPENSION_CONFIRMATION_MAX_INTERVAL = 10.0


class OnCancellingCallback(Protocol):
    def __call__(self, flow_run_id: uuid.UUID) -> None: ...


class OnSuspendedCallback(Protocol):
    def __call__(self, flow_run_id: uuid.UUID, state: State) -> None: ...


class OnFailureCallback(Protocol):
    def __call__(self, flow_run_ids: set[uuid.UUID]) -> None: ...


class _SuspensionWatch:
    """Reconcile suspension events with durable states for one flow run."""

    def __init__(
        self,
        flow_run_id: uuid.UUID,
        client: PrefectClient,
        on_suspended: OnSuspendedCallback,
        logger: logging.Logger,
    ) -> None:
        self.flow_run_id = flow_run_id
        self.is_suspended = False
        self._client = client
        self._on_suspended = on_suspended
        self._logger = logger
        self._initialized = asyncio.Event()
        self._replay_checkpoint: datetime | None = None
        self._confirmation_tasks: dict[uuid.UUID, asyncio.Task[None]] = {}
        self._closed = False

    def initialize(self, state: State | None) -> None:
        """Set the initial server checkpoint and release waiting events."""
        if not self._initialized.is_set():
            self._replay_checkpoint = state.timestamp if state is not None else None
            self._initialized.set()
        self.notify_if_suspended(state)

    def notify_if_suspended(self, state: State | None) -> None:
        if (
            not self.is_suspended
            and state is not None
            and is_suspended_flow_run_state(state)
        ):
            self.is_suspended = True
            self._on_suspended(self.flow_run_id, state)

    def observe(self, state_id: uuid.UUID, occurred: datetime) -> None:
        """Confirm a new suspension event without blocking event consumption."""
        if self._closed or self.is_suspended:
            return
        if state_id in self._confirmation_tasks:
            return

        task = asyncio.create_task(self._confirm(state_id, occurred))
        self._confirmation_tasks[state_id] = task
        task.add_done_callback(
            lambda completed, state_id=state_id: self._confirmation_done(
                state_id, completed
            )
        )

    async def _confirm(self, state_id: uuid.UUID, occurred: datetime) -> None:
        await self._initialized.wait()
        if self._closed or self.is_suspended:
            return
        if self._replay_checkpoint is not None and occurred <= self._replay_checkpoint:
            self._logger.debug(
                "Ignoring replayed suspension event for flow run %s that occurred"
                " at or before the initial server state.",
                self.flow_run_id,
            )
            return

        warning_deadline = time.monotonic() + SUSPENSION_CONFIRMATION_WARNING_AFTER
        retry_interval = SUSPENSION_CONFIRMATION_INTERVAL
        warned = False
        last_error: Exception | None = None

        while not self._closed and not self.is_suspended:
            try:
                flow_run = await self._client.read_flow_run(self.flow_run_id)
            except ObjectNotFound:
                self._logger.debug(
                    "Flow run %s no longer exists; abandoning suspension confirmation.",
                    self.flow_run_id,
                )
                return
            except Exception as exc:
                last_error = exc
            else:
                state = flow_run.state
                if state is not None:
                    if state.id == state_id or is_suspended_flow_run_state(state):
                        self.notify_if_suspended(state)
                        return
                    if state.timestamp >= occurred:
                        # Superseded (e.g. resumed) before confirmation: still
                        # stop, or this engine could double-execute alongside
                        # the resumed run's fresh submission.
                        self.notify_if_suspended(
                            State(
                                id=state_id,
                                type=StateType.PAUSED,
                                name="Suspended",
                                timestamp=occurred,
                            )
                        )
                        return

            if not warned and time.monotonic() >= warning_deadline:
                self._logger.warning(
                    "Received a suspension event for flow run %s, but its state %s"
                    " has not become visible within %s seconds; continuing to"
                    " retry.",
                    self.flow_run_id,
                    state_id,
                    SUSPENSION_CONFIRMATION_WARNING_AFTER,
                    exc_info=last_error,
                )
                warned = True

            await asyncio.sleep(retry_interval)
            if warned:
                retry_interval = min(
                    max(retry_interval * 2, SUSPENSION_CONFIRMATION_INTERVAL),
                    SUSPENSION_CONFIRMATION_MAX_INTERVAL,
                )

    def _confirmation_done(self, state_id: uuid.UUID, task: asyncio.Task[None]) -> None:
        self._confirmation_tasks.pop(state_id, None)
        if task.cancelled():
            return
        if error := task.exception():
            self._logger.error(
                "Suspension confirmation failed for flow run %s and state %s.",
                self.flow_run_id,
                state_id,
                exc_info=error,
            )

    def cancel(self) -> tuple[asyncio.Task[None], ...]:
        self._closed = True
        tasks = tuple(self._confirmation_tasks.values())
        self._confirmation_tasks.clear()
        for task in tasks:
            task.cancel()
        return tasks


class FlowRunCancellingObserver:
    def __init__(
        self,
        on_cancelling: OnCancellingCallback,
        polling_interval: float = 10,
        event_filter: EventFilter | None = None,
        on_failure: OnFailureCallback | None = None,
    ):
        """
        Observer that cancels flow runs when they are marked as cancelling.

        Will use a websocket connection to listen for cancelling flow run events by default with a fallback
        to polling when the websocket connection is lost.

        Args:
            on_cancelling: Callback to call when a flow run is marked as cancelling.
            polling_interval: Interval in seconds to poll for cancelling flow runs when websocket connection is lost.
            event_filter: Optional event filter to use for the websocket subscription.
                If not provided, defaults to filtering for "prefect.flow-run.Cancelling" events.
            on_failure: Optional callback to call when both websocket and polling mechanisms fail.
                Called with the set of in-flight flow run IDs that can no longer be monitored for cancellation.
        """
        self.logger = get_logger("FlowRunCancellingObserver")
        self.on_cancelling = on_cancelling
        self.on_failure = on_failure
        self.polling_interval = polling_interval

        if event_filter is not None:
            if (
                event_filter.event is None
                or event_filter.event.name is None
                or "prefect.flow-run.Cancelling" not in event_filter.event.name
            ):
                raise ValueError(
                    "event_filter must include 'prefect.flow-run.Cancelling' in event.name"
                )
            self._event_filter = event_filter
        else:
            self._event_filter = EventFilter(
                event=EventNameFilter(name=["prefect.flow-run.Cancelling"])
            )
        self._in_flight_flow_run_ids: set[uuid.UUID] = set()
        self._events_subscriber: PrefectEventSubscriber | None
        self._exit_stack = AsyncExitStack()
        self._consumer_task: asyncio.Task[None] | None = None
        self._polling_task: asyncio.Task[None] | None = None
        self._is_shutting_down = False
        self._client: PrefectClient | None = None
        self._cancelling_flow_run_ids: set[uuid.UUID] = set()

    def add_in_flight_flow_run_id(self, flow_run_id: uuid.UUID):
        self.logger.debug("Adding in-flight flow run ID: %s", flow_run_id)
        self._in_flight_flow_run_ids.add(flow_run_id)

    def remove_in_flight_flow_run_id(self, flow_run_id: uuid.UUID):
        self.logger.debug("Removing in-flight flow run ID: %s", flow_run_id)
        self._in_flight_flow_run_ids.discard(flow_run_id)
        self._cancelling_flow_run_ids.discard(flow_run_id)

    async def _consume_events(self):
        if self._events_subscriber is None:
            raise RuntimeError(
                "Events subscriber not initialized. Please use `async with` to initialize the observer."
            )
        async for event in self._events_subscriber:
            try:
                flow_run_id = uuid.UUID(
                    event.resource["prefect.resource.id"].replace(
                        "prefect.flow-run.", ""
                    )
                )
                if flow_run_id not in self._in_flight_flow_run_ids:
                    continue
                self.on_cancelling(flow_run_id)
            except ValueError:
                self.logger.warning(
                    "Received event with invalid flow run ID: %s",
                    event.resource["prefect.resource.id"],
                )

    def _start_polling_task(self, task: asyncio.Task[None]):
        if task.cancelled():
            # If the consumer task was cancelled, the observer is shutting down
            # and we don't need to start the polling task
            return
        if exc := task.exception():
            self.logger.warning(
                "The FlowRunCancellingObserver websocket failed with an exception. Switching to polling mode.",
                exc_info=exc,
            )
            self._polling_task = asyncio.create_task(
                critical_service_loop(
                    workload=self._check_for_cancelled_flow_runs,
                    interval=self.polling_interval,
                    jitter_range=0.3,
                )
            )
            self._polling_task.add_done_callback(self._handle_polling_task_done)

    def _handle_polling_task_done(self, task: asyncio.Task[None]):
        if task.exception():
            self.logger.error(
                "Cancellation polling task failed. Execution will continue, but flow run cancellation will fail.",
                exc_info=task.exception(),
            )
            if self.on_failure is not None:
                self.on_failure(self._in_flight_flow_run_ids.copy())
        else:
            self.logger.debug("Polling task completed")

    async def _check_for_cancelled_flow_runs(self):
        if self._is_shutting_down:
            return
        if self._client is None:
            raise RuntimeError(
                "Client not initialized. Please use `async with` to initialize the observer."
            )

        self.logger.debug("Checking for cancelled flow runs")
        named_cancelling_flow_runs = await self._client.read_flow_runs(
            flow_run_filter=FlowRunFilter(
                state=FlowRunFilterState(
                    type=FlowRunFilterStateType(any_=[StateType.CANCELLED]),
                    name=FlowRunFilterStateName(any_=["Cancelling"]),
                ),
                # Avoid duplicate cancellation calls
                id=FlowRunFilterId(
                    any_=list(
                        self._in_flight_flow_run_ids - self._cancelling_flow_run_ids
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
                        self._in_flight_flow_run_ids - self._cancelling_flow_run_ids
                    )
                ),
            ),
        )

        cancelling_flow_runs = named_cancelling_flow_runs + typed_cancelling_flow_runs

        if cancelling_flow_runs:
            self.logger.info(
                "Found %s flow runs awaiting cancellation.", len(cancelling_flow_runs)
            )

        for flow_run in cancelling_flow_runs:
            self._cancelling_flow_run_ids.add(flow_run.id)
            self.on_cancelling(flow_run.id)

    async def __aenter__(self):
        try:
            self._events_subscriber = await self._exit_stack.enter_async_context(
                get_events_subscriber(filter=self._event_filter)
            )
        except Exception as e:
            self.logger.warning(
                "Failed to connect to the events stream. Falling back to polling "
                "for cancellation events. Reason: %s",
                str(e),
            )
            self._events_subscriber = None

        self._client = await self._exit_stack.enter_async_context(get_client())

        if self._events_subscriber is not None:
            self._consumer_task = asyncio.create_task(self._consume_events())
            self._consumer_task.add_done_callback(self._start_polling_task)
        else:
            # WebSocket unavailable — start polling immediately
            self._polling_task = asyncio.create_task(
                critical_service_loop(
                    workload=self._check_for_cancelled_flow_runs,
                    interval=self.polling_interval,
                    jitter_range=0.3,
                )
            )
            self._polling_task.add_done_callback(self._handle_polling_task_done)

        return self

    async def __aexit__(self, *exc_info: Any):
        self.logger.debug("Shutting down FlowRunCancellingObserver")
        self._is_shutting_down = True
        await self._exit_stack.__aexit__(*exc_info)
        if self._consumer_task is not None:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass
            except Exception:
                self.logger.warning(
                    "Consumer task exited with exception", exc_info=True
                )
                pass

        if self._polling_task is not None:
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
            except Exception:
                self.logger.warning("Polling task exited with exception", exc_info=True)
                pass


class FlowRunSuspendingObserver:
    def __init__(
        self,
        on_suspended: OnSuspendedCallback,
        polling_interval: float = 10,
        event_filter: EventFilter | None = None,
        on_failure: OnFailureCallback | None = None,
    ):
        """
        Observer that notices flow runs when they are marked as suspended.

        Uses the events stream to listen for suspension events by default, with a
        polling fallback when the websocket connection is unavailable or lost.
        """
        self.logger = get_logger("FlowRunSuspendingObserver")
        self.on_suspended = on_suspended
        self.on_failure = on_failure
        self.polling_interval = polling_interval

        if event_filter is not None:
            if (
                event_filter.event is None
                or event_filter.event.name is None
                or "prefect.flow-run.Suspended" not in event_filter.event.name
            ):
                raise ValueError(
                    "event_filter must include 'prefect.flow-run.Suspended' in event.name"
                )
            self._event_filter = event_filter
        else:
            self._event_filter = EventFilter(
                event=EventNameFilter(name=["prefect.flow-run.Suspended"])
            )
        self._events_subscriber: PrefectEventSubscriber | None
        self._exit_stack = AsyncExitStack()
        self._consumer_task: asyncio.Task[None] | None = None
        self._polling_task: asyncio.Task[None] | None = None
        self._is_shutting_down = False
        self._client: PrefectClient | None = None
        self._watches: dict[uuid.UUID, _SuspensionWatch] = {}

    @property
    def _in_flight_flow_run_ids(self) -> set[uuid.UUID]:
        return set(self._watches)

    def add_in_flight_flow_run_id(self, flow_run_id: uuid.UUID):
        if self._client is None:
            raise RuntimeError(
                "Client not initialized. Please use `async with` to initialize the observer."
            )
        self.logger.debug("Adding in-flight flow run ID: %s", flow_run_id)
        if flow_run_id not in self._watches:
            watch = self._watches[flow_run_id] = self._create_watch(flow_run_id)
            watch.initialize(None)

    def _create_watch(self, flow_run_id: uuid.UUID) -> _SuspensionWatch:
        if self._client is None:
            raise RuntimeError(
                "Client not initialized. Please use `async with` to initialize the observer."
            )
        return _SuspensionWatch(
            flow_run_id=flow_run_id,
            client=self._client,
            on_suspended=self.on_suspended,
            logger=self.logger,
        )

    def remove_in_flight_flow_run_id(self, flow_run_id: uuid.UUID):
        self.logger.debug("Removing in-flight flow run ID: %s", flow_run_id)
        if watch := self._watches.pop(flow_run_id, None):
            watch.cancel()

    async def watch_flow_run_id(self, flow_run_id: uuid.UUID) -> None:
        if self._client is None:
            raise RuntimeError(
                "Client not initialized. Please use `async with` to initialize the observer."
            )
        self.logger.debug("Adding in-flight flow run ID: %s", flow_run_id)
        if flow_run_id not in self._watches:
            self._watches[flow_run_id] = self._create_watch(flow_run_id)
        retry_interval = max(min(self.polling_interval, 1.0), 0.01)
        attempts = 0

        while not self._is_shutting_down:
            watch = self._watches.get(flow_run_id)
            if watch is None or watch.is_suspended:
                return

            try:
                flow_run = await self._client.read_flow_run(flow_run_id)
            except Exception:
                attempts += 1
                log = self.logger.warning if attempts == 1 else self.logger.debug
                log(
                    "Failed to check current state for flow run %s while starting"
                    " suspension observer. Retrying before reporting observer ready.",
                    flow_run_id,
                    exc_info=True,
                )
                await asyncio.sleep(retry_interval)
                continue

            watch.initialize(flow_run.state)
            return

    def _notify_if_suspended_state(
        self, flow_run_id: uuid.UUID, state: State | None
    ) -> None:
        if watch := self._watches.get(flow_run_id):
            watch.notify_if_suspended(state)

    async def _consume_events(self):
        if self._events_subscriber is None:
            raise RuntimeError(
                "Events subscriber not initialized. Please use `async with` to initialize the observer."
            )
        async for event in self._events_subscriber:
            try:
                flow_run_id = uuid.UUID(
                    event.resource["prefect.resource.id"].replace(
                        "prefect.flow-run.", ""
                    )
                )
                watch = self._watches.get(flow_run_id)
                if watch is None:
                    continue

                # State change events carry the ID of the state they report, so the
                # event identifies the exact transition to confirm. Confirmation is
                # done in a separate task to keep consuming events while we wait.
                watch.observe(event.id, event.occurred)
            except ValueError:
                self.logger.warning(
                    "Received event with invalid flow run ID: %s",
                    event.resource["prefect.resource.id"],
                )

    def _start_polling_task(self, task: asyncio.Task[None]):
        if task.cancelled() or self._is_shutting_down:
            return

        if exc := task.exception():
            self.logger.warning(
                "The FlowRunSuspendingObserver websocket failed with an exception. Switching to polling mode.",
                exc_info=exc,
            )
        else:
            self.logger.warning(
                "The FlowRunSuspendingObserver websocket closed. Switching to polling mode.",
            )

        self._polling_task = asyncio.create_task(
            critical_service_loop(
                workload=self._check_for_suspended_flow_runs,
                interval=self.polling_interval,
                jitter_range=0.3,
            )
        )
        self._polling_task.add_done_callback(self._handle_polling_task_done)

    def _handle_polling_task_done(self, task: asyncio.Task[None]):
        if task.exception():
            self.logger.error(
                "Suspension polling task failed. Execution will continue, but external flow run suspension will fail.",
                exc_info=task.exception(),
            )
            if self.on_failure is not None:
                self.on_failure(self._in_flight_flow_run_ids.copy())
        else:
            self.logger.debug("Polling task completed")

    async def _check_for_suspended_flow_runs(self):
        if self._is_shutting_down:
            return
        if self._client is None:
            raise RuntimeError(
                "Client not initialized. Please use `async with` to initialize the observer."
            )

        flow_run_ids = {
            flow_run_id
            for flow_run_id, watch in self._watches.items()
            if not watch.is_suspended
        }
        if not flow_run_ids:
            return

        self.logger.debug("Checking for suspended flow runs")
        suspended_flow_runs = await self._client.read_flow_runs(
            flow_run_filter=FlowRunFilter(
                state=FlowRunFilterState(
                    type=FlowRunFilterStateType(any_=[StateType.PAUSED]),
                    name=FlowRunFilterStateName(any_=["Suspended"]),
                ),
                id=FlowRunFilterId(any_=list(flow_run_ids)),
            ),
        )

        if suspended_flow_runs:
            self.logger.info(
                "Found %s flow runs awaiting suspension.", len(suspended_flow_runs)
            )

        for flow_run in suspended_flow_runs:
            if flow_run.state:
                self._notify_if_suspended_state(flow_run.id, flow_run.state)

    async def __aenter__(self):
        try:
            self._events_subscriber = await self._exit_stack.enter_async_context(
                get_events_subscriber(filter=self._event_filter)
            )
        except Exception as e:
            self.logger.warning(
                "Failed to connect to the events stream. Falling back to polling "
                "for suspension events. Reason: %s",
                str(e),
            )
            self._events_subscriber = None

        self._client = await self._exit_stack.enter_async_context(get_client())

        if self._events_subscriber is not None:
            self._consumer_task = asyncio.create_task(self._consume_events())
            self._consumer_task.add_done_callback(self._start_polling_task)
        else:
            self._polling_task = asyncio.create_task(
                critical_service_loop(
                    workload=self._check_for_suspended_flow_runs,
                    interval=self.polling_interval,
                    jitter_range=0.3,
                )
            )
            self._polling_task.add_done_callback(self._handle_polling_task_done)

        return self

    async def __aexit__(self, *exc_info: Any):
        self.logger.debug("Shutting down FlowRunSuspendingObserver")
        self._is_shutting_down = True
        tasks = [task for watch in self._watches.values() for task in watch.cancel()]
        self._watches.clear()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await self._exit_stack.__aexit__(*exc_info)
        if self._consumer_task is not None:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass
            except Exception:
                self.logger.warning(
                    "Consumer task exited with exception", exc_info=True
                )
                pass

        if self._polling_task is not None:
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
            except Exception:
                self.logger.warning("Polling task exited with exception", exc_info=True)
                pass
