from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from prefect._internal.schemas.bases import ActionBaseModel
from prefect._internal.schemas.validators import (
    validate_block_document_name,
    validate_name_present_on_nonanonymous_blocks,
)
from prefect.types import (
    Name,
)


class BlockDocumentCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a block document."""

    name: Optional[Name] = Field(
        default=None, description="The name of the block document"
    )
    data: Dict[str, Any] = Field(
        default_factory=dict, description="The block document's data"
    )
    block_schema_id: UUID = Field(
        default=..., description="The block schema ID for the block document"
    )
    block_type_id: UUID = Field(
        default=..., description="The block type ID for the block document"
    )
    is_anonymous: bool = Field(
        default=False,
        description=(
            "Whether the block is anonymous (anonymous blocks are usually created by"
            " Prefect automatically)"
        ),
    )

    _validate_name_format = field_validator("name")(validate_block_document_name)

    @model_validator(mode="before")
    def validate_name_is_present_if_not_anonymous(cls, values):
        return validate_name_present_on_nonanonymous_blocks(values)