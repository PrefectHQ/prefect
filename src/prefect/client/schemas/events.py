from typing import TYPE_CHECKING

from pydantic import AnyHttpUrl, Field

from prefect._internal.schemas.bases import PrefectBaseModel
from prefect.events.schemas.events import ReceivedEvent

if TYPE_CHECKING:
    from prefect.client.orchestration import PrefectClient, SyncPrefectClient


class EventPage(PrefectBaseModel):
    """a single page of events returned from the API"""

    events: list[ReceivedEvent] = Field(description="the events matching the query")
    total: int = Field(description="the total number of matching events")
    next_page: AnyHttpUrl | None = Field(
        description="the URL for the next page of results, if there are more"
    )

    async def get_next_page(self, client: "PrefectClient") -> "EventPage | None":
        """
        fetch the next page of events.

        args:
            client: the PrefectClient instance to use for fetching

        returns:
            the next EventPage, or None if there are no more pages
        """
        if not self.next_page:
            return None
        return await client.read_events_page(self.next_page)

    def get_next_page_sync(self, client: "SyncPrefectClient") -> "EventPage | None":
        """
        fetch the next page of events (sync version).

        args:
            client: the SyncPrefectClient instance to use for fetching

        returns:
            the next EventPage, or None if there are no more pages
        """
        if not self.next_page:
            return None
        return client.read_events_page(self.next_page)
