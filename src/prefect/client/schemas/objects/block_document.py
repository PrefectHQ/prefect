from functools import partial
from typing import (
    Any,
    Dict,
    Optional,
)
from uuid import UUID

from pydantic import (
    Field,
    SerializationInfo,
    field_validator,
    model_serializer,
    model_validator,
)

from prefect._internal.schemas.bases import ObjectBaseModel
from prefect._internal.schemas.validators import (
    validate_block_document_name,
    validate_name_present_on_nonanonymous_blocks,
)
from prefect.types import (
    Name,
)
from prefect.utilities.collections import visit_collection
from prefect.utilities.pydantic import handle_secret_render

from .block_schema import BlockSchema
from .block_type import BlockType


class BlockDocument(ObjectBaseModel):
    """An ORM representation of a block document."""

    name: Optional[Name] = Field(
        default=None,
        description=(
            "The block document's name. Not required for anonymous block documents."
        ),
    )
    data: Dict[str, Any] = Field(
        default_factory=dict, description="The block document's data"
    )
    block_schema_id: UUID = Field(default=..., description="A block schema ID")
    block_schema: Optional[BlockSchema] = Field(
        default=None, description="The associated block schema"
    )
    block_type_id: UUID = Field(default=..., description="A block type ID")
    block_type_name: Optional[str] = Field(None, description="A block type name")
    block_type: Optional[BlockType] = Field(
        default=None, description="The associated block type"
    )
    block_document_references: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="Record of the block document's references"
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
    @classmethod
    def validate_name_is_present_if_not_anonymous(cls, values):
        return validate_name_present_on_nonanonymous_blocks(values)

    @model_serializer(mode="wrap")
    def serialize_data(self, handler, info: SerializationInfo):
        self.data = visit_collection(
            self.data,
            visit_fn=partial(handle_secret_render, context=info.context or {}),
            return_data=True,
        )
        return handler(self)
