from typing import TYPE_CHECKING, Optional

from prefect.client.orchestration.base import BaseAsyncClient, BaseClient

if TYPE_CHECKING:
    from prefect.server.events.filters import EventFilter
    from prefect.server.events.schemas.events import EventPage


class EventClient(BaseClient):
    def read_events(
        self,
        filter: Optional["EventFilter"] = None,
        limit: int = 100,
    ) -> "EventPage":
        """
        query historical events from the API.

        args:
            filter: optional filter criteria to narrow down events
            limit: maximum number of events to return (default 100)

        returns:
            EventPage containing events, total count, and next page link
        """
        from prefect.server.events.schemas.events import EventPage

        response = self.request(
            "POST",
            "/events/filter",
            json={
                "filter": filter.model_dump(mode="json") if filter else None,
                "limit": limit,
            },
        )
        return EventPage.model_validate(response.json())


class EventAsyncClient(BaseAsyncClient):
    async def read_events(
        self,
        filter: Optional["EventFilter"] = None,
        limit: int = 100,
    ) -> "EventPage":
        """
        query historical events from the API.

        args:
            filter: optional filter criteria to narrow down events
            limit: maximum number of events to return (default 100)

        returns:
            EventPage containing events, total count, and next page link
        """
        from prefect.server.events.schemas.events import EventPage

        response = await self.request(
            "POST",
            "/events/filter",
            json={
                "filter": filter.model_dump(mode="json") if filter else None,
                "limit": limit,
            },
        )
        return EventPage.model_validate(response.json())
