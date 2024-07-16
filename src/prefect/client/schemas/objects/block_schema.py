from typing import (
    Any,
    Dict,
    List,
    Optional,
)
from uuid import UUID

from pydantic import (
    Field,
)

from prefect._internal.schemas.bases import ObjectBaseModel

from .block_type import BlockType

DEFAULT_BLOCK_SCHEMA_VERSION = "non-versioned"


class BlockSchema(ObjectBaseModel):
    """An ORM representation of a block schema."""

    checksum: str = Field(default=..., description="The block schema's unique checksum")
    fields: Dict[str, Any] = Field(
        default_factory=dict, description="The block schema's field schema"
    )
    block_type_id: Optional[UUID] = Field(default=..., description="A block type ID")
    block_type: Optional[BlockType] = Field(
        default=None, description="The associated block type"
    )
    capabilities: List[str] = Field(
        default_factory=list,
        description="A list of Block capabilities",
    )
    version: str = Field(
        default=DEFAULT_BLOCK_SCHEMA_VERSION,
        description="Human readable identifier for the block schema",
    )
