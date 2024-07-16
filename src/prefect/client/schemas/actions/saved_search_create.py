from typing import List

from pydantic import Field

from prefect._internal.schemas.bases import ActionBaseModel
from prefect.client.schemas.objects import SavedSearchFilter


class SavedSearchCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a saved search."""

    name: str = Field(default=..., description="The name of the saved search.")
    filters: List[SavedSearchFilter] = Field(
        default_factory=list, description="The filter set for the saved search."
    )
