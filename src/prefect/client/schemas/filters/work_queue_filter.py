from typing import Optional

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel

from .operator_mixin import OperatorMixin
from .work_queue_filter_id import WorkQueueFilterId
from .work_queue_filter_name import WorkQueueFilterName


class WorkQueueFilter(PrefectBaseModel, OperatorMixin):
    """Filter work queues. Only work queues matching all criteria will be
    returned"""

    id: Optional[WorkQueueFilterId] = Field(
        default=None, description="Filter criteria for `WorkQueue.id`"
    )

    name: Optional[WorkQueueFilterName] = Field(
        default=None, description="Filter criteria for `WorkQueue.name`"
    )
