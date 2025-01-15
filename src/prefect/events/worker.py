from contextlib import asynccontextmanager
from contextvars import Context, copy_context
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple, Type
from uuid import UUID

from typing_extensions import Self

from prefect._internal.concurrency.services import QueueService
from prefect.settings import (
    PREFECT_API_KEY,
    PREFECT_API_URL,
    PREFECT_CLOUD_API_URL,
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

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient


def should_emit_events() -> bool:
    return (
        emit_events_to_cloud()
        or should_emit_events_to_running_server()
        or should_emit_events_to_ephemeral_server()
    )


def emit_events_to_cloud() -> bool:
    api_url = PREFECT_API_URL.value()
    return isinstance(api_url, str) and api_url.startswith(
        PREFECT_CLOUD_API_URL.value()
    )


def should_emit_events_to_running_server() -> bool:
    api_url = PREFECT_API_URL.value()
    return isinstance(api_url, str)


def should_emit_events_to_ephemeral_server() -> bool:
    return PREFECT_API_KEY.value() is None


class EventsWorker(QueueService[Event]):
    def __init__(
        self, client_type: Type[EventsClient], client_options: Tuple[Tuple[str, Any]]
    ):
        super().__init__(client_type, client_options)
        self.client_type = client_type
        self.client_options = client_options
        self._client: EventsClient
        self._orchestration_client: "PrefectClient"
        self._context_cache: Dict[UUID, Context] = {}

    @asynccontextmanager
    async def _lifespan(self):
        self._client = self.client_type(**{k: v for k, v in self.client_options})
        from prefect.client.orchestration import get_client

        self._orchestration_client = get_client()
        async with self._client:
            async with self._orchestration_client:
                yield

    def _prepare_item(self, event: Event) -> Event:
        self._context_cache[event.id] = copy_context()
        return event

    async def _handle(self, event: Event):
        context = self._context_cache.pop(event.id)
        with temporary_context(context=context):
            await self.attach_related_resources_from_context(event)

        await self._client.emit(event)

    async def attach_related_resources_from_context(self, event: Event) -> None:
        if "prefect.resource.lineage-group" in event.resource:
            # We attach related resources to lineage events in `emit_lineage_event`,
            # instead of the worker, because not all run-related resources are
            # upstream from every lineage event (they might be downstream).
            # The "related" field in the event schema tracks upstream resources
            # only.
            return

        exclude = {resource.id for resource in event.involved_resources}
        event.related += await related_resources_from_run_context(
            client=self._orchestration_client, exclude=exclude
        )

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
            elif should_emit_events_to_ephemeral_server():
                # create an ephemeral API if none was provided
                from prefect.server.api.server import SubprocessASGIServer

                server = SubprocessASGIServer()
                server.start()
                assert server.server_process is not None, "Server process did not start"

                client_kwargs = {"api_url": server.api_url}
                client_type = PrefectEventsClient
            else:
                client_type = NullEventsClient

        # The base class will take care of returning an existing worker with these
        # options if available
        return super().instance(client_type, tuple(client_kwargs.items()))
