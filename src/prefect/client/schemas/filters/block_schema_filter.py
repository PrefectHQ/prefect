from typing import Optional

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel

from .block_schema_filter_block_type_id import BlockSchemaFilterBlockTypeId
from .block_schema_filter_capabilities import BlockSchemaFilterCapabilities
from .block_schema_filter_id import BlockSchemaFilterId
from .block_schema_filter_version import BlockSchemaFilterVersion
from .operator_mixin import OperatorMixin


class BlockSchemaFilter(PrefectBaseModel, OperatorMixin):
    """Filter BlockSchemas"""

    block_type_id: Optional[BlockSchemaFilterBlockTypeId] = Field(
        default=None, description="Filter criteria for `BlockSchema.block_type_id`"
    )
    block_capabilities: Optional[BlockSchemaFilterCapabilities] = Field(
        default=None, description="Filter criteria for `BlockSchema.capabilities`"
    )
    id: Optional[BlockSchemaFilterId] = Field(
        default=None, description="Filter criteria for `BlockSchema.id`"
    )
    version: Optional[BlockSchemaFilterVersion] = Field(
        default=None, description="Filter criteria for `BlockSchema.version`"
    )