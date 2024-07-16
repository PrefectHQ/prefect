from uuid import UUID, uuid4

from pydantic import Field

from prefect._internal.schemas.bases import ActionBaseModel


class BlockDocumentReferenceCreate(ActionBaseModel):
    """Data used to create block document reference."""

    id: UUID = Field(default_factory=uuid4)
    parent_block_document_id: UUID = Field(
        default=..., description="ID of block document the reference is nested within"
    )
    reference_block_document_id: UUID = Field(
        default=..., description="ID of the nested block document"
    )
    name: str = Field(
        default=..., description="The name that the reference is nested under"
    )