from typing import (
    Optional,
)

from pydantic import (
    Field,
    HttpUrl,
)

from prefect._internal.schemas.bases import ObjectBaseModel
from prefect.types import (
    Name,
)


class BlockType(ObjectBaseModel):
    """An ORM representation of a block type"""

    name: Name = Field(default=..., description="A block type's name")
    slug: str = Field(default=..., description="A block type's slug")
    logo_url: Optional[HttpUrl] = Field(
        default=None, description="Web URL for the block type's logo"
    )
    documentation_url: Optional[HttpUrl] = Field(
        default=None, description="Web URL for the block type's documentation"
    )
    description: Optional[str] = Field(
        default=None,
        description="A short blurb about the corresponding block's intended use",
    )
    code_example: Optional[str] = Field(
        default=None,
        description="A code snippet demonstrating use of the corresponding block",
    )
    is_protected: bool = Field(
        default=False, description="Protected block types cannot be modified via API."
    )
