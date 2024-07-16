from typing import List, Optional

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel


class BlockTypeFilterSlug(PrefectBaseModel):
    """Filter by `BlockType.slug`"""

    any_: Optional[List[str]] = Field(
        default=None, description="A list of slugs to match"
    )
