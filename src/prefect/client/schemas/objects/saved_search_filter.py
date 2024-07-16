from typing import (
    Any,
)

from pydantic import (
    Field,
)

from prefect._internal.schemas.bases import PrefectBaseModel


class SavedSearchFilter(PrefectBaseModel):
    """A filter for a saved search model. Intended for use by the Prefect UI."""

    object: str = Field(default=..., description="The object over which to filter.")
    property: str = Field(
        default=..., description="The property of the object on which to filter."
    )
    type: str = Field(default=..., description="The type of the property.")
    operation: str = Field(
        default=...,
        description="The operator to apply to the object. For example, `equals`.",
    )
    value: Any = Field(
        default=..., description="A JSON-compatible value for the filter."
    )