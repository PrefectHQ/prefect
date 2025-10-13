"""
Flow run subscriber that interleaves events and logs from a flow run
"""

import asyncio
from types import TracebackType
from typing import Any, Optional, Union
from uuid import UUID

from typing_extensions import Self

from prefect.client.schemas.filters import LogFilter, LogFilterFlowRunId
from prefect.client.schemas.objects import Log
from prefect.events import Event
from prefect.events.clients import PrefectEventSubscriber, get_events_subscriber
from prefect.events.filters import EventAnyResourceFilter, EventFilter
from prefect.logging.clients import PrefectLogsSubscriber, get_logs_subscriber

TERMINAL_FLOW_RUN_EVENTS = {
    "prefect.flow-run.Completed",
    "prefect.flow-run.Failed",
    "prefect.flow-run.Crashed",
}


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
    _queue: "asyncio.Queue[Union[Log, Event, None]]"
    _tasks: list["asyncio.Task[None]"]
    _flow_completed: bool
    _straggler_timeout: int
    _reconnection_attempts: int
    _log_filter: LogFilter
    _event_filter: EventFilter
    _logs_subscriber: Union[PrefectLogsSubscriber, Any]
    _events_subscriber: Union[PrefectEventSubscriber, Any]
    _sentinels_received: int

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

    def __aiter__(self) -> Self:
        """Return self as an async iterator"""
        return self

    async def __anext__(self) -> Union[Log, Event]:
        """Get the next log or event from the interleaved stream"""
        while self._sentinels_received < len(self._tasks):
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
        """Background task to consume logs and put them in the queue"""
        try:
            async for log in self._logs_subscriber:
                await self._queue.put(log)
        except asyncio.CancelledError:
            pass
        except Exception:
            pass
        finally:
            await self._queue.put(None)

    async def _consume_events(self) -> None:
        """Background task to consume events and put them in the queue"""
        try:
            async for event in self._events_subscriber:
                await self._queue.put(event)

                if (
                    event.event in TERMINAL_FLOW_RUN_EVENTS
                    and event.resource.id == f"prefect.flow-run.{self._flow_run_id}"
                ):
                    self._flow_completed = True
                    break
        except Exception:
            pass
        finally:
            await self._queue.put(None)
