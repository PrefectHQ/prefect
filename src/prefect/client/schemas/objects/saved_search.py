from typing import (
    List,
)

from pydantic import (
    Field,
)

from prefect._internal.schemas.bases import ObjectBaseModel

from .saved_search_filter import SavedSearchFilter


class SavedSearch(ObjectBaseModel):
    """An ORM representation of saved search data. Represents a set of filter criteria."""

    name: str = Field(default=..., description="The name of the saved search.")
    filters: List[SavedSearchFilter] = Field(
        default_factory=list, description="The filter set for the saved search."
    )
