from typing import Optional

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel

from .block_type_filter_name import BlockTypeFilterName
from .block_type_filter_slug import BlockTypeFilterSlug


class BlockTypeFilter(PrefectBaseModel):
    """Filter BlockTypes"""

    name: Optional[BlockTypeFilterName] = Field(
        default=None, description="Filter criteria for `BlockType.name`"
    )

    slug: Optional[BlockTypeFilterSlug] = Field(
        default=None, description="Filter criteria for `BlockType.slug`"
    )
