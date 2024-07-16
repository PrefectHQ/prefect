from typing import Optional

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel

from .deployment_filter_id import DeploymentFilterId
from .deployment_filter_is_schedule_active import DeploymentFilterIsScheduleActive
from .deployment_filter_name import DeploymentFilterName
from .deployment_filter_tags import DeploymentFilterTags
from .deployment_filter_work_queue_name import DeploymentFilterWorkQueueName
from .operator_mixin import OperatorMixin


class DeploymentFilter(PrefectBaseModel, OperatorMixin):
    """Filter for deployments. Only deployments matching all criteria will be returned."""

    id: Optional[DeploymentFilterId] = Field(
        default=None, description="Filter criteria for `Deployment.id`"
    )
    name: Optional[DeploymentFilterName] = Field(
        default=None, description="Filter criteria for `Deployment.name`"
    )
    is_schedule_active: Optional[DeploymentFilterIsScheduleActive] = Field(
        default=None, description="Filter criteria for `Deployment.is_schedule_active`"
    )
    tags: Optional[DeploymentFilterTags] = Field(
        default=None, description="Filter criteria for `Deployment.tags`"
    )
    work_queue_name: Optional[DeploymentFilterWorkQueueName] = Field(
        default=None, description="Filter criteria for `Deployment.work_queue_name`"
    )
