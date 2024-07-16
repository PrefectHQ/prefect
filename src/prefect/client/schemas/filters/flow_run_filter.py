from typing import Optional

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel

from .flow_run_filter_deployment_id import FlowRunFilterDeploymentId
from .flow_run_filter_expected_start_time import FlowRunFilterExpectedStartTime
from .flow_run_filter_flow_version import FlowRunFilterFlowVersion
from .flow_run_filter_id import FlowRunFilterId
from .flow_run_filter_idempotency_key import FlowRunFilterIdempotencyKey
from .flow_run_filter_name import FlowRunFilterName
from .flow_run_filter_next_scheduled_start_time import (
    FlowRunFilterNextScheduledStartTime,
)
from .flow_run_filter_parent_flow_run_id import FlowRunFilterParentFlowRunId
from .flow_run_filter_parent_task_run_id import FlowRunFilterParentTaskRunId
from .flow_run_filter_start_time import FlowRunFilterStartTime
from .flow_run_filter_state import FlowRunFilterState
from .flow_run_filter_tags import FlowRunFilterTags
from .flow_run_filter_work_queue_name import FlowRunFilterWorkQueueName
from .operator_mixin import OperatorMixin


class FlowRunFilter(PrefectBaseModel, OperatorMixin):
    """Filter flow runs. Only flow runs matching all criteria will be returned"""

    id: Optional[FlowRunFilterId] = Field(
        default=None, description="Filter criteria for `FlowRun.id`"
    )
    name: Optional[FlowRunFilterName] = Field(
        default=None, description="Filter criteria for `FlowRun.name`"
    )
    tags: Optional[FlowRunFilterTags] = Field(
        default=None, description="Filter criteria for `FlowRun.tags`"
    )
    deployment_id: Optional[FlowRunFilterDeploymentId] = Field(
        default=None, description="Filter criteria for `FlowRun.deployment_id`"
    )
    work_queue_name: Optional[FlowRunFilterWorkQueueName] = Field(
        default=None, description="Filter criteria for `FlowRun.work_queue_name"
    )
    state: Optional[FlowRunFilterState] = Field(
        default=None, description="Filter criteria for `FlowRun.state`"
    )
    flow_version: Optional[FlowRunFilterFlowVersion] = Field(
        default=None, description="Filter criteria for `FlowRun.flow_version`"
    )
    start_time: Optional[FlowRunFilterStartTime] = Field(
        default=None, description="Filter criteria for `FlowRun.start_time`"
    )
    expected_start_time: Optional[FlowRunFilterExpectedStartTime] = Field(
        default=None, description="Filter criteria for `FlowRun.expected_start_time`"
    )
    next_scheduled_start_time: Optional[FlowRunFilterNextScheduledStartTime] = Field(
        default=None,
        description="Filter criteria for `FlowRun.next_scheduled_start_time`",
    )
    parent_flow_run_id: Optional[FlowRunFilterParentFlowRunId] = Field(
        default=None, description="Filter criteria for subflows of the given flow runs"
    )
    parent_task_run_id: Optional[FlowRunFilterParentTaskRunId] = Field(
        default=None, description="Filter criteria for `FlowRun.parent_task_run_id`"
    )
    idempotency_key: Optional[FlowRunFilterIdempotencyKey] = Field(
        default=None, description="Filter criteria for `FlowRun.idempotency_key`"
    )