from pydantic import AnyHttpUrl, Field

from prefect._internal.schemas.bases import PrefectBaseModel
from prefect.events.schemas.events import ReceivedEvent


class EventPage(PrefectBaseModel):
    """a single page of events returned from the API"""

    events: list[ReceivedEvent] = Field(description="the events matching the query")
    total: int = Field(description="the total number of matching events")
    next_page: AnyHttpUrl | None = Field(
        description="the URL for the next page of results, if there are more"
    )
