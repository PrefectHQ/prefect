from contextlib import asynccontextmanager
from contextvars import Context, copy_context
from typing import Any, Optional, Tuple, Type

from typing_extensions import Self

from prefect._internal.concurrency.services import QueueService
from prefect.settings import (
    PREFECT_API_KEY,
    PREFECT_API_URL,
    PREFECT_CLOUD_API_URL,
    PREFECT_EXPERIMENTAL_EVENTS,
)
from prefect.utilities.context import temporary_context

from .clients import (
    EventsClient,
    NullEventsClient,
    PrefectCloudEventsClient,
    PrefectEventsClient,
)
from .related import related_resources_from_run_context
from .schemas.events import Event


def should_emit_events() -> bool:
    return emit_events_to_cloud() or should_emit_events_to_running_server()


def emit_events_to_cloud() -> bool:
    api_url = PREFECT_API_URL.value()
    return isinstance(api_url, str) and api_url.startswith(
        PREFECT_CLOUD_API_URL.value()
    )


def should_emit_events_to_running_server() -> bool:
    api_url = PREFECT_API_URL.value()
    return isinstance(api_url, str) and PREFECT_EXPERIMENTAL_EVENTS


class EventsWorker(QueueService[Event]):
    def __init__(
        self, client_type: Type[EventsClient], client_options: Tuple[Tuple[str, Any]]
    ):
        super().__init__(client_type, client_options)
        self.client_type = client_type
        self.client_options = client_options
        self._client: EventsClient

    @asynccontextmanager
    async def _lifespan(self):
        self._client = self.client_type(**{k: v for k, v in self.client_options})

        async with self._client:
            yield

    def _prepare_item(self, event: Event) -> Tuple[Event, Context]:
        return (event, copy_context())

    async def _handle(self, event_and_context: Tuple[Event, Context]):
        event, context = event_and_context
        with temporary_context(context=context):
            await self.attach_related_resources_from_context(event)

        await self._client.emit(event)

    async def attach_related_resources_from_context(self, event: Event):
        exclude = {resource.id for resource in event.involved_resources}
        event.related += await related_resources_from_run_context(exclude=exclude)

    @classmethod
    def instance(
        cls: Type[Self], client_type: Optional[Type[EventsClient]] = None
    ) -> Self:
        client_kwargs = {}

        # Select a client type for this worker based on settings
        if client_type is None:
            if emit_events_to_cloud():
                client_type = PrefectCloudEventsClient
                client_kwargs = {
                    "api_url": PREFECT_API_URL.value(),
                    "api_key": PREFECT_API_KEY.value(),
                }
            elif should_emit_events_to_running_server():
                client_type = PrefectEventsClient

            else:
                client_type = NullEventsClient

        # The base class will take care of returning an existing worker with these
        # options if available
        return super().instance(client_type, tuple(client_kwargs.items()))
