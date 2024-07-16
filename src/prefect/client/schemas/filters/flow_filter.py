from typing import Optional

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel

from .flow_filter_id import FlowFilterId
from .flow_filter_name import FlowFilterName
from .flow_filter_tags import FlowFilterTags
from .operator_mixin import OperatorMixin


class FlowFilter(PrefectBaseModel, OperatorMixin):
    """Filter for flows. Only flows matching all criteria will be returned."""

    id: Optional[FlowFilterId] = Field(
        default=None, description="Filter criteria for `Flow.id`"
    )
    name: Optional[FlowFilterName] = Field(
        default=None, description="Filter criteria for `Flow.name`"
    )
    tags: Optional[FlowFilterTags] = Field(
        default=None, description="Filter criteria for `Flow.tags`"
    )