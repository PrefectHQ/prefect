from typing import List, Optional

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel


class ArtifactCollectionFilterKey(PrefectBaseModel):
    """Filter by `ArtifactCollection.key`."""

    any_: Optional[List[str]] = Field(
        default=None, description="A list of artifact keys to include"
    )

    like_: Optional[str] = Field(
        default=None,
        description=(
            "A string to match artifact keys against. This can include "
            "SQL wildcard characters like `%` and `_`."
        ),
        examples=["my-artifact-%"],
    )

    exists_: Optional[bool] = Field(
        default=None,
        description=(
            "If `true`, only include artifacts with a non-null key. If `false`, "
            "only include artifacts with a null key. Should return all rows in "
            "the ArtifactCollection table if specified."
        ),
    )
