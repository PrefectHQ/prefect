"""
Schemas that define Orion filtering operations.

Each filter schema includes logic for transforming itself into a SQL `where` clause.
"""

import datetime
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

import sqlalchemy as sa
from pydantic import Field
from sqlalchemy.sql.elements import BooleanClauseList

import prefect.orion.schemas as schemas
from prefect.orion.utilities.schemas import PrefectBaseModel

if TYPE_CHECKING:
    from prefect.orion.database.interface import OrionDBInterface

# TOOD: Consider moving the `as_sql_filter` functions out of here since they are a
#       database model level function and do not properly separate concerns when
#       present in the schemas module


class PrefectFilterBaseModel(PrefectBaseModel):
    """Base model for Prefect filters"""

    class Config:
        extra = "forbid"

    def as_sql_filter(self, db: "OrionDBInterface") -> BooleanClauseList:
        """Generate SQL filter from provided filter parameters. If no filters parameters are available, return a TRUE filter."""
        filters = self._get_filter_list(db)
        return sa.and_(*filters) if filters else sa.and_(True)

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        """Return a list of boolean filter statements based on filter parameters"""
        raise NotImplementedError("_get_filter_list must be implemented")


class FlowFilterId(PrefectFilterBaseModel):
    """Filter by `Flow.id`."""

    any_: List[UUID] = Field(None, description="A list of flow ids to include")

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        filters = []
        if self.any_ is not None:
            filters.append(db.Flow.id.in_(self.any_))
        return filters


class FlowFilterName(PrefectFilterBaseModel):
    """Filter by `Flow.name`."""

    any_: List[str] = Field(
        None,
        description="A list of flow names to include",
        example=["my-flow-1", "my-flow-2"],
    )

    like_: str = Field(
        None,
        description=(
            "A case-insensitive partial match. For example, "
            " passing 'marvin' will match "
            "'marvin', 'sad-Marvin', and 'marvin-robot'."
        ),
        example="marvin",
    )

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        filters = []
        if self.any_ is not None:
            filters.append(db.Flow.name.in_(self.any_))
        if self.like_ is not None:
            filters.append(db.Flow.name.ilike(f"%{self.like_}%"))
        return filters


class FlowFilterTags(PrefectFilterBaseModel):
    """Filter by `Flow.tags`."""

    all_: List[str] = Field(
        None,
        example=["tag-1", "tag-2"],
        description="A list of tags. Flows will be returned only if their tags are a superset of the list",
    )
    is_null_: bool = Field(None, description="If true, only include flows without tags")

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        from prefect.orion.utilities.database import json_has_all_keys

        filters = []
        if self.all_ is not None:
            filters.append(json_has_all_keys(db.Flow.tags, self.all_))
        if self.is_null_ is not None:
            filters.append(db.Flow.tags == [] if self.is_null_ else db.Flow.tags != [])
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

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        filters = []

        if self.id is not None:
            filters.append(self.id.as_sql_filter(db))
        if self.name is not None:
            filters.append(self.name.as_sql_filter(db))
        if self.tags is not None:
            filters.append(self.tags.as_sql_filter(db))

        return filters


class FlowRunFilterId(PrefectFilterBaseModel):
    """Filter by FlowRun.id."""

    any_: List[UUID] = Field(None, description="A list of flow run ids to include")
    not_any_: List[UUID] = Field(None, description="A list of flow run ids to exclude")

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        filters = []
        if self.any_ is not None:
            filters.append(db.FlowRun.id.in_(self.any_))
        if self.not_any_ is not None:
            filters.append(db.FlowRun.id.not_in(self.not_any_))
        return filters


class FlowRunFilterName(PrefectFilterBaseModel):
    """Filter by `FlowRun.name`."""

    any_: List[str] = Field(
        None,
        description="A list of flow run names to include",
        example=["my-flow-run-1", "my-flow-run-2"],
    )

    like_: str = Field(
        None,
        description=(
            "A case-insensitive partial match. For example, "
            " passing 'marvin' will match "
            "'marvin', 'sad-Marvin', and 'marvin-robot'."
        ),
        example="marvin",
    )

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        filters = []
        if self.any_ is not None:
            filters.append(db.FlowRun.name.in_(self.any_))
        if self.like_ is not None:
            filters.append(db.FlowRun.name.ilike(f"%{self.like_}%"))
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

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        from prefect.orion.utilities.database import json_has_all_keys

        filters = []
        if self.all_ is not None:
            filters.append(json_has_all_keys(db.FlowRun.tags, self.all_))
        if self.is_null_ is not None:
            filters.append(
                db.FlowRun.tags == [] if self.is_null_ else db.FlowRun.tags != []
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

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        filters = []
        if self.any_ is not None:
            filters.append(db.FlowRun.deployment_id.in_(self.any_))
        if self.is_null_ is not None:
            filters.append(
                db.FlowRun.deployment_id == None
                if self.is_null_
                else db.FlowRun.deployment_id != None
            )
        return filters


class FlowRunFilterStateType(PrefectFilterBaseModel):
    """Filter by `FlowRun.state_type`."""

    any_: List[schemas.states.StateType] = Field(
        None, description="A list of flow run state types to include"
    )

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        filters = []
        if self.any_ is not None:
            filters.append(db.FlowRun.state_type.in_(self.any_))
        return filters


class FlowRunFilterStateName(PrefectFilterBaseModel):
    any_: List[str] = Field(
        None, description="A list of flow run state names to include"
    )

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        filters = []
        if self.any_ is not None:
            filters.append(db.FlowRun.state_name.in_(self.any_))
        return filters


class FlowRunFilterState(PrefectFilterBaseModel):
    type: Optional[FlowRunFilterStateType]
    name: Optional[FlowRunFilterStateName]

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        filters = []
        if self.type is not None:
            filters.extend(self.type._get_filter_list(db))
        if self.name is not None:
            filters.extend(self.name._get_filter_list(db))
        return filters


class FlowRunFilterFlowVersion(PrefectFilterBaseModel):
    """Filter by `FlowRun.flow_version`."""

    any_: List[str] = Field(
        None, description="A list of flow run flow_versions to include"
    )

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        filters = []
        if self.any_ is not None:
            filters.append(db.FlowRun.flow_version.in_(self.any_))
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

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        filters = []
        if self.before_ is not None:
            filters.append(db.FlowRun.start_time <= self.before_)
        if self.after_ is not None:
            filters.append(db.FlowRun.start_time >= self.after_)
        if self.is_null_ is not None:
            filters.append(
                db.FlowRun.start_time == None
                if self.is_null_
                else db.FlowRun.start_time != None
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

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        filters = []
        if self.before_ is not None:
            filters.append(db.FlowRun.expected_start_time <= self.before_)
        if self.after_ is not None:
            filters.append(db.FlowRun.expected_start_time >= self.after_)
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

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        filters = []
        if self.before_ is not None:
            filters.append(db.FlowRun.next_scheduled_start_time <= self.before_)
        if self.after_ is not None:
            filters.append(db.FlowRun.next_scheduled_start_time >= self.after_)
        return filters


class FlowRunFilterParentTaskRunId(PrefectFilterBaseModel):
    """Filter by `FlowRun.parent_task_run_id`."""

    any_: List[UUID] = Field(
        None, description="A list of flow run parent_task_run_ids to include"
    )
    is_null_: bool = Field(
        None, description="If true, only include flow runs without parent_task_run_id"
    )

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        filters = []
        if self.any_ is not None:
            filters.append(db.FlowRun.parent_task_run_id.in_(self.any_))
        if self.is_null_ is not None:
            filters.append(
                db.FlowRun.parent_task_run_id == None
                if self.is_null_
                else db.FlowRun.parent_task_run_id != None
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

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        filters = []

        if self.id is not None:
            filters.append(self.id.as_sql_filter(db))
        if self.name is not None:
            filters.append(self.name.as_sql_filter(db))
        if self.tags is not None:
            filters.append(self.tags.as_sql_filter(db))
        if self.deployment_id is not None:
            filters.append(self.deployment_id.as_sql_filter(db))
        if self.flow_version is not None:
            filters.append(self.flow_version.as_sql_filter(db))
        if self.state is not None:
            filters.append(self.state.as_sql_filter(db))
        if self.start_time is not None:
            filters.append(self.start_time.as_sql_filter(db))
        if self.expected_start_time is not None:
            filters.append(self.expected_start_time.as_sql_filter(db))
        if self.next_scheduled_start_time is not None:
            filters.append(self.next_scheduled_start_time.as_sql_filter(db))
        if self.parent_task_run_id is not None:
            filters.append(self.parent_task_run_id.as_sql_filter(db))

        return filters


class TaskRunFilterId(PrefectFilterBaseModel):
    """Filter by `TaskRun.id`."""

    any_: List[UUID] = Field(None, description="A list of task run ids to include")

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        filters = []
        if self.any_ is not None:
            filters.append(db.TaskRun.id.in_(self.any_))
        return filters


class TaskRunFilterName(PrefectFilterBaseModel):
    """Filter by `TaskRun.name`."""

    any_: List[str] = Field(
        None,
        description="A list of task run names to include",
        example=["my-task-run-1", "my-task-run-2"],
    )

    like_: str = Field(
        None,
        description=(
            "A case-insensitive partial match. For example, "
            " passing 'marvin' will match "
            "'marvin', 'sad-Marvin', and 'marvin-robot'."
        ),
        example="marvin",
    )

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        filters = []
        if self.any_ is not None:
            filters.append(db.TaskRun.name.in_(self.any_))
        if self.like_ is not None:
            filters.append(db.TaskRun.name.ilike(f"%{self.like_}%"))
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

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        from prefect.orion.utilities.database import json_has_all_keys

        filters = []
        if self.all_ is not None:
            filters.append(json_has_all_keys(db.TaskRun.tags, self.all_))
        if self.is_null_ is not None:
            filters.append(
                db.TaskRun.tags == [] if self.is_null_ else db.TaskRun.tags != []
            )
        return filters


class TaskRunFilterStateType(PrefectFilterBaseModel):
    """Filter by `TaskRun.state_type`."""

    any_: List[schemas.states.StateType] = Field(
        None, description="A list of task run state types to include"
    )

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        filters = []
        if self.any_ is not None:
            filters.append(db.TaskRun.state_type.in_(self.any_))
        return filters


class TaskRunFilterStateName(PrefectFilterBaseModel):
    any_: List[str] = Field(
        None, description="A list of task run state names to include"
    )

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        filters = []
        if self.any_ is not None:
            filters.append(db.TaskRun.state_name.in_(self.any_))
        return filters


class TaskRunFilterState(PrefectFilterBaseModel):
    type: Optional[TaskRunFilterStateType]
    name: Optional[TaskRunFilterStateName]

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        filters = []
        if self.type is not None:
            filters.extend(self.type._get_filter_list(db))
        if self.name is not None:
            filters.extend(self.name._get_filter_list(db))
        return filters


class TaskRunFilterSubFlowRuns(PrefectFilterBaseModel):
    """Filter by `TaskRun.subflow_run`."""

    exists_: bool = Field(
        None,
        description="If true, only include task runs that are subflow run parents; if false, exclude parent task runs",
    )

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        filters = []
        if self.exists_ is True:
            filters.append(db.TaskRun.subflow_run.has())
        elif self.exists_ is False:
            filters.append(sa.not_(db.TaskRun.subflow_run.has()))
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

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        filters = []
        if self.before_ is not None:
            filters.append(db.TaskRun.start_time <= self.before_)
        if self.after_ is not None:
            filters.append(db.TaskRun.start_time >= self.after_)
        if self.is_null_ is not None:
            filters.append(
                db.TaskRun.start_time == None
                if self.is_null_
                else db.TaskRun.start_time != None
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

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        filters = []

        if self.id is not None:
            filters.append(self.id.as_sql_filter(db))
        if self.name is not None:
            filters.append(self.name.as_sql_filter(db))
        if self.tags is not None:
            filters.append(self.tags.as_sql_filter(db))
        if self.state is not None:
            filters.append(self.state.as_sql_filter(db))
        if self.start_time is not None:
            filters.append(self.start_time.as_sql_filter(db))
        if self.subflow_runs is not None:
            filters.append(self.subflow_runs.as_sql_filter(db))

        return filters


class DeploymentFilterId(PrefectFilterBaseModel):
    """Filter by `Deployment.id`."""

    any_: List[UUID] = Field(None, description="A list of deployment ids to include")

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        filters = []
        if self.any_ is not None:
            filters.append(db.Deployment.id.in_(self.any_))
        return filters


class DeploymentFilterName(PrefectFilterBaseModel):
    """Filter by `Deployment.name`."""

    any_: List[str] = Field(
        None,
        description="A list of deployment names to include",
        example=["my-deployment-1", "my-deployment-2"],
    )

    like_: str = Field(
        None,
        description=(
            "A case-insensitive partial match. For example, "
            " passing 'marvin' will match "
            "'marvin', 'sad-Marvin', and 'marvin-robot'."
        ),
        example="marvin",
    )

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        filters = []
        if self.any_ is not None:
            filters.append(db.Deployment.name.in_(self.any_))
        if self.like_ is not None:
            filters.append(db.Deployment.name.ilike(f"%{self.like_}%"))
        return filters


class DeploymentFilterIsScheduleActive(PrefectFilterBaseModel):
    """Filter by `Deployment.is_schedule_active`."""

    eq_: bool = Field(
        None,
        description="Only returns where deployment schedule is/is not active",
    )

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        filters = []
        if self.eq_ is not None:
            filters.append(db.Deployment.is_schedule_active.is_(self.eq_))
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

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        from prefect.orion.utilities.database import json_has_all_keys

        filters = []
        if self.all_ is not None:
            filters.append(json_has_all_keys(db.Deployment.tags, self.all_))
        if self.is_null_ is not None:
            filters.append(
                db.Deployment.tags == [] if self.is_null_ else db.Deployment.tags != []
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

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        filters = []

        if self.id is not None:
            filters.append(self.id.as_sql_filter(db))
        if self.name is not None:
            filters.append(self.name.as_sql_filter(db))
        if self.is_schedule_active is not None:
            filters.append(self.is_schedule_active.as_sql_filter(db))
        if self.tags is not None:
            filters.append(self.tags.as_sql_filter(db))

        return filters


class LogFilterName(PrefectFilterBaseModel):
    """Filter by `Log.name`."""

    any_: List[str] = Field(
        None,
        description="A list of log names to include",
        example=["prefect.logger.flow_runs", "prefect.logger.task_runs"],
    )

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        filters = []
        if self.any_ is not None:
            filters.append(db.Log.name.in_(self.any_))
        return filters


class LogFilterLevel(PrefectFilterBaseModel):
    """Filter by `Log.level`."""

    ge_: int = Field(
        None,
        description="Include logs with a level greater than or equal to this level",
        example=20,
    )

    le_: int = Field(
        None,
        description="Include logs with a level less than or equal to this level",
        example=50,
    )

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        filters = []
        if self.ge_ is not None:
            filters.append(db.Log.level >= self.ge_)
        if self.le_ is not None:
            filters.append(db.Log.level <= self.le_)
        return filters


class LogFilterTimestamp(PrefectFilterBaseModel):
    """Filter by `Log.timestamp`."""

    before_: datetime.datetime = Field(
        None, description="Only include logs with a timestamp at or before this time"
    )
    after_: datetime.datetime = Field(
        None, description="Only include logs with a timestamp at or after this time"
    )

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        filters = []
        if self.before_ is not None:
            filters.append(db.Log.timestamp <= self.before_)
        if self.after_ is not None:
            filters.append(db.Log.timestamp >= self.after_)
        return filters


class LogFilterFlowRunId(PrefectFilterBaseModel):
    """Filter by `Log.flow_run_id`."""

    any_: List[UUID] = Field(None, description="A list of flow run IDs to include")

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        filters = []
        if self.any_ is not None:
            filters.append(db.Log.flow_run_id.in_(self.any_))
        return filters


class LogFilterTaskRunId(PrefectFilterBaseModel):
    """Filter by `Log.task_run_id`."""

    any_: List[UUID] = Field(None, description="A list of task run IDs to include")

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        filters = []
        if self.any_ is not None:
            filters.append(db.Log.task_run_id.in_(self.any_))
        return filters


class LogFilter(PrefectFilterBaseModel):
    """Filter logs. Only logs matching all criteria will be returned"""

    level: Optional[LogFilterLevel] = Field(
        None, description="Filter criteria for `Log.level`"
    )
    timestamp: Optional[LogFilterTimestamp] = Field(
        None, description="Filter criteria for `Log.timestamp`"
    )
    flow_run_id: Optional[LogFilterFlowRunId] = Field(
        None, description="Filter criteria for `Log.flow_run_id`"
    )
    task_run_id: Optional[LogFilterTaskRunId] = Field(
        None, description="Filter criteria for `Log.task_run_id`"
    )

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        filters = []

        if self.level is not None:
            filters.append(self.level.as_sql_filter(db))
        if self.timestamp is not None:
            filters.append(self.timestamp.as_sql_filter(db))
        if self.flow_run_id is not None:
            filters.append(self.flow_run_id.as_sql_filter(db))
        if self.task_run_id is not None:
            filters.append(self.task_run_id.as_sql_filter(db))

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


class BlockTypeFilterName(PrefectFilterBaseModel):
    """Filter by `BlockType.name`"""

    like_: str = Field(
        None,
        description=(
            "A case-insensitive partial match. For example, "
            " passing 'marvin' will match "
            "'marvin', 'sad-Marvin', and 'marvin-robot'."
        ),
        example="marvin",
    )

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        filters = []
        if self.like_ is not None:
            filters.append(db.BlockType.name.ilike(f"%{self.like_}%"))
        return filters


class BlockTypeFilter(PrefectFilterBaseModel):
    """Filter BlockTypes"""

    name: Optional[BlockTypeFilterName] = Field(
        None, description="Filter criteria for `BlockType.name`"
    )

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        filters = []

        if self.name is not None:
            filters.append(self.name.as_sql_filter(db))

        return filters


class BlockSchemaFilterBlockTypeId(PrefectFilterBaseModel):
    """Filter by `BlockSchema.block_type_id`."""

    any_: List[UUID] = Field(None, description="A list of block type ids to include")

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        filters = []
        if self.any_ is not None:
            filters.append(db.BlockSchema.block_type_id.in_(self.any_))
        return filters


class BlockSchemaFilterCapabilities(PrefectFilterBaseModel):
    """Filter by `BlockSchema.capabilities`"""

    all_: List[str] = Field(
        None,
        example=["write-storage", "read-storage"],
        description="A list of block capabilities. Block entities will be returned "
        "only if an associated block schema has a superset of the defined capabilities.",
    )

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        from prefect.orion.utilities.database import json_has_all_keys

        filters = []
        if self.all_ is not None:
            filters.append(json_has_all_keys(db.BlockSchema.capabilities, self.all_))
        return filters


class BlockSchemaFilter(PrefectFilterBaseModel):
    """Filter BlockSchemas"""

    block_type_id: Optional[BlockSchemaFilterBlockTypeId] = Field(
        None, description="Filter criteria for `BlockSchema.block_type_id`"
    )
    block_capabilities: Optional[BlockSchemaFilterCapabilities] = Field(
        None, description="Filter criteria for `BlockSchema.capabilities`"
    )

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        filters = []

        if self.block_type_id is not None:
            filters.append(self.block_type_id.as_sql_filter(db))
        if self.block_capabilities is not None:
            filters.append(self.block_capabilities.as_sql_filter(db))

        return filters


class BlockDocumentFilterIsAnonymous(PrefectFilterBaseModel):
    """Filter by `BlockDocument.is_anonymous`."""

    eq_: bool = Field(
        None,
        description="Filter block documents for only those that are or are not anonymous.",
    )

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        filters = []
        if self.eq_ is not None:
            filters.append(db.BlockDocument.is_anonymous.is_(self.eq_))
        return filters


class BlockDocumentFilterBlockTypeId(PrefectFilterBaseModel):
    """Filter by `BlockDocument.block_type_id`."""

    any_: List[UUID] = Field(None, description="A list of block type ids to include")

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        filters = []
        if self.any_ is not None:
            filters.append(db.BlockDocument.block_type_id.in_(self.any_))
        return filters


class BlockDocumentFilter(PrefectFilterBaseModel):
    """Filter BlockDocuments. Only BlockDocuments matching all criteria will be returned"""

    is_anonymous: Optional[BlockDocumentFilterIsAnonymous] = Field(
        # default is to exclude anonymous blocks
        BlockDocumentFilterIsAnonymous(eq_=False),
        description=(
            "Filter criteria for `BlockDocument.is_anonymous`. "
            "Defaults to excluding anonymous blocks."
        ),
    )
    block_type_id: Optional[BlockDocumentFilterBlockTypeId] = Field(
        None, description="Filter criteria for `BlockDocument.block_type_id`"
    )

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        filters = []
        if self.is_anonymous is not None:
            filters.append(self.is_anonymous.as_sql_filter(db))
        if self.block_type_id is not None:
            filters.append(self.block_type_id.as_sql_filter(db))

        return filters


class FlowRunNotificationPolicyFilterIsActive(PrefectFilterBaseModel):
    """Filter by `FlowRunNotificationPolicy.is_active`."""

    eq_: bool = Field(
        None,
        description="Filter notification policies for only those that are or are not active.",
    )

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        filters = []
        if self.eq_ is not None:
            filters.append(db.FlowRunNotificationPolicy.is_active.is_(self.eq_))
        return filters


class FlowRunNotificationPolicyFilter(PrefectFilterBaseModel):
    """Filter FlowRunNotificationPolicies."""

    is_active: Optional[FlowRunNotificationPolicyFilterIsActive] = Field(
        FlowRunNotificationPolicyFilterIsActive(eq_=False),
        description=("Filter criteria for `FlowRunNotificationPolicy.is_active`. "),
    )

    def _get_filter_list(self, db: "OrionDBInterface") -> List:
        filters = []
        if self.is_active is not None:
            filters.append(self.is_active.as_sql_filter(db))

        return filters
