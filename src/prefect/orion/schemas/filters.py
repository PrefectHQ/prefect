import datetime
from typing import List, Optional
from uuid import UUID

import sqlalchemy as sa
from pydantic import Field, conint, root_validator

import prefect
from prefect.orion import schemas
from prefect.orion.models import orm
from prefect.orion.utilities.database import json_has_all_keys
from prefect.orion.utilities.schemas import PrefectBaseModel


class Pagination(PrefectBaseModel):
    limit: conint(
        ge=0, le=prefect.settings.orion.api.default_limit
    ) = prefect.settings.orion.api.default_limit
    offset: conint(ge=0) = 0


class PrefectFilterBaseModel(PrefectBaseModel):
    """Base model for Prefect filters"""

    @root_validator
    def check_at_least_one_operator_is_not_none(cls, values):
        """At least one operator must be specified in order to generate sql filters"""
        if not any([val is not None for val in values.values()]):
            raise ValueError(
                f"Prefect Filter must have at least one operator with arguments.\n"
                f"{cls.__name__!r} got operator input: {values}"
            )
        return values

    @root_validator
    def check_all_and_is_null_are_not_both_supplied(cls, values):
        """For filters with all_ and is_null_, don't allow both fields to be provided by default"""
        if values.get("all_") is not None and values.get("is_null_"):
            raise ValueError(
                f"Cannot provide Prefect Filter {cls.__name__!r} all_ with is_null_ = True"
            )
        return values

    @root_validator
    def check_any_and_is_null_are_not_both_supplied(cls, values):
        """For filters with any_ and is_null_, don't allow both fields to be provided by default"""
        if values.get("any_") is not None and values.get("is_null_"):
            raise ValueError(
                f"Cannot provide Prefect Filter {cls.__name__!r} any_ with is_null_ = True"
            )
        return values

    @root_validator
    def test_before_and_after_are_not_mutually_exclusive(cls, values):
        """For filters with before_ and after_, make sure they are not mutally exclusive by default"""
        if values.get("before_") is not None and values.get("after_") is not None:
            if values.get("before_") <= values.get("after_"):
                raise ValueError(
                    f"Cannot provide Prefect Filter {cls.__name__!r} where before_ is less than after_"
                )
        return values


class FlowFilterIds(PrefectFilterBaseModel):
    any_: List[UUID] = Field(None, description="A list of flow ids to include")

    def as_sql_filter(self):
        return orm.Flow.id.in_(self.any_)


class FlowFilterNames(PrefectFilterBaseModel):
    any_: List[str] = Field(
        None,
        description="A list of flow names to include",
        example=["my-flow-1", "my-flow-2"],
    )

    def as_sql_filter(self):
        return orm.Flow.name.in_(self.any_)


class FlowFilterTags(PrefectFilterBaseModel):
    all_: List[str] = Field(
        None,
        example=["tag-1", "tag-2"],
        description="A list of tags. Flows will be returned only if their tags are a superset of the list",
    )
    is_null_: bool = Field(None, description="If true, only include flows without tags")

    def as_sql_filter(self):
        if self.all_ is not None:
            return json_has_all_keys(orm.Flow.tags, self.all_)
        elif self.is_null_ is not None:
            return orm.Flow.tags == [] if self.is_null_ else orm.Flow.tags != []


class FlowFilter(PrefectFilterBaseModel):
    """Filter for flows. Only flows matching all criteria will be returned"""

    ids: Optional[FlowFilterIds]
    names: Optional[FlowFilterNames]
    tags: Optional[FlowFilterTags]

    def as_sql_filter(self) -> List:
        filters = []

        if self.ids is not None:
            filters.append(self.ids.as_sql_filter())
        if self.names is not None:
            filters.append(self.names.as_sql_filter())
        if self.tags is not None:
            filters.append(self.tags.as_sql_filter())

        return sa.and_(*filters) if filters else sa.and_(True)


class FlowRunFilterIds(PrefectFilterBaseModel):
    any_: List[UUID] = Field(None, description="A list of flow run ids to include")

    def as_sql_filter(self):
        return orm.FlowRun.id.in_(self.any_)


class FlowRunFilterTags(PrefectFilterBaseModel):
    all_: List[str] = Field(
        None,
        example=["tag-1", "tag-2"],
        description="A list of tags. Flow runs will be returned only if their tags are a superset of the list",
    )
    is_null_: bool = Field(
        None, description="If true, only include flow runs without tags"
    )

    def as_sql_filter(self):
        if self.all_ is not None:
            return json_has_all_keys(orm.FlowRun.tags, self.all_)
        elif self.is_null_ is not None:
            return orm.FlowRun.tags == [] if self.is_null_ else orm.FlowRun.tags != []


class FlowRunFilterDeploymentIds(PrefectFilterBaseModel):
    any_: List[UUID] = Field(
        None, description="A list of flow run deployment ids to include"
    )
    is_null_: bool = Field(
        None, description="If true, only include flow runs without deployment ids"
    )

    def as_sql_filter(self):
        if self.any_ is not None:
            return orm.FlowRun.deployment_id.in_(self.any_)
        elif self.is_null_ is not None:
            return (
                orm.FlowRun.deployment_id == None
                if self.is_null_
                else orm.FlowRun.deployment_id != None
            )


class FlowRunFilterStateTypes(PrefectFilterBaseModel):
    any_: List[schemas.states.StateType] = Field(
        None, description="A list of flow run state_types to include"
    )

    def as_sql_filter(self):
        return orm.FlowRun.state_type.in_(self.any_)


class FlowRunFilterFlowVersions(PrefectFilterBaseModel):
    any_: List[str] = Field(
        None, description="A list of flow run flow_versions to include"
    )

    def as_sql_filter(self):
        return orm.FlowRun.flow_version.in_(self.any_)


class FlowRunFilterStartTime(PrefectFilterBaseModel):
    before_: datetime.datetime = Field(
        None, description="Only include flow runs starting at or before this time"
    )
    after_: datetime.datetime = Field(
        None, description="Only include flow runs starting at or after this time"
    )

    def as_sql_filter(self):
        if self.before_ and self.after_:
            return orm.FlowRun.start_time.between(self.after_, self.before_)
        elif self.before_:
            return orm.FlowRun.start_time <= self.before_
        elif self.after_:
            return orm.FlowRun.start_time >= self.after_


class FlowRunFilterExpectedStartTime(PrefectFilterBaseModel):
    before_: datetime.datetime = Field(
        None,
        description="Only include flow runs scheduled to start at or before this time",
    )
    after_: datetime.datetime = Field(
        None,
        description="Only include flow runs scheduled to start at or after this time",
    )

    def as_sql_filter(self):
        if self.before_ and self.after_:
            return orm.FlowRun.expected_start_time.between(self.after_, self.before_)
        elif self.before_:
            return orm.FlowRun.expected_start_time <= self.before_
        elif self.after_:
            return orm.FlowRun.expected_start_time >= self.after_


class FlowRunFilterNextScheduledStartTime(PrefectFilterBaseModel):
    before_: datetime.datetime = Field(
        None,
        description="Only include flow runs with a next_scheduled_start_time or before this time",
    )
    after_: datetime.datetime = Field(
        None,
        description="Only include flow runs with a next_scheduled_start_time at or after this time",
    )

    def as_sql_filter(self):
        if self.before_ and self.after_:
            return orm.FlowRun.next_scheduled_start_time.between(
                self.after_, self.before_
            )
        elif self.before_:
            return orm.FlowRun.next_scheduled_start_time <= self.before_
        elif self.after_:
            return orm.FlowRun.next_scheduled_start_time >= self.after_


class FlowRunFilterParentTaskRunIds(PrefectFilterBaseModel):
    any_: List[UUID] = Field(
        None, description="A list of flow run parent_task_run_ids to include"
    )
    is_null_: bool = Field(
        None, description="If true, only include flow runs without parent_task_run_id"
    )

    def as_sql_filter(self):
        if self.any_ is not None:
            return orm.FlowRun.parent_task_run_id.in_(self.any_)
        elif self.is_null_ is not None:
            return (
                orm.FlowRun.parent_task_run_id == None
                if self.is_null_
                else orm.FlowRun.parent_task_run_id != None
            )


class FlowRunFilter(PrefectFilterBaseModel):
    """Filter flow runs. Only flow runs matching all criteria will be returned"""

    ids: Optional[FlowRunFilterIds]
    tags: Optional[FlowRunFilterTags]
    deployment_ids: Optional[FlowRunFilterDeploymentIds]
    state_types: Optional[FlowRunFilterStateTypes]
    flow_versions: Optional[FlowRunFilterFlowVersions]
    start_time: Optional[FlowRunFilterStartTime]
    expected_start_time: Optional[FlowRunFilterExpectedStartTime]
    next_scheduled_start_time: Optional[FlowRunFilterNextScheduledStartTime]
    parent_task_run_ids: Optional[FlowRunFilterParentTaskRunIds]

    def as_sql_filter(self) -> List:
        filters = []

        if self.ids is not None:
            filters.append(self.ids.as_sql_filter())
        if self.tags is not None:
            filters.append(self.tags.as_sql_filter())
        if self.deployment_ids is not None:
            filters.append(self.deployment_ids.as_sql_filter())
        if self.flow_versions is not None:
            filters.append(self.flow_versions.as_sql_filter())
        if self.state_types is not None:
            filters.append(self.state_types.as_sql_filter())
        if self.start_time is not None:
            filters.append(self.start_time.as_sql_filter())
        if self.expected_start_time is not None:
            filters.append(self.expected_start_time.as_sql_filter())
        if self.next_scheduled_start_time is not None:
            filters.append(self.next_scheduled_start_time.as_sql_filter())
        if self.parent_task_run_ids is not None:
            filters.append(self.parent_task_run_ids.as_sql_filter())

        return sa.and_(*filters) if filters else sa.and_(True)


class TaskRunFilterIds(PrefectFilterBaseModel):
    any_: List[UUID] = Field(None, description="A list of task run ids to include")

    def as_sql_filter(self):
        return orm.TaskRun.id.in_(self.any_)


class TaskRunFilterTags(PrefectFilterBaseModel):
    all_: List[str] = Field(
        None,
        example=["tag-1", "tag-2"],
        description="A list of tags. Task runs will be returned only if their tags are a superset of the list",
    )
    is_null_: bool = Field(
        None, description="If true, only include task runs without tags"
    )

    def as_sql_filter(self):
        if self.all_ is not None:
            return json_has_all_keys(orm.TaskRun.tags, self.all_)
        elif self.is_null_ is not None:
            return orm.TaskRun.tags == [] if self.is_null_ else orm.TaskRun.tags != []


class TaskRunFilterStateTypes(PrefectFilterBaseModel):
    any_: List[schemas.states.StateType] = Field(
        None, description="A list of task run state types to include"
    )

    def as_sql_filter(self):
        return orm.TaskRun.state_type.in_(self.any_)


class TaskRunFilterStartTime(PrefectFilterBaseModel):
    before_: datetime.datetime = Field(
        None, description="Only include task runs starting at or before this time"
    )
    after_: datetime.datetime = Field(
        None, description="Only include task runs starting at or after this time"
    )

    def as_sql_filter(self):
        if self.before_ and self.after_:
            return orm.TaskRun.start_time.between(self.after_, self.before_)
        elif self.before_:
            return orm.TaskRun.start_time <= self.before_
        elif self.after_:
            return orm.TaskRun.start_time >= self.after_


class TaskRunFilter(PrefectFilterBaseModel):
    """Filter task runs. Only task runs matching all criteria will be returned"""

    ids: Optional[TaskRunFilterIds]
    tags: Optional[TaskRunFilterTags]
    state_types: Optional[TaskRunFilterStateTypes]
    start_time: Optional[TaskRunFilterStartTime]

    def as_sql_filter(self) -> List:
        filters = []

        if self.ids is not None:
            filters.append(self.ids.as_sql_filter())
        if self.tags is not None:
            filters.append(self.tags.as_sql_filter())
        if self.state_types is not None:
            filters.append(self.state_types.as_sql_filter())
        if self.start_time is not None:
            filters.append(self.start_time.as_sql_filter())

        return sa.and_(*filters) if filters else sa.and_(True)
