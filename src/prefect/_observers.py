from __future__ import annotations

import asyncio
import uuid
from contextlib import AsyncExitStack
from typing import Any, Protocol

from prefect.client.orchestration import PrefectClient, get_client
from prefect.client.schemas.filters import (
    FlowRunFilter,
    FlowRunFilterId,
    FlowRunFilterState,
    FlowRunFilterStateName,
    FlowRunFilterStateType,
)
from prefect.client.schemas.objects import StateType
from prefect.events.clients import PrefectEventSubscriber, get_events_subscriber
from prefect.events.filters import EventFilter, EventNameFilter
from prefect.logging.loggers import get_logger
from prefect.utilities.services import critical_service_loop


class OnCancellingCallback(Protocol):
    def __call__(self, flow_run_id: uuid.UUID) -> None: ...


class OnFailureCallback(Protocol):
    def __call__(self, flow_run_ids: set[uuid.UUID]) -> None: ...


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
        self._events_subscriber = await self._exit_stack.enter_async_context(
            get_events_subscriber(filter=self._event_filter)
        )
        self._client = await self._exit_stack.enter_async_context(get_client())
        self._consumer_task = asyncio.create_task(self._consume_events())
        self._consumer_task.add_done_callback(self._start_polling_task)
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
