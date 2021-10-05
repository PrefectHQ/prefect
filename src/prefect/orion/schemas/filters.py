"""
Schemas that define Orion filtering operations.

Each filter schema includes logic for transforming itself into a SQL `where` clause.
"""

import datetime
from typing import List, Optional
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.sql.elements import BooleanClauseList
from pydantic import Field

from prefect.orion import schemas
from prefect.orion.models import orm
from prefect.orion.utilities.database import json_has_all_keys
from prefect.orion.utilities.schemas import PrefectBaseModel


class PrefectFilterBaseModel(PrefectBaseModel):
    """Base model for Prefect filters"""

    def as_sql_filter(self) -> BooleanClauseList:
        """Generate SQL filter from provided filter parameters. If no filters parameters are available, return a TRUE filter."""
        filters = self._get_filter_list()
        return sa.and_(*filters) if filters else sa.and_(True)

    def _get_filter_list(self) -> List:
        """Return a list of boolean filter statements based on filter parameters"""
        raise NotImplementedError("_get_filter_list must be implemented")


class FlowFilterId(PrefectFilterBaseModel):
    """Filter by `Flow.id`."""

    any_: List[UUID] = Field(None, description="A list of flow ids to include")

    def _get_filter_list(self) -> List:
        filters = []
        if self.any_ is not None:
            filters.append(orm.Flow.id.in_(self.any_))
        return filters


class FlowFilterName(PrefectFilterBaseModel):
    """Filter by `Flow.name`."""

    any_: List[str] = Field(
        None,
        description="A list of flow names to include",
        example=["my-flow-1", "my-flow-2"],
    )

    def _get_filter_list(self) -> List:
        filters = []
        if self.any_ is not None:
            filters.append(orm.Flow.name.in_(self.any_))
        return filters


class FlowFilterTags(PrefectFilterBaseModel):
    """Filter by `Flow.tags`."""

    all_: List[str] = Field(
        None,
        example=["tag-1", "tag-2"],
        description="A list of tags. Flows will be returned only if their tags are a superset of the list",
    )
    is_null_: bool = Field(None, description="If true, only include flows without tags")

    def _get_filter_list(self) -> List:
        filters = []
        if self.all_ is not None:
            filters.append(json_has_all_keys(orm.Flow.tags, self.all_))
        if self.is_null_ is not None:
            filters.append(
                orm.Flow.tags == [] if self.is_null_ else orm.Flow.tags != []
            )
        return filters


class FlowFilter(PrefectFilterBaseModel):
    """Filter for flows. Only flows matching all criteria will be returned."""

    id: Optional[FlowFilterId] = Field(
        None, description="Filter criteria for `Flow.id`"
    )
    name: Optional[FlowFilterName] = Field(
        None, description="Filter criteria for `Flow.name`"
    )
    tags: Optional[FlowFilterTags] = Field(
        None, description="Filter criteria for `Flow.tags`"
    )

    def _get_filter_list(self) -> List:
        filters = []

        if self.id is not None:
            filters.append(self.id.as_sql_filter())
        if self.name is not None:
            filters.append(self.name.as_sql_filter())
        if self.tags is not None:
            filters.append(self.tags.as_sql_filter())

        return filters


class FlowRunFilterId(PrefectFilterBaseModel):
    """Filter by FlowRun.id."""

    any_: List[UUID] = Field(None, description="A list of flow run ids to include")
    not_any_: List[UUID] = Field(None, description="A list of flow run ids to exclude")

    def _get_filter_list(self) -> List:
        filters = []
        if self.any_ is not None:
            filters.append(orm.FlowRun.id.in_(self.any_))
        if self.not_any_ is not None:
            filters.append(orm.FlowRun.id.not_in(self.not_any_))
        return filters


class FlowRunFilterName(PrefectFilterBaseModel):
    """Filter by `FlowRun.name`."""

    any_: List[str] = Field(
        None,
        description="A list of flow run names to include",
        example=["my-flow-run-1", "my-flow-run-2"],
    )

    def _get_filter_list(self) -> List:
        filters = []
        if self.any_ is not None:
            filters.append(orm.FlowRun.name.in_(self.any_))
        return filters


class FlowRunFilterTags(PrefectFilterBaseModel):
    """Filter by `FlowRun.tags`."""

    all_: List[str] = Field(
        None,
        example=["tag-1", "tag-2"],
        description="A list of tags. Flow runs will be returned only if their tags are a superset of the list",
    )
    is_null_: bool = Field(
        None, description="If true, only include flow runs without tags"
    )

    def _get_filter_list(self) -> List:
        filters = []
        if self.all_ is not None:
            filters.append(json_has_all_keys(orm.FlowRun.tags, self.all_))
        if self.is_null_ is not None:
            filters.append(
                orm.FlowRun.tags == [] if self.is_null_ else orm.FlowRun.tags != []
            )
        return filters


class FlowRunFilterDeploymentId(PrefectFilterBaseModel):
    """Filter by `FlowRun.deployment_id`."""

    any_: List[UUID] = Field(
        None, description="A list of flow run deployment ids to include"
    )
    is_null_: bool = Field(
        None, description="If true, only include flow runs without deployment ids"
    )

    def _get_filter_list(self) -> List:
        filters = []
        if self.any_ is not None:
            filters.append(orm.FlowRun.deployment_id.in_(self.any_))
        if self.is_null_ is not None:
            filters.append(
                orm.FlowRun.deployment_id == None
                if self.is_null_
                else orm.FlowRun.deployment_id != None
            )
        return filters


class FlowRunFilterStateType(PrefectFilterBaseModel):
    """Filter by `FlowRun.state_type`."""

    any_: List[schemas.states.StateType] = Field(
        None, description="A list of flow run state types to include"
    )

    def _get_filter_list(self) -> List:
        filters = []
        if self.any_ is not None:
            filters.append(orm.FlowRun.state_type.in_(self.any_))
        return filters


class FlowRunFilterStateName(PrefectFilterBaseModel):
    any_: List[str] = Field(
        None, description="A list of flow run state names to include"
    )

    def _get_filter_list(self):
        filters = []
        if self.any_ is not None:
            filters.append(orm.FlowRun.state.has(orm.FlowRunState.name.in_(self.any_)))
        return filters


class FlowRunFilterState(PrefectFilterBaseModel):
    type: Optional[FlowRunFilterStateType]
    name: Optional[FlowRunFilterStateName]

    def _get_filter_list(self):
        filters = []
        if self.type is not None:
            filters.extend(self.type._get_filter_list())
        if self.name is not None:
            filters.extend(self.name._get_filter_list())
        return filters


class FlowRunFilterFlowVersion(PrefectFilterBaseModel):
    """Filter by `FlowRun.flow_version`."""

    any_: List[str] = Field(
        None, description="A list of flow run flow_versions to include"
    )

    def _get_filter_list(self) -> List:
        filters = []
        if self.any_ is not None:
            filters.append(orm.FlowRun.flow_version.in_(self.any_))
        return filters


class FlowRunFilterStartTime(PrefectFilterBaseModel):
    """Filter by `FlowRun.start_time`."""

    before_: datetime.datetime = Field(
        None, description="Only include flow runs starting at or before this time"
    )
    after_: datetime.datetime = Field(
        None, description="Only include flow runs starting at or after this time"
    )
    is_null_: bool = Field(
        None, description="If true, only return flow runs without a start time"
    )

    def _get_filter_list(self) -> List:
        filters = []
        if self.before_ is not None:
            filters.append(orm.FlowRun.start_time <= self.before_)
        if self.after_ is not None:
            filters.append(orm.FlowRun.start_time >= self.after_)
        if self.is_null_ is not None:
            filters.append(
                orm.FlowRun.start_time == None
                if self.is_null_
                else orm.FlowRun.start_time != None
            )
        return filters


class FlowRunFilterExpectedStartTime(PrefectFilterBaseModel):
    """Filter by `FlowRun.expected_start_time`."""

    before_: datetime.datetime = Field(
        None,
        description="Only include flow runs scheduled to start at or before this time",
    )
    after_: datetime.datetime = Field(
        None,
        description="Only include flow runs scheduled to start at or after this time",
    )

    def _get_filter_list(self) -> List:
        filters = []
        if self.before_ is not None:
            filters.append(orm.FlowRun.expected_start_time <= self.before_)
        if self.after_ is not None:
            filters.append(orm.FlowRun.expected_start_time >= self.after_)
        return filters


class FlowRunFilterNextScheduledStartTime(PrefectFilterBaseModel):
    """Filter by `FlowRun.next_scheduled_start_time`."""

    before_: datetime.datetime = Field(
        None,
        description="Only include flow runs with a next_scheduled_start_time or before this time",
    )
    after_: datetime.datetime = Field(
        None,
        description="Only include flow runs with a next_scheduled_start_time at or after this time",
    )

    def _get_filter_list(self) -> List:
        filters = []
        if self.before_ is not None:
            filters.append(orm.FlowRun.next_scheduled_start_time <= self.before_)
        if self.after_ is not None:
            filters.append(orm.FlowRun.next_scheduled_start_time >= self.after_)
        return filters


class FlowRunFilterParentTaskRunId(PrefectFilterBaseModel):
    """Filter by `FlowRun.parent_task_run_id`."""

    any_: List[UUID] = Field(
        None, description="A list of flow run parent_task_run_ids to include"
    )
    is_null_: bool = Field(
        None, description="If true, only include flow runs without parent_task_run_id"
    )

    def _get_filter_list(self) -> List:
        filters = []
        if self.any_ is not None:
            filters.append(orm.FlowRun.parent_task_run_id.in_(self.any_))
        if self.is_null_ is not None:
            filters.append(
                orm.FlowRun.parent_task_run_id == None
                if self.is_null_
                else orm.FlowRun.parent_task_run_id != None
            )
        return filters


class FlowRunFilter(PrefectFilterBaseModel):
    """Filter flow runs. Only flow runs matching all criteria will be returned"""

    id: Optional[FlowRunFilterId] = Field(
        None, description="Filter criteria for `FlowRun.id`"
    )
    name: Optional[FlowRunFilterName] = Field(
        None, description="Filter criteria for `FlowRun.name`"
    )
    tags: Optional[FlowRunFilterTags] = Field(
        None, description="Filter criteria for `FlowRun.tags`"
    )
    deployment_id: Optional[FlowRunFilterDeploymentId] = Field(
        None, description="Filter criteria for `FlowRun.deployment_id`"
    )
    state: Optional[FlowRunFilterState] = Field(
        None, description="Filter criteria for `FlowRun.state`"
    )
    flow_version: Optional[FlowRunFilterFlowVersion] = Field(
        None, description="Filter criteria for `FlowRun.flow_version`"
    )
    start_time: Optional[FlowRunFilterStartTime] = Field(
        None, description="Filter criteria for `FlowRun.start_time`"
    )
    expected_start_time: Optional[FlowRunFilterExpectedStartTime] = Field(
        None, description="Filter criteria for `FlowRun.expected_start_time`"
    )
    next_scheduled_start_time: Optional[FlowRunFilterNextScheduledStartTime] = Field(
        None, description="Filter criteria for `FlowRun.next_scheduled_start_time`"
    )
    parent_task_run_id: Optional[FlowRunFilterParentTaskRunId] = Field(
        None, description="Filter criteria for `FlowRun.parent_task_run_id`"
    )

    def _get_filter_list(self) -> List:
        filters = []

        if self.id is not None:
            filters.append(self.id.as_sql_filter())
        if self.name is not None:
            filters.append(self.name.as_sql_filter())
        if self.tags is not None:
            filters.append(self.tags.as_sql_filter())
        if self.deployment_id is not None:
            filters.append(self.deployment_id.as_sql_filter())
        if self.flow_version is not None:
            filters.append(self.flow_version.as_sql_filter())
        if self.state is not None:
            filters.append(self.state.as_sql_filter())
        if self.start_time is not None:
            filters.append(self.start_time.as_sql_filter())
        if self.expected_start_time is not None:
            filters.append(self.expected_start_time.as_sql_filter())
        if self.next_scheduled_start_time is not None:
            filters.append(self.next_scheduled_start_time.as_sql_filter())
        if self.parent_task_run_id is not None:
            filters.append(self.parent_task_run_id.as_sql_filter())

        return filters


class TaskRunFilterId(PrefectFilterBaseModel):
    """Filter by `TaskRun.id`."""

    any_: List[UUID] = Field(None, description="A list of task run ids to include")

    def _get_filter_list(self) -> List:
        filters = []
        if self.any_ is not None:
            filters.append(orm.TaskRun.id.in_(self.any_))
        return filters


class TaskRunFilterName(PrefectFilterBaseModel):
    """Filter by `TaskRun.name`."""

    any_: List[str] = Field(
        None,
        description="A list of task run names to include",
        example=["my-task-run-1", "my-task-run-2"],
    )

    def _get_filter_list(self) -> List:
        filters = []
        if self.any_ is not None:
            filters.append(orm.TaskRun.name.in_(self.any_))
        return filters


class TaskRunFilterTags(PrefectFilterBaseModel):
    """Filter by `TaskRun.tags`."""

    all_: List[str] = Field(
        None,
        example=["tag-1", "tag-2"],
        description="A list of tags. Task runs will be returned only if their tags are a superset of the list",
    )
    is_null_: bool = Field(
        None, description="If true, only include task runs without tags"
    )

    def _get_filter_list(self) -> List:
        filters = []
        if self.all_ is not None:
            filters.append(json_has_all_keys(orm.TaskRun.tags, self.all_))
        if self.is_null_ is not None:
            filters.append(
                orm.TaskRun.tags == [] if self.is_null_ else orm.TaskRun.tags != []
            )
        return filters


class TaskRunFilterStateType(PrefectFilterBaseModel):
    """Filter by `TaskRun.state_type`."""

    any_: List[schemas.states.StateType] = Field(
        None, description="A list of task run state types to include"
    )

    def _get_filter_list(self) -> List:
        filters = []
        if self.any_ is not None:
            filters.append(orm.TaskRun.state_type.in_(self.any_))
        return filters


class TaskRunFilterStateName(PrefectFilterBaseModel):
    any_: List[str] = Field(
        None, description="A list of task run state names to include"
    )

    def _get_filter_list(self):
        filters = []
        if self.any_ is not None:
            filters.append(orm.TaskRun.state.has(orm.TaskRunState.name.in_(self.any_)))
        return filters


class TaskRunFilterState(PrefectFilterBaseModel):
    type: Optional[TaskRunFilterStateType]
    name: Optional[TaskRunFilterStateName]

    def _get_filter_list(self):
        filters = []
        if self.type is not None:
            filters.extend(self.type._get_filter_list())
        if self.name is not None:
            filters.extend(self.name._get_filter_list())
        return filters


class TaskRunFilterSubFlowRuns(PrefectFilterBaseModel):
    """Filter by `TaskRun.subflow_run`."""

    exists_: bool = Field(
        None,
        description="If true, only include task runs that are subflow run parents; if false, exclude parent task runs",
    )

    def _get_filter_list(self) -> List:
        filters = []
        if self.exists_ is True:
            filters.append(orm.TaskRun.subflow_run.has())
        elif self.exists_ is False:
            filters.append(sa.not_(orm.TaskRun.subflow_run.has()))
        return filters


class TaskRunFilterStartTime(PrefectFilterBaseModel):
    """Filter by `TaskRun.start_time`."""

    before_: datetime.datetime = Field(
        None, description="Only include task runs starting at or before this time"
    )
    after_: datetime.datetime = Field(
        None, description="Only include task runs starting at or after this time"
    )
    is_null_: bool = Field(
        None, description="If true, only return task runs without a start time"
    )

    def _get_filter_list(self) -> List:
        filters = []
        if self.before_ is not None:
            filters.append(orm.TaskRun.start_time <= self.before_)
        if self.after_ is not None:
            filters.append(orm.TaskRun.start_time >= self.after_)
        if self.is_null_ is not None:
            filters.append(
                orm.TaskRun.start_time == None
                if self.is_null_
                else orm.TaskRun.start_time != None
            )
        return filters


class TaskRunFilter(PrefectFilterBaseModel):
    """Filter task runs. Only task runs matching all criteria will be returned"""

    id: Optional[TaskRunFilterId] = Field(
        None, description="Filter criteria for `TaskRun.id`"
    )
    name: Optional[TaskRunFilterName] = Field(
        None, description="Filter criteria for `TaskRun.name`"
    )
    tags: Optional[TaskRunFilterTags] = Field(
        None, description="Filter criteria for `TaskRun.tags`"
    )
    state: Optional[TaskRunFilterState] = Field(
        None, description="Filter criteria for `TaskRun.state`"
    )
    start_time: Optional[TaskRunFilterStartTime] = Field(
        None, description="Filter criteria for `TaskRun.start_time`"
    )
    subflow_runs: Optional[TaskRunFilterSubFlowRuns] = Field(
        None, description="Filter criteria for `TaskRun.subflow_run`"
    )

    def _get_filter_list(self) -> List:
        filters = []

        if self.id is not None:
            filters.append(self.id.as_sql_filter())
        if self.name is not None:
            filters.append(self.name.as_sql_filter())
        if self.tags is not None:
            filters.append(self.tags.as_sql_filter())
        if self.state is not None:
            filters.append(self.state.as_sql_filter())
        if self.start_time is not None:
            filters.append(self.start_time.as_sql_filter())
        if self.subflow_runs is not None:
            filters.append(self.subflow_runs.as_sql_filter())

        return filters


class DeploymentFilterId(PrefectFilterBaseModel):
    """Filter by `Deployment.id`."""

    any_: List[UUID] = Field(None, description="A list of deployment ids to include")

    def _get_filter_list(self) -> List:
        filters = []
        if self.any_ is not None:
            filters.append(orm.Deployment.id.in_(self.any_))
        return filters


class DeploymentFilterName(PrefectFilterBaseModel):
    """Filter by `Deployment.name`."""

    any_: List[str] = Field(
        None,
        description="A list of deployment names to include",
        example=["my-deployment-1", "my-deployment-2"],
    )

    def _get_filter_list(self) -> List:
        filters = []
        if self.any_ is not None:
            filters.append(orm.Deployment.name.in_(self.any_))
        return filters


class DeploymentFilterIsScheduleActive(PrefectFilterBaseModel):
    """Filter by `Deployment.is_schedule_active`."""

    eq_: bool = Field(
        None,
        description="Only returns where deployment schedule is/is not active",
    )

    def _get_filter_list(self) -> List:
        filters = []
        if self.eq_ is not None:
            filters.append(orm.Deployment.is_schedule_active.is_(self.eq_))
        return filters


class DeploymentFilterTags(PrefectFilterBaseModel):
    """Filter by `Deployment.tags`."""

    all_: List[str] = Field(
        None,
        example=["tag-1", "tag-2"],
        description="A list of tags. Deployments will be returned only if their tags are a superset of the list",
    )
    is_null_: bool = Field(
        None, description="If true, only include deployments without tags"
    )

    def _get_filter_list(self) -> List:
        filters = []
        if self.all_ is not None:
            filters.append(json_has_all_keys(orm.Deployment.tags, self.all_))
        if self.is_null_ is not None:
            filters.append(
                orm.Deployment.tags == []
                if self.is_null_
                else orm.Deployment.tags != []
            )
        return filters


class DeploymentFilter(PrefectFilterBaseModel):
    """Filter for deployments. Only deployments matching all criteria will be returned."""

    id: Optional[DeploymentFilterId] = Field(
        None, description="Filter criteria for `Deployment.id`"
    )
    name: Optional[DeploymentFilterName] = Field(
        None, description="Filter criteria for `Deployment.name`"
    )
    is_schedule_active: Optional[DeploymentFilterIsScheduleActive] = Field(
        None, description="Filter criteria for `Deployment.is_schedule_active`"
    )
    tags: Optional[DeploymentFilterTags] = Field(
        None, description="Filter criteria for `Deployment.tags`"
    )

    def _get_filter_list(self) -> List:
        filters = []

        if self.id is not None:
            filters.append(self.id.as_sql_filter())
        if self.name is not None:
            filters.append(self.name.as_sql_filter())
        if self.is_schedule_active is not None:
            filters.append(self.is_schedule_active.as_sql_filter())
        if self.tags is not None:
            filters.append(self.tags.as_sql_filter())

        return filters


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
