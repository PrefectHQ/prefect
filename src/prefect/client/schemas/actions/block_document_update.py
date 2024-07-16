from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import Field

from prefect._internal.schemas.bases import ActionBaseModel


class BlockDocumentUpdate(ActionBaseModel):
    """Data used by the Prefect REST API to update a block document."""

    block_schema_id: Optional[UUID] = Field(
        default=None, description="A block schema ID"
    )
    data: Dict[str, Any] = Field(
        default_factory=dict, description="The block document's data"
    )
    merge_existing_data: bool = Field(
        default=True,
        description="Whether to merge the existing data with the new data or replace it",
    )