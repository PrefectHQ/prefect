"""
Schemas that define Prefect REST API filtering operations.
"""

from typing import List, Optional
from uuid import UUID

from pydantic import Field

from prefect._internal.schemas.bases import PrefectBaseModel
from prefect.client.schemas.objects import StateType
from prefect.types import DateTime
from prefect.utilities.collections import AutoEnum


class Operator(AutoEnum):
    """Operators for combining filter criteria."""

    and_ = AutoEnum.auto()
    or_ = AutoEnum.auto()


class OperatorMixin:
    """Base model for Prefect filters that combines criteria with a user-provided operator"""

    operator: Operator = Field(
        default=Operator.and_,
        description="Operator for combining filter criteria. Defaults to 'and_'.",
    )


class FlowFilterId(PrefectBaseModel):
    """Filter by `Flow.id`."""

    any_: Optional[List[UUID]] = Field(
        default=None, description="A list of flow ids to include"
    )


class FlowFilterName(PrefectBaseModel):
    """Filter by `Flow.name`."""

    any_: Optional[List[str]] = Field(
        default=None,
        description="A list of flow names to include",
        examples=[["my-flow-1", "my-flow-2"]],
    )

    like_: Optional[str] = Field(
        default=None,
        description=(
            "A case-insensitive partial match. For example, "
            " passing 'marvin' will match "
            "'marvin', 'sad-Marvin', and 'marvin-robot'."
        ),
        examples=["marvin"],
    )


class FlowFilterTags(PrefectBaseModel, OperatorMixin):
    """Filter by `Flow.tags`."""

    all_: Optional[List[str]] = Field(
        default=None,
        examples=[["tag-1", "tag-2"]],
        description=(
            "A list of tags. Flows will be returned only if their tags are a superset"
            " of the list"
        ),
    )
    is_null_: Optional[bool] = Field(
        default=None, description="If true, only include flows without tags"
    )


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


class FlowRunFilterId(PrefectBaseModel):
    """Filter by FlowRun.id."""

    any_: Optional[List[UUID]] = Field(
        default=None, description="A list of flow run ids to include"
    )
    not_any_: Optional[List[UUID]] = Field(
        default=None, description="A list of flow run ids to exclude"
    )


class FlowRunFilterName(PrefectBaseModel):
    """Filter by `FlowRun.name`."""

    any_: Optional[List[str]] = Field(
        default=None,
        description="A list of flow run names to include",
        examples=[["my-flow-run-1", "my-flow-run-2"]],
    )

    like_: Optional[str] = Field(
        default=None,
        description=(
            "A case-insensitive partial match. For example, "
            " passing 'marvin' will match "
            "'marvin', 'sad-Marvin', and 'marvin-robot'."
        ),
        examples=["marvin"],
    )


class FlowRunFilterTags(PrefectBaseModel, OperatorMixin):
    """Filter by `FlowRun.tags`."""

    all_: Optional[List[str]] = Field(
        default=None,
        examples=[["tag-1", "tag-2"]],
        description=(
            "A list of tags. Flow runs will be returned only if their tags are a"
            " superset of the list"
        ),
    )
    any_: Optional[List[str]] = Field(
        default=None,
        examples=[["tag-1", "tag-2"]],
        description="A list of tags to include",
    )
    is_null_: Optional[bool] = Field(
        default=None, description="If true, only include flow runs without tags"
    )


class FlowRunFilterDeploymentId(PrefectBaseModel, OperatorMixin):
    """Filter by `FlowRun.deployment_id`."""

    any_: Optional[List[UUID]] = Field(
        default=None, description="A list of flow run deployment ids to include"
    )
    is_null_: Optional[bool] = Field(
        default=None,
        description="If true, only include flow runs without deployment ids",
    )


class FlowRunFilterWorkQueueName(PrefectBaseModel, OperatorMixin):
    """Filter by `FlowRun.work_queue_name`."""

    any_: Optional[List[str]] = Field(
        default=None,
        description="A list of work queue names to include",
        examples=[["work_queue_1", "work_queue_2"]],
    )
    is_null_: Optional[bool] = Field(
        default=None,
        description="If true, only include flow runs without work queue names",
    )


class FlowRunFilterStateType(PrefectBaseModel):
    """Filter by `FlowRun.state_type`."""

    any_: Optional[List[StateType]] = Field(
        default=None, description="A list of flow run state types to include"
    )
    not_any_: Optional[List[StateType]] = Field(
        default=None, description="A list of flow run state types to exclude"
    )


class FlowRunFilterStateName(PrefectBaseModel):
    any_: Optional[List[str]] = Field(
        default=None, description="A list of flow run state names to include"
    )
    not_any_: Optional[List[str]] = Field(
        default=None, description="A list of flow run state names to exclude"
    )


class FlowRunFilterState(PrefectBaseModel, OperatorMixin):
    type: Optional[FlowRunFilterStateType] = Field(
        default=None, description="Filter criteria for `FlowRun` state type"
    )
    name: Optional[FlowRunFilterStateName] = Field(
        default=None, description="Filter criteria for `FlowRun` state name"
    )


class FlowRunFilterFlowVersion(PrefectBaseModel):
    """Filter by `FlowRun.flow_version`."""

    any_: Optional[List[str]] = Field(
        default=None, description="A list of flow run flow_versions to include"
    )


class FlowRunFilterStartTime(PrefectBaseModel):
    """Filter by `FlowRun.start_time`."""

    before_: Optional[DateTime] = Field(
        default=None,
        description="Only include flow runs starting at or before this time",
    )
    after_: Optional[DateTime] = Field(
        default=None,
        description="Only include flow runs starting at or after this time",
    )
    is_null_: Optional[bool] = Field(
        default=None, description="If true, only return flow runs without a start time"
    )


class FlowRunFilterExpectedStartTime(PrefectBaseModel):
    """Filter by `FlowRun.expected_start_time`."""

    before_: Optional[DateTime] = Field(
        default=None,
        description="Only include flow runs scheduled to start at or before this time",
    )
    after_: Optional[DateTime] = Field(
        default=None,
        description="Only include flow runs scheduled to start at or after this time",
    )


class FlowRunFilterNextScheduledStartTime(PrefectBaseModel):
    """Filter by `FlowRun.next_scheduled_start_time`."""

    before_: Optional[DateTime] = Field(
        default=None,
        description=(
            "Only include flow runs with a next_scheduled_start_time or before this"
            " time"
        ),
    )
    after_: Optional[DateTime] = Field(
        default=None,
        description=(
            "Only include flow runs with a next_scheduled_start_time at or after this"
            " time"
        ),
    )


class FlowRunFilterParentFlowRunId(PrefectBaseModel, OperatorMixin):
    """Filter for subflows of the given flow runs"""

    any_: Optional[List[UUID]] = Field(
        default=None, description="A list of flow run parents to include"
    )


class FlowRunFilterParentTaskRunId(PrefectBaseModel, OperatorMixin):
    """Filter by `FlowRun.parent_task_run_id`."""

    any_: Optional[List[UUID]] = Field(
        default=None, description="A list of flow run parent_task_run_ids to include"
    )
    is_null_: Optional[bool] = Field(
        default=None,
        description="If true, only include flow runs without parent_task_run_id",
    )


class FlowRunFilterIdempotencyKey(PrefectBaseModel):
    """Filter by FlowRun.idempotency_key."""

    any_: Optional[List[str]] = Field(
        default=None, description="A list of flow run idempotency keys to include"
    )
    not_any_: Optional[List[str]] = Field(
        default=None, description="A list of flow run idempotency keys to exclude"
    )


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


class TaskRunFilterFlowRunId(PrefectBaseModel):
    """Filter by `TaskRun.flow_run_id`."""

    any_: Optional[List[UUID]] = Field(
        default=None, description="A list of flow run ids to include"
    )

    is_null_: bool = Field(
        default=False,
        description="If true, only include task runs without a flow run id",
    )


class TaskRunFilterId(PrefectBaseModel):
    """Filter by `TaskRun.id`."""

    any_: Optional[List[UUID]] = Field(
        default=None, description="A list of task run ids to include"
    )


class TaskRunFilterName(PrefectBaseModel):
    """Filter by `TaskRun.name`."""

    any_: Optional[List[str]] = Field(
        default=None,
        description="A list of task run names to include",
        examples=[["my-task-run-1", "my-task-run-2"]],
    )

    like_: Optional[str] = Field(
        default=None,
        description=(
            "A case-insensitive partial match. For example, "
            " passing 'marvin' will match "
            "'marvin', 'sad-Marvin', and 'marvin-robot'."
        ),
        examples=["marvin"],
    )


class TaskRunFilterTags(PrefectBaseModel, OperatorMixin):
    """Filter by `TaskRun.tags`."""

    all_: Optional[List[str]] = Field(
        default=None,
        examples=[["tag-1", "tag-2"]],
        description=(
            "A list of tags. Task runs will be returned only if their tags are a"
            " superset of the list"
        ),
    )
    is_null_: Optional[bool] = Field(
        default=None, description="If true, only include task runs without tags"
    )


class TaskRunFilterStateType(PrefectBaseModel):
    """Filter by `TaskRun.state_type`."""

    any_: Optional[List[StateType]] = Field(
        default=None, description="A list of task run state types to include"
    )


class TaskRunFilterStateName(PrefectBaseModel):
    any_: Optional[List[str]] = Field(
        default=None, description="A list of task run state names to include"
    )


class TaskRunFilterState(PrefectBaseModel, OperatorMixin):
    type: Optional[TaskRunFilterStateType]
    name: Optional[TaskRunFilterStateName]


class TaskRunFilterSubFlowRuns(PrefectBaseModel):
    """Filter by `TaskRun.subflow_run`."""

    exists_: Optional[bool] = Field(
        default=None,
        description=(
            "If true, only include task runs that are subflow run parents; if false,"
            " exclude parent task runs"
        ),
    )


class TaskRunFilterStartTime(PrefectBaseModel):
    """Filter by `TaskRun.start_time`."""

    before_: Optional[DateTime] = Field(
        default=None,
        description="Only include task runs starting at or before this time",
    )
    after_: Optional[DateTime] = Field(
        default=None,
        description="Only include task runs starting at or after this time",
    )
    is_null_: Optional[bool] = Field(
        default=None, description="If true, only return task runs without a start time"
    )


class TaskRunFilter(PrefectBaseModel, OperatorMixin):
    """Filter task runs. Only task runs matching all criteria will be returned"""

    id: Optional[TaskRunFilterId] = Field(
        default=None, description="Filter criteria for `TaskRun.id`"
    )
    name: Optional[TaskRunFilterName] = Field(
        default=None, description="Filter criteria for `TaskRun.name`"
    )
    tags: Optional[TaskRunFilterTags] = Field(
        default=None, description="Filter criteria for `TaskRun.tags`"
    )
    state: Optional[TaskRunFilterState] = Field(
        default=None, description="Filter criteria for `TaskRun.state`"
    )
    start_time: Optional[TaskRunFilterStartTime] = Field(
        default=None, description="Filter criteria for `TaskRun.start_time`"
    )
    subflow_runs: Optional[TaskRunFilterSubFlowRuns] = Field(
        default=None, description="Filter criteria for `TaskRun.subflow_run`"
    )
    flow_run_id: Optional[TaskRunFilterFlowRunId] = Field(
        default=None, description="Filter criteria for `TaskRun.flow_run_id`"
    )


class DeploymentFilterId(PrefectBaseModel):
    """Filter by `Deployment.id`."""

    any_: Optional[List[UUID]] = Field(
        default=None, description="A list of deployment ids to include"
    )


class DeploymentFilterName(PrefectBaseModel):
    """Filter by `Deployment.name`."""

    any_: Optional[List[str]] = Field(
        default=None,
        description="A list of deployment names to include",
        examples=[["my-deployment-1", "my-deployment-2"]],
    )

    like_: Optional[str] = Field(
        default=None,
        description=(
            "A case-insensitive partial match. For example, "
            " passing 'marvin' will match "
            "'marvin', 'sad-Marvin', and 'marvin-robot'."
        ),
        examples=["marvin"],
    )


class DeploymentFilterWorkQueueName(PrefectBaseModel):
    """Filter by `Deployment.work_queue_name`."""

    any_: Optional[List[str]] = Field(
        default=None,
        description="A list of work queue names to include",
        examples=[["work_queue_1", "work_queue_2"]],
    )


class DeploymentFilterTags(PrefectBaseModel, OperatorMixin):
    """Filter by `Deployment.tags`."""

    all_: Optional[List[str]] = Field(
        default=None,
        examples=[["tag-1", "tag-2"]],
        description=(
            "A list of tags. Deployments will be returned only if their tags are a"
            " superset of the list"
        ),
    )
    any_: Optional[list[str]] = Field(
        default=None,
        examples=[["tag-1", "tag-2"]],
        description="A list of tags to include",
    )
    is_null_: Optional[bool] = Field(
        default=None, description="If true, only include deployments without tags"
    )


class DeploymentFilterConcurrencyLimit(PrefectBaseModel):
    """DEPRECATED: Prefer `Deployment.concurrency_limit_id` over `Deployment.concurrency_limit`."""

    ge_: Optional[int] = Field(
        default=None,
        description="Only include deployments with a concurrency limit greater than or equal to this value",
    )
    le_: Optional[int] = Field(
        default=None,
        description="Only include deployments with a concurrency limit less than or equal to this value",
    )
    is_null_: Optional[bool] = Field(
        default=None,
        description="If true, only include deployments without a concurrency limit",
    )


class DeploymentFilter(PrefectBaseModel, OperatorMixin):
    """Filter for deployments. Only deployments matching all criteria will be returned."""

    id: Optional[DeploymentFilterId] = Field(
        default=None, description="Filter criteria for `Deployment.id`"
    )
    name: Optional[DeploymentFilterName] = Field(
        default=None, description="Filter criteria for `Deployment.name`"
    )
    tags: Optional[DeploymentFilterTags] = Field(
        default=None, description="Filter criteria for `Deployment.tags`"
    )
    work_queue_name: Optional[DeploymentFilterWorkQueueName] = Field(
        default=None, description="Filter criteria for `Deployment.work_queue_name`"
    )
    concurrency_limit: Optional[DeploymentFilterConcurrencyLimit] = Field(
        default=None,
        description="DEPRECATED: Prefer `Deployment.concurrency_limit_id` over `Deployment.concurrency_limit`. If provided, will be ignored for backwards-compatibility. Will be removed after December 2024.",
        deprecated=True,
    )


class LogFilterName(PrefectBaseModel):
    """Filter by `Log.name`."""

    any_: Optional[List[str]] = Field(
        default=None,
        description="A list of log names to include",
        examples=[["prefect.logger.flow_runs", "prefect.logger.task_runs"]],
    )


class LogFilterLevel(PrefectBaseModel):
    """Filter by `Log.level`."""

    ge_: Optional[int] = Field(
        default=None,
        description="Include logs with a level greater than or equal to this level",
        examples=[20],
    )

    le_: Optional[int] = Field(
        default=None,
        description="Include logs with a level less than or equal to this level",
        examples=[50],
    )


class LogFilterTimestamp(PrefectBaseModel):
    """Filter by `Log.timestamp`."""

    before_: Optional[DateTime] = Field(
        default=None,
        description="Only include logs with a timestamp at or before this time",
    )
    after_: Optional[DateTime] = Field(
        default=None,
        description="Only include logs with a timestamp at or after this time",
    )


class LogFilterFlowRunId(PrefectBaseModel):
    """Filter by `Log.flow_run_id`."""

    any_: Optional[List[UUID]] = Field(
        default=None, description="A list of flow run IDs to include"
    )


class LogFilterTaskRunId(PrefectBaseModel):
    """Filter by `Log.task_run_id`."""

    any_: Optional[List[UUID]] = Field(
        default=None, description="A list of task run IDs to include"
    )


class LogFilter(PrefectBaseModel, OperatorMixin):
    """Filter logs. Only logs matching all criteria will be returned"""

    level: Optional[LogFilterLevel] = Field(
        default=None, description="Filter criteria for `Log.level`"
    )
    timestamp: Optional[LogFilterTimestamp] = Field(
        default=None, description="Filter criteria for `Log.timestamp`"
    )
    flow_run_id: Optional[LogFilterFlowRunId] = Field(
        default=None, description="Filter criteria for `Log.flow_run_id`"
    )
    task_run_id: Optional[LogFilterTaskRunId] = Field(
        default=None, description="Filter criteria for `Log.task_run_id`"
    )


class FilterSet(PrefectBaseModel):
    """A collection of filters for common objects"""

    flows: FlowFilter = Field(
        default_factory=FlowFilter, description="Filters that apply to flows"
    )
    flow_runs: FlowRunFilter = Field(
        default_factory=FlowRunFilter, description="Filters that apply to flow runs"
    )
    task_runs: TaskRunFilter = Field(
        default_factory=TaskRunFilter, description="Filters that apply to task runs"
    )
    deployments: DeploymentFilter = Field(
        default_factory=DeploymentFilter,
        description="Filters that apply to deployments",
    )


class BlockTypeFilterName(PrefectBaseModel):
    """Filter by `BlockType.name`"""

    like_: Optional[str] = Field(
        default=None,
        description=(
            "A case-insensitive partial match. For example, "
            " passing 'marvin' will match "
            "'marvin', 'sad-Marvin', and 'marvin-robot'."
        ),
        examples=["marvin"],
    )


class BlockTypeFilterSlug(PrefectBaseModel):
    """Filter by `BlockType.slug`"""

    any_: Optional[List[str]] = Field(
        default=None, description="A list of slugs to match"
    )


class BlockTypeFilter(PrefectBaseModel):
    """Filter BlockTypes"""

    name: Optional[BlockTypeFilterName] = Field(
        default=None, description="Filter criteria for `BlockType.name`"
    )

    slug: Optional[BlockTypeFilterSlug] = Field(
        default=None, description="Filter criteria for `BlockType.slug`"
    )


class BlockSchemaFilterBlockTypeId(PrefectBaseModel):
    """Filter by `BlockSchema.block_type_id`."""

    any_: Optional[List[UUID]] = Field(
        default=None, description="A list of block type ids to include"
    )


class BlockSchemaFilterId(PrefectBaseModel):
    """Filter by BlockSchema.id"""

    any_: Optional[List[UUID]] = Field(
        default=None, description="A list of IDs to include"
    )


class BlockSchemaFilterCapabilities(PrefectBaseModel):
    """Filter by `BlockSchema.capabilities`"""

    all_: Optional[List[str]] = Field(
        default=None,
        examples=[["write-storage", "read-storage"]],
        description=(
            "A list of block capabilities. Block entities will be returned only if an"
            " associated block schema has a superset of the defined capabilities."
        ),
    )


class BlockSchemaFilterVersion(PrefectBaseModel):
    """Filter by `BlockSchema.capabilities`"""

    any_: Optional[List[str]] = Field(
        default=None,
        examples=[["2.0.0", "2.1.0"]],
        description="A list of block schema versions.",
    )


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


class BlockDocumentFilterIsAnonymous(PrefectBaseModel):
    """Filter by `BlockDocument.is_anonymous`."""

    eq_: Optional[bool] = Field(
        default=None,
        description=(
            "Filter block documents for only those that are or are not anonymous."
        ),
    )


class BlockDocumentFilterBlockTypeId(PrefectBaseModel):
    """Filter by `BlockDocument.block_type_id`."""

    any_: Optional[List[UUID]] = Field(
        default=None, description="A list of block type ids to include"
    )


class BlockDocumentFilterId(PrefectBaseModel):
    """Filter by `BlockDocument.id`."""

    any_: Optional[List[UUID]] = Field(
        default=None, description="A list of block ids to include"
    )


class BlockDocumentFilterName(PrefectBaseModel):
    """Filter by `BlockDocument.name`."""

    any_: Optional[List[str]] = Field(
        default=None, description="A list of block names to include"
    )
    like_: Optional[str] = Field(
        default=None,
        description=(
            "A string to match block names against. This can include "
            "SQL wildcard characters like `%` and `_`."
        ),
        examples=["my-block%"],
    )


class BlockDocumentFilter(PrefectBaseModel, OperatorMixin):
    """Filter BlockDocuments. Only BlockDocuments matching all criteria will be returned"""

    id: Optional[BlockDocumentFilterId] = Field(
        default=None, description="Filter criteria for `BlockDocument.id`"
    )
    is_anonymous: Optional[BlockDocumentFilterIsAnonymous] = Field(
        # default is to exclude anonymous blocks
        BlockDocumentFilterIsAnonymous(eq_=False),
        description=(
            "Filter criteria for `BlockDocument.is_anonymous`. "
            "Defaults to excluding anonymous blocks."
        ),
    )
    block_type_id: Optional[BlockDocumentFilterBlockTypeId] = Field(
        default=None, description="Filter criteria for `BlockDocument.block_type_id`"
    )
    name: Optional[BlockDocumentFilterName] = Field(
        default=None, description="Filter criteria for `BlockDocument.name`"
    )


class FlowRunNotificationPolicyFilterIsActive(PrefectBaseModel):
    """Filter by `FlowRunNotificationPolicy.is_active`."""

    eq_: Optional[bool] = Field(
        default=None,
        description=(
            "Filter notification policies for only those that are or are not active."
        ),
    )


class FlowRunNotificationPolicyFilter(PrefectBaseModel):
    """Filter FlowRunNotificationPolicies."""

    is_active: Optional[FlowRunNotificationPolicyFilterIsActive] = Field(
        default=FlowRunNotificationPolicyFilterIsActive(eq_=False),
        description="Filter criteria for `FlowRunNotificationPolicy.is_active`. ",
    )


class WorkQueueFilterId(PrefectBaseModel):
    """Filter by `WorkQueue.id`."""

    any_: Optional[List[UUID]] = Field(
        default=None,
        description="A list of work queue ids to include",
    )


class WorkQueueFilterName(PrefectBaseModel):
    """Filter by `WorkQueue.name`."""

    any_: Optional[List[str]] = Field(
        default=None,
        description="A list of work queue names to include",
        examples=[["wq-1", "wq-2"]],
    )

    startswith_: Optional[List[str]] = Field(
        default=None,
        description=(
            "A list of case-insensitive starts-with matches. For example, "
            " passing 'marvin' will match "
            "'marvin', and 'Marvin-robot', but not 'sad-marvin'."
        ),
        examples=[["marvin", "Marvin-robot"]],
    )


class WorkQueueFilter(PrefectBaseModel, OperatorMixin):
    """Filter work queues. Only work queues matching all criteria will be
    returned"""

    id: Optional[WorkQueueFilterId] = Field(
        default=None, description="Filter criteria for `WorkQueue.id`"
    )

    name: Optional[WorkQueueFilterName] = Field(
        default=None, description="Filter criteria for `WorkQueue.name`"
    )


class WorkPoolFilterId(PrefectBaseModel):
    """Filter by `WorkPool.id`."""

    any_: Optional[List[UUID]] = Field(
        default=None, description="A list of work pool ids to include"
    )


class WorkPoolFilterName(PrefectBaseModel):
    """Filter by `WorkPool.name`."""

    any_: Optional[List[str]] = Field(
        default=None, description="A list of work pool names to include"
    )


class WorkPoolFilterType(PrefectBaseModel):
    """Filter by `WorkPool.type`."""

    any_: Optional[List[str]] = Field(
        default=None, description="A list of work pool types to include"
    )


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


class WorkerFilterWorkPoolId(PrefectBaseModel):
    """Filter by `Worker.worker_config_id`."""

    any_: Optional[List[UUID]] = Field(
        default=None, description="A list of work pool ids to include"
    )


class WorkerFilterLastHeartbeatTime(PrefectBaseModel):
    """Filter by `Worker.last_heartbeat_time`."""

    before_: Optional[DateTime] = Field(
        default=None,
        description=(
            "Only include processes whose last heartbeat was at or before this time"
        ),
    )
    after_: Optional[DateTime] = Field(
        default=None,
        description=(
            "Only include processes whose last heartbeat was at or after this time"
        ),
    )


class WorkerFilterStatus(PrefectBaseModel):
    """Filter by `Worker.status`."""

    any_: Optional[List[str]] = Field(
        default=None, description="A list of worker statuses to include"
    )
    not_any_: Optional[List[str]] = Field(
        default=None, description="A list of worker statuses to exclude"
    )


class WorkerFilter(PrefectBaseModel, OperatorMixin):
    # worker_config_id: Optional[WorkerFilterWorkPoolId] = Field(
    #     default=None, description="Filter criteria for `Worker.worker_config_id`"
    # )

    last_heartbeat_time: Optional[WorkerFilterLastHeartbeatTime] = Field(
        default=None,
        description="Filter criteria for `Worker.last_heartbeat_time`",
    )
    status: Optional[WorkerFilterStatus] = Field(
        default=None, description="Filter criteria for `Worker.status`"
    )


class ArtifactFilterId(PrefectBaseModel):
    """Filter by `Artifact.id`."""

    any_: Optional[List[UUID]] = Field(
        default=None, description="A list of artifact ids to include"
    )


class ArtifactFilterKey(PrefectBaseModel):
    """Filter by `Artifact.key`."""

    any_: Optional[List[str]] = Field(
        default=None, description="A list of artifact keys to include"
    )

    like_: Optional[str] = Field(
        default=None,
        description=(
            "A string to match artifact keys against. This can include "
            "SQL wildcard characters like `%` and `_`."
        ),
        examples=["my-artifact-%"],
    )

    exists_: Optional[bool] = Field(
        default=None,
        description=(
            "If `true`, only include artifacts with a non-null key. If `false`, "
            "only include artifacts with a null key."
        ),
    )


class ArtifactFilterFlowRunId(PrefectBaseModel):
    """Filter by `Artifact.flow_run_id`."""

    any_: Optional[List[UUID]] = Field(
        default=None, description="A list of flow run IDs to include"
    )


class ArtifactFilterTaskRunId(PrefectBaseModel):
    """Filter by `Artifact.task_run_id`."""

    any_: Optional[List[UUID]] = Field(
        default=None, description="A list of task run IDs to include"
    )


class ArtifactFilterType(PrefectBaseModel):
    """Filter by `Artifact.type`."""

    any_: Optional[List[str]] = Field(
        default=None, description="A list of artifact types to include"
    )
    not_any_: Optional[List[str]] = Field(
        default=None, description="A list of artifact types to exclude"
    )


class ArtifactFilter(PrefectBaseModel, OperatorMixin):
    """Filter artifacts. Only artifacts matching all criteria will be returned"""

    id: Optional[ArtifactFilterId] = Field(
        default=None, description="Filter criteria for `Artifact.id`"
    )
    key: Optional[ArtifactFilterKey] = Field(
        default=None, description="Filter criteria for `Artifact.key`"
    )
    flow_run_id: Optional[ArtifactFilterFlowRunId] = Field(
        default=None, description="Filter criteria for `Artifact.flow_run_id`"
    )
    task_run_id: Optional[ArtifactFilterTaskRunId] = Field(
        default=None, description="Filter criteria for `Artifact.task_run_id`"
    )
    type: Optional[ArtifactFilterType] = Field(
        default=None, description="Filter criteria for `Artifact.type`"
    )


class ArtifactCollectionFilterLatestId(PrefectBaseModel):
    """Filter by `ArtifactCollection.latest_id`."""

    any_: Optional[List[UUID]] = Field(
        default=None, description="A list of artifact ids to include"
    )


class ArtifactCollectionFilterKey(PrefectBaseModel):
    """Filter by `ArtifactCollection.key`."""

    any_: Optional[List[str]] = Field(
        default=None, description="A list of artifact keys to include"
    )

    like_: Optional[str] = Field(
        default=None,
        description=(
            "A string to match artifact keys against. This can include "
            "SQL wildcard characters like `%` and `_`."
        ),
        examples=["my-artifact-%"],
    )

    exists_: Optional[bool] = Field(
        default=None,
        description=(
            "If `true`, only include artifacts with a non-null key. If `false`, "
            "only include artifacts with a null key. Should return all rows in "
            "the ArtifactCollection table if specified."
        ),
    )


class ArtifactCollectionFilterFlowRunId(PrefectBaseModel):
    """Filter by `ArtifactCollection.flow_run_id`."""

    any_: Optional[List[UUID]] = Field(
        default=None, description="A list of flow run IDs to include"
    )


class ArtifactCollectionFilterTaskRunId(PrefectBaseModel):
    """Filter by `ArtifactCollection.task_run_id`."""

    any_: Optional[List[UUID]] = Field(
        default=None, description="A list of task run IDs to include"
    )


class ArtifactCollectionFilterType(PrefectBaseModel):
    """Filter by `ArtifactCollection.type`."""

    any_: Optional[List[str]] = Field(
        default=None, description="A list of artifact types to include"
    )
    not_any_: Optional[List[str]] = Field(
        default=None, description="A list of artifact types to exclude"
    )


class ArtifactCollectionFilter(PrefectBaseModel, OperatorMixin):
    """Filter artifact collections. Only artifact collections matching all criteria will be returned"""

    latest_id: Optional[ArtifactCollectionFilterLatestId] = Field(
        default=None, description="Filter criteria for `Artifact.id`"
    )
    key: Optional[ArtifactCollectionFilterKey] = Field(
        default=None, description="Filter criteria for `Artifact.key`"
    )
    flow_run_id: Optional[ArtifactCollectionFilterFlowRunId] = Field(
        default=None, description="Filter criteria for `Artifact.flow_run_id`"
    )
    task_run_id: Optional[ArtifactCollectionFilterTaskRunId] = Field(
        default=None, description="Filter criteria for `Artifact.task_run_id`"
    )
    type: Optional[ArtifactCollectionFilterType] = Field(
        default=None, description="Filter criteria for `Artifact.type`"
    )


class VariableFilterId(PrefectBaseModel):
    """Filter by `Variable.id`."""

    any_: Optional[List[UUID]] = Field(
        default=None, description="A list of variable ids to include"
    )


class VariableFilterName(PrefectBaseModel):
    """Filter by `Variable.name`."""

    any_: Optional[List[str]] = Field(
        default=None, description="A list of variables names to include"
    )
    like_: Optional[str] = Field(
        default=None,
        description=(
            "A string to match variable names against. This can include "
            "SQL wildcard characters like `%` and `_`."
        ),
        examples=["my_variable_%"],
    )


class VariableFilterTags(PrefectBaseModel, OperatorMixin):
    """Filter by `Variable.tags`."""

    all_: Optional[List[str]] = Field(
        default=None,
        examples=[["tag-1", "tag-2"]],
        description=(
            "A list of tags. Variables will be returned only if their tags are a"
            " superset of the list"
        ),
    )
    is_null_: Optional[bool] = Field(
        default=None, description="If true, only include Variables without tags"
    )


class VariableFilter(PrefectBaseModel, OperatorMixin):
    """Filter variables. Only variables matching all criteria will be returned"""

    id: Optional[VariableFilterId] = Field(
        default=None, description="Filter criteria for `Variable.id`"
    )
    name: Optional[VariableFilterName] = Field(
        default=None, description="Filter criteria for `Variable.name`"
    )
    tags: Optional[VariableFilterTags] = Field(
        default=None, description="Filter criteria for `Variable.tags`"
    )
