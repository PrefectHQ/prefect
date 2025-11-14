from typing import TYPE_CHECKING

from prefect.client.orchestration.base import BaseAsyncClient, BaseClient
from prefect.client.schemas.events import EventPage

if TYPE_CHECKING:
    from prefect.events.filters import EventFilter


class EventClient(BaseClient):
    def read_events(
        self,
        filter: "EventFilter | None" = None,
        limit: int = 100,
    ) -> EventPage:
        """
        query historical events from the API.

        args:
            filter: optional filter criteria to narrow down events
            limit: maximum number of events to return per page (default 100)

        returns:
            EventPage containing events, total count, and next page link
        """
        response = self.request(
            "POST",
            "/events/filter",
            json={
                "filter": filter.model_dump(mode="json") if filter else None,
                "limit": limit,
            },
        )
        return EventPage.model_validate(response.json())

    def read_events_page(self, next_page_url: str) -> EventPage:
        """
        retrieve the next page of events using a next_page URL.

        args:
            next_page_url: the next_page URL from a previous EventPage response

        returns:
            EventPage containing the next page of events
        """
        response = self._client.get(str(next_page_url))
        response.raise_for_status()
        return EventPage.model_validate(response.json())


class EventAsyncClient(BaseAsyncClient):
    async def read_events(
        self,
        filter: "EventFilter | None" = None,
        limit: int = 100,
    ) -> EventPage:
        """
        query historical events from the API.

        args:
            filter: optional filter criteria to narrow down events
            limit: maximum number of events to return per page (default 100)

        returns:
            EventPage containing events, total count, and next page link
        """
        response = await self.request(
            "POST",
            "/events/filter",
            json={
                "filter": filter.model_dump(mode="json") if filter else None,
                "limit": limit,
            },
        )
        return EventPage.model_validate(response.json())

    async def read_events_page(self, next_page_url: str) -> EventPage:
        """
        retrieve the next page of events using a next_page URL.

        args:
            next_page_url: the next_page URL from a previous EventPage response

        returns:
            EventPage containing the next page of events
        """
        response = await self._client.get(str(next_page_url))
        response.raise_for_status()
        return EventPage.model_validate(response.json())
