"""
Flow run subscriber that interleaves events and logs from a flow run
"""

from __future__ import annotations

import asyncio
from types import TracebackType
from typing import TYPE_CHECKING, Any, Optional, Union
from uuid import UUID

from typing_extensions import Self

from prefect.client.schemas.filters import LogFilter, LogFilterFlowRunId
from prefect.client.schemas.objects import TERMINAL_STATES, Log, StateType
from prefect.events.clients import get_events_subscriber
from prefect.events.filters import EventAnyResourceFilter, EventFilter
from prefect.events.schemas.events import Event
from prefect.logging.clients import get_logs_subscriber

if TYPE_CHECKING:
    from prefect.events.clients import PrefectEventSubscriber
    from prefect.logging.clients import PrefectLogsSubscriber

# Cap on the backoff between attempts to resume a dropped subscription.
MAX_RESUME_BACKOFF_SECONDS = 30


class FlowRunSubscriber:
    """
    Subscribes to both events and logs for a specific flow run, yielding them
    in an interleaved stream.

    This subscriber combines the event stream and log stream for a flow run into
    a single async iterator. When a terminal event (Completed, Failed, or Crashed)
    is received, the event subscription stops but log subscription continues for a
    configurable timeout to catch any straggler logs.

    Example:
        ```python
        from prefect.events.subscribers import FlowRunSubscriber

        async with FlowRunSubscriber(flow_run_id=my_flow_run_id) as subscriber:
            async for item in subscriber:
                if isinstance(item, Event):
                    print(f"Event: {item.event}")
                else:  # isinstance(item, Log)
                    print(f"Log: {item.message}")
        ```
    """

    _flow_run_id: UUID
    _queue: asyncio.Queue[Union[Log, Event, None]]
    _tasks: list[asyncio.Task[None]]
    _flow_completed: bool
    _straggler_timeout: int
    _reconnection_attempts: int
    _log_filter: LogFilter
    _event_filter: EventFilter
    _logs_subscriber: PrefectLogsSubscriber | Any
    _events_subscriber: PrefectEventSubscriber | Any
    _sentinels_received: int
    _error: Optional[Exception]

    def __init__(
        self,
        flow_run_id: UUID,
        straggler_timeout: int = 3,
        reconnection_attempts: int = 10,
    ):
        """
        Args:
            flow_run_id: The ID of the flow run to follow
            straggler_timeout: After a terminal event, how long (in seconds) to wait
                for additional logs before stopping
            reconnection_attempts: Number of times to attempt reconnection if
                the websocket connection is lost
        """
        self._flow_run_id = flow_run_id
        self._straggler_timeout = straggler_timeout
        self._reconnection_attempts = reconnection_attempts
        self._queue = asyncio.Queue()
        self._tasks = []
        self._flow_completed = False
        self._sentinels_received = 0
        self._error = None

        self._log_filter = LogFilter(flow_run_id=LogFilterFlowRunId(any_=[flow_run_id]))
        self._event_filter = EventFilter(
            any_resource=EventAnyResourceFilter(id=[f"prefect.flow-run.{flow_run_id}"])
        )

        self._logs_subscriber = None
        self._events_subscriber = None

    async def __aenter__(self) -> Self:
        """Enter the async context manager"""
        self._logs_subscriber = get_logs_subscriber(
            filter=self._log_filter, reconnection_attempts=self._reconnection_attempts
        )
        self._events_subscriber = get_events_subscriber(
            filter=self._event_filter, reconnection_attempts=self._reconnection_attempts
        )

        await self._logs_subscriber.__aenter__()
        await self._events_subscriber.__aenter__()

        self._tasks = [
            asyncio.create_task(self._consume_logs()),
            asyncio.create_task(self._consume_events()),
        ]

        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """Exit the async context manager and clean up resources"""
        for task in self._tasks:
            task.cancel()

        await asyncio.gather(*self._tasks, return_exceptions=True)

        await self._logs_subscriber.__aexit__(exc_type, exc_val, exc_tb)
        await self._events_subscriber.__aexit__(exc_type, exc_val, exc_tb)

    @property
    def flow_completed(self) -> bool:
        """Whether the flow run was observed in a terminal state.

        When this is `False` after the stream has been exhausted, the
        subscription ended before a terminal event was received or the API
        confirmed that the run finished.
        """
        return self._flow_completed

    @property
    def error(self) -> Optional[Exception]:
        """The first error raised by a consumer task, if any.

        A consumer records an error here when its underlying websocket dies
        instead of raising, so callers can distinguish a clean end of stream
        from a connection failure.
        """
        return self._error

    def _record_error(self, exc: Exception) -> None:
        if self._error is None:
            self._error = exc

    def _is_terminal_event(self, event: Event) -> bool:
        """Whether an event marks the flow run reaching a terminal state"""
        if event.resource.id != f"prefect.flow-run.{self._flow_run_id}":
            return False

        state_type_str = event.resource.get("prefect.state-type")
        if not state_type_str and "validated_state" in event.payload:
            state_type_str = event.payload["validated_state"].get("type")
        if not state_type_str:
            return False

        try:
            return StateType(state_type_str) in TERMINAL_STATES
        except ValueError:
            return False

    async def _flow_run_is_terminal(self) -> Optional[bool]:
        """Read the flow run's current state from the server.

        Returns `True`/`False` for a terminal/non-terminal state, or `None` if
        the server could not be reached. Used to decide whether a dropped
        subscription should be resumed (the run is still active) or allowed to
        end (the run has finished).
        """
        # Imported here to avoid a circular import: `prefect.events` is
        # imported while `prefect.client.orchestration` is initializing.
        from prefect.client.orchestration import get_client

        try:
            async with get_client() as client:
                flow_run = await client.read_flow_run(self._flow_run_id)
        except Exception:
            return None
        state = flow_run.state
        return state is not None and state.is_final()

    def __aiter__(self) -> Self:
        """Return self as an async iterator"""
        return self

    async def __anext__(self) -> Union[Log, Event]:
        """Get the next log or event from the interleaved stream"""
        while self._sentinels_received < len(self._tasks):
            # A consumer failed before the flow reached a terminal state. Stop
            # instead of blocking on a sibling stream that may stay open and
            # idle indefinitely; the failure is surfaced by the caller. The
            # failed consumer's sentinel unblocks any pending queue.get() so we
            # re-enter the loop and hit this check.
            if self._error is not None and not self._flow_completed:
                raise StopAsyncIteration
            if self._flow_completed:
                try:
                    item = await asyncio.wait_for(
                        self._queue.get(), timeout=self._straggler_timeout
                    )
                except asyncio.TimeoutError:
                    raise StopAsyncIteration
            else:
                item = await self._queue.get()

            if item is None:
                self._sentinels_received += 1
                continue

            return item

        raise StopAsyncIteration

    async def _consume_logs(self) -> None:
        """Background task to consume logs and put them in the queue.

        Resumes the subscription if it drops while the flow run is still
        active, so a transient websocket failure does not truncate the logs.
        """
        backoff = 0.0
        try:
            while not self._flow_completed:
                stream_error: Optional[Exception] = None
                try:
                    async for log in self._logs_subscriber:
                        backoff = 0.0
                        await self._queue.put(log)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    stream_error = exc

                if not await self._should_resume(stream_error):
                    break
                backoff = min(backoff + 1, MAX_RESUME_BACKOFF_SECONDS)
                await asyncio.sleep(backoff)
        except asyncio.CancelledError:
            pass
        finally:
            await self._queue.put(None)

    async def _consume_events(self) -> None:
        """Background task to consume events and put them in the queue.

        Resumes the subscription if it drops before a terminal event is
        observed and the flow run is still active on the server.
        """
        backoff = 0.0
        try:
            while not self._flow_completed:
                stream_error: Optional[Exception] = None
                try:
                    async for event in self._events_subscriber:
                        backoff = 0.0
                        await self._queue.put(event)
                        if self._is_terminal_event(event):
                            self._flow_completed = True
                            break
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    stream_error = exc

                if self._flow_completed or not await self._should_resume(stream_error):
                    break
                backoff = min(backoff + 1, MAX_RESUME_BACKOFF_SECONDS)
                await asyncio.sleep(backoff)
        except asyncio.CancelledError:
            pass
        finally:
            await self._queue.put(None)

    async def _should_resume(self, stream_error: Optional[Exception]) -> bool:
        """Decide whether to resume a subscription whose stream just ended.

        Resumes only while the flow run is still active on the server. If the
        run has finished, marks the shared subscriber complete and stops
        without error. If the server is unreachable, stops and records
        `stream_error` (if any) so the caller can surface the failure instead
        of reporting the run as finished.
        """
        terminal = await self._flow_run_is_terminal()
        if terminal is True:
            self._flow_completed = True
            return False
        if terminal is False:
            return True
        if terminal is None and stream_error is not None:
            self._record_error(stream_error)
        return False
