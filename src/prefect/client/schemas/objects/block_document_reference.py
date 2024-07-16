from typing import (
    Optional,
)
from uuid import UUID

from pydantic import (
    Field,
    model_validator,
)

from prefect._internal.schemas.bases import ObjectBaseModel
from prefect._internal.schemas.validators import (
    validate_parent_and_ref_diff,
)

from .block_document import BlockDocument


class BlockDocumentReference(ObjectBaseModel):
    """An ORM representation of a block document reference."""

    parent_block_document_id: UUID = Field(
        default=..., description="ID of block document the reference is nested within"
    )
    parent_block_document: Optional[BlockDocument] = Field(
        default=None, description="The block document the reference is nested within"
    )
    reference_block_document_id: UUID = Field(
        default=..., description="ID of the nested block document"
    )
    reference_block_document: Optional[BlockDocument] = Field(
        default=None, description="The nested block document"
    )
    name: str = Field(
        default=..., description="The name that the reference is nested under"
    )

    @model_validator(mode="before")
    @classmethod
    def validate_parent_and_ref_are_different(cls, values):
        if isinstance(values, dict):
            return validate_parent_and_ref_diff(values)
        return values