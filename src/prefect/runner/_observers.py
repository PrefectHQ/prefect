import asyncio
import uuid
from contextlib import AsyncExitStack
from typing import Any, Protocol

from prefect.events.clients import PrefectEventSubscriber, get_events_subscriber
from prefect.events.filters import EventFilter, EventNameFilter
from prefect.logging.loggers import get_logger


class OnCancellingCallback(Protocol):
    def __call__(self, flow_run_id: uuid.UUID) -> None: ...


class FlowRunCancellingObserver:
    def __init__(self, on_cancelling: OnCancellingCallback):
        self.logger = get_logger("FlowRunCancellingObserver")
        self.on_cancelling = on_cancelling
        self._events_subscriber: PrefectEventSubscriber | None
        self._exit_stack = AsyncExitStack()

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
                self.logger.debug(
                    "Received event with invalid flow run ID: %s",
                    event.resource["prefect.resource.id"],
                )

    async def __aenter__(self):
        self._events_subscriber = await self._exit_stack.enter_async_context(
            get_events_subscriber(
                filter=EventFilter(
                    event=EventNameFilter(name=["prefect.flow-run.Cancelling"])
                )
            )
        )
        self._consumer_task = asyncio.create_task(self._consume_events())
        return self

    async def __aexit__(self, *exc_info: Any):
        await self._exit_stack.__aexit__(*exc_info)
        self._consumer_task.cancel()
        try:
            await self._consumer_task
        except asyncio.CancelledError:
            pass
        except Exception:
            self.logger.exception("Error consuming events")
