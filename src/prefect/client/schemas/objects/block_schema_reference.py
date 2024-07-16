from typing import (
    Optional,
)
from uuid import UUID

from pydantic import (
    Field,
)

from prefect._internal.schemas.bases import ObjectBaseModel

from .block_schema import BlockSchema


class BlockSchemaReference(ObjectBaseModel):
    """An ORM representation of a block schema reference."""

    parent_block_schema_id: UUID = Field(
        default=..., description="ID of block schema the reference is nested within"
    )
    parent_block_schema: Optional[BlockSchema] = Field(
        default=None, description="The block schema the reference is nested within"
    )
    reference_block_schema_id: UUID = Field(
        default=..., description="ID of the nested block schema"
    )
    reference_block_schema: Optional[BlockSchema] = Field(
        default=None, description="The nested block schema"
    )
    name: str = Field(
        default=..., description="The name that the reference is nested under"
    )
