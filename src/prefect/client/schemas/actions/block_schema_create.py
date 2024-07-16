from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import Field

from prefect._internal.schemas.bases import ActionBaseModel
from prefect.client.schemas.objects import DEFAULT_BLOCK_SCHEMA_VERSION


class BlockSchemaCreate(ActionBaseModel):
    """Data used by the Prefect REST API to create a block schema."""

    fields: Dict[str, Any] = Field(
        default_factory=dict, description="The block schema's field schema"
    )
    block_type_id: Optional[UUID] = Field(None)
    capabilities: List[str] = Field(
        default_factory=list,
        description="A list of Block capabilities",
    )
    version: str = Field(
        default=DEFAULT_BLOCK_SCHEMA_VERSION,
        description="Human readable identifier for the block schema",
    )
