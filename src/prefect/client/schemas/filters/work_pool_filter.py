from typing import Optional

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel

from .operator_mixin import OperatorMixin
from .work_pool_filter_id import WorkPoolFilterId
from .work_pool_filter_name import WorkPoolFilterName
from .work_pool_filter_type import WorkPoolFilterType


class WorkPoolFilter(PrefectBaseModel, OperatorMixin):
    id: Optional[WorkPoolFilterId] = Field(
        default=None, description="Filter criteria for `WorkPool.id`"
    )
    name: Optional[WorkPoolFilterName] = Field(
        default=None, description="Filter criteria for `WorkPool.name`"
    )
    type: Optional[WorkPoolFilterType] = Field(
        default=None, description="Filter criteria for `WorkPool.type`"
    )
