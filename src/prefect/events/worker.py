from contextlib import asynccontextmanager
from typing import Any, Optional, Tuple, Type

from typing_extensions import Self

from prefect._internal.compatibility.experimental import experiment_enabled
from prefect._internal.concurrency.services import QueueService
from prefect.settings import PREFECT_API_KEY, PREFECT_API_URL, PREFECT_CLOUD_API_URL

from .clients import EventsClient, NullEventsClient, PrefectCloudEventsClient
from .schemas import Event


class EventsWorker(QueueService[Event]):
    def __init__(
        self, client_type: Type[EventsClient], client_options: Tuple[Tuple[str, Any]]
    ):
        super().__init__(client_type, client_options)
        self._client_type = client_type
        self._client_options = client_options
        self._client: EventsClient

    @asynccontextmanager
    async def _lifespan(self):
        self._client = self._client_type(**{k: v for k, v in self._client_options})

        async with self._client:
            yield

    async def _handle(self, item: Event):
        await self._client.emit(item)

    @classmethod
    def instance(cls: Type[Self], client_type: Optional[EventsClient] = None) -> Self:
        client_kwargs = {}

        # Select a client type for this worker based on settings
        if client_type is None:
            api = PREFECT_API_URL.value()
            if (
                experiment_enabled("events_client")
                and api
                and api.startswith(PREFECT_CLOUD_API_URL.value())
            ):
                client_type = PrefectCloudEventsClient
                client_kwargs = {
                    "api_url": PREFECT_API_URL.value(),
                    "api_key": PREFECT_API_KEY.value(),
                }

            else:
                client_type = NullEventsClient

        # The base class will take care of returning an existing worker with these
        # options if available
        return super().instance(client_type, tuple(client_kwargs.items()))
