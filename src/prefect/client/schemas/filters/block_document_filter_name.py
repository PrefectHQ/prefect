from typing import List, Optional

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel


class BlockDocumentFilterName(PrefectBaseModel):
    """Filter by `BlockDocument.name`."""

    any_: Optional[List[str]] = Field(
        default=None, description="A list of block names to include"
    )
    like_: Optional[str] = Field(
        default=None,
        description=(
            "A string to match block names against. This can include "
            "SQL wildcard characters like `%` and `_`."
        ),
        examples=["my-block%"],
    )