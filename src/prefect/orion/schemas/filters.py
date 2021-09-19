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


class FlowFilterIds(PrefectBaseModel):
    any_: List[UUID] = Field(None, description="A list of flow ids to include")

    def as_sql_filter(self):
        return orm.Flow.id.in_(self.any_)


class FlowFilterNames(PrefectBaseModel):
    any_: List[str] = Field(
        None,
        description="A list of flow names to include",
        example=["my-flow-1", "my-flow-2"],
    )

    def as_sql_filter(self):
        return orm.Flow.name.in_(self.any_)


class FlowFilterTags(PrefectBaseModel):
    all_: List[str] = Field(
        None,
        example=["tag-1", "tag-2"],
        description="A list of tags. Flows will be returned only if their tags are a superset of the list",
    )
    is_null_: bool = Field(
        False, description="If true, only include flows without tags"
    )

    @root_validator
    def check_all_and_is_null_are_not_both_supplied(cls, values):
        if values.get("all_") is not None and values.get("is_null_"):
            raise ValueError("Cannot provide tags all_ with is_null_ = True")
        return values

    def as_sql_filter(self):
        if self.all_ is not None:
            return json_has_all_keys(orm.Flow.tags, self.all_)
        elif self.is_null_:
            return orm.Flow.tags == []
        raise ValueError("No sql filter available. all_ and is_null_ are not set")


class FlowFilter(PrefectBaseModel):
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


class FlowRunFilterIds(PrefectBaseModel):
    any_: List[UUID] = Field(None, description="A list of flow run ids to include")

    def as_sql_filter(self):
        return orm.FlowRun.id.in_(self.any_)


class FlowRunFilterTags(PrefectBaseModel):
    all_: List[str] = Field(
        None,
        example=["tag-1", "tag-2"],
        description="A list of tags. Flow runs will be returned only if their tags are a superset of the list",
    )
    is_null_: bool = Field(
        False, description="If true, only include flow runs without tags"
    )

    @root_validator
    def check_all_and_is_null_are_not_both_supplied(cls, values):
        if values.get("all_") is not None and values.get("is_null_"):
            raise ValueError("Cannot provide tags all_ with is_null_ = True")
        return values

    def as_sql_filter(self):
        if self.all_ is not None:
            return json_has_all_keys(orm.FlowRun.tags, self.all_)
        elif self.is_null_:
            return orm.FlowRun.tags == []
        raise ValueError("No sql filter available. all_ and is_null_ are not set")


class FlowRunFilterDeploymentIds(PrefectBaseModel):
    any_: List[UUID] = Field(
        None, description="A list of flow run deployment ids to include"
    )
    is_null_: bool = Field(
        False, description="If true, only include flow runs without deployment ids"
    )

    @root_validator
    def check_any_and_is_null_are_not_both_supplied(cls, values):
        if values.get("any_") is not None and values.get("is_null_"):
            raise ValueError("Cannot provide deployment ids any_ with is_null_ = True")
        return values

    def as_sql_filter(self):
        if self.any_ is not None:
            return orm.FlowRun.deployment_id.in_(self.any_)
        elif self.is_null_:
            return orm.FlowRun.deployment_id == None


class FlowRunFilterStateTypes(PrefectBaseModel):
    any_: List[schemas.states.StateType] = Field(
        None, description="A list of flow run state types to include"
    )

    def as_sql_filter(self):
        return orm.FlowRun.state_type.in_(self.any_)


class FlowRunFilterFlowVersions(PrefectBaseModel):
    any_: List[str] = Field(
        None, description="A list of flow run deployment ids to include"
    )

    def as_sql_filter(self):
        return orm.FlowRun.flow_version.in_(self.any_)


class FlowRunFilterStartTime(PrefectBaseModel):
    before_: datetime.datetime = Field(
        None, description="Only include flow runs starting at or before this time"
    )
    after_: datetime.datetime = Field(
        None, description="Only include flow runs starting at or after this time"
    )

    @root_validator
    def test_before_and_after_are_not_mutually_exclusive(cls, values):
        if values.get("before_") is not None and values.get("after_") is not None:
            if values.get("before_") <= values.get("after_"):
                raise ValueError("Start time before_ must be greater than after_")
        return values

    def as_sql_filter(self):
        if self.before_ and self.after_:
            return orm.FlowRun.start_time.between(self.after_, self.before_)
        elif self.before_:
            return orm.FlowRun.start_time <= self.before_
        elif self.after_:
            return orm.FlowRun.start_time >= self.after_
        raise ValueError("Must specify before or after criteria for start time")


class FlowRunFilterExpectedStartTime(PrefectBaseModel):
    before_: datetime.datetime = Field(
        None,
        description="Only include flow runs scheduled to start at or before this time",
    )
    after_: datetime.datetime = Field(
        None,
        description="Only include flow runs scheduled to start at or after this time",
    )

    @root_validator
    def test_before_and_after_are_not_mutually_exclusive(cls, values):
        if values.get("before_") is not None and values.get("after_") is not None:
            if values.get("before_") <= values.get("after_"):
                raise ValueError(
                    "Expected start time before_ must be greater than after_"
                )
        return values

    def as_sql_filter(self):
        if self.before_ and self.after_:
            return orm.FlowRun.expected_start_time.between(self.after_, self.before_)
        elif self.before_:
            return orm.FlowRun.expected_start_time <= self.before_
        elif self.after_:
            return orm.FlowRun.expected_start_time >= self.after_
        raise ValueError(
            "Must specify before or after criteria for expected start time"
        )


class FlowRunFilterNextScheduledStartTime(PrefectBaseModel):
    before_: datetime.datetime = Field(
        None,
        description="Only include flow runs with a next scheduled start time or before this time",
    )
    after_: datetime.datetime = Field(
        None,
        description="Only include flow runs with a next scheduled start time at or after this time",
    )

    @root_validator
    def test_before_and_after_are_not_mutually_exclusive(cls, values):
        if values.get("before_") is not None and values.get("after_") is not None:
            if values.get("before_") <= values.get("after_"):
                raise ValueError(
                    "Next scheduled start time before_ must be greater than after_"
                )
        return values

    def as_sql_filter(self):
        if self.before_ and self.after_:
            return orm.FlowRun.next_scheduled_start_time.between(
                self.after_, self.before_
            )
        elif self.before_:
            return orm.FlowRun.next_scheduled_start_time <= self.before_
        elif self.after_:
            return orm.FlowRun.next_scheduled_start_time >= self.after_
        raise ValueError(
            "Must specify before or after criteria for next scheduled start time"
        )


class FlowRunFilterParentTaskRunIds(PrefectBaseModel):
    any_: List[UUID] = Field(
        None, description="A list of flow run parent task run ids to include"
    )
    is_null_: bool = Field(
        False, description="If true, only include flow runs without parent task run ids"
    )

    @root_validator
    def check_any_and_is_null_are_not_both_supplied(cls, values):
        if values.get("any_") is not None and values.get("is_null_"):
            raise ValueError(
                "Cannot provide parent task run ids any_ with is_null_ = True"
            )
        return values

    def as_sql_filter(self):
        if self.any_ is not None:
            return orm.FlowRun.parent_task_run_id.in_(self.any_)
        elif self.is_null_:
            return orm.FlowRun.parent_task_run_id == None


class FlowRunFilter(PrefectBaseModel):
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


class TaskRunFilterIds(PrefectBaseModel):
    any_: List[UUID] = Field(None, description="A list of task run ids to include")

    def as_sql_filter(self):
        return orm.TaskRun.id.in_(self.any_)


class TaskRunFilterTags(PrefectBaseModel):
    all_: List[str] = Field(
        None,
        example=["tag-1", "tag-2"],
        description="A list of tags. Task runs will be returned only if their tags are a superset of the list",
    )
    is_null_: bool = Field(
        False, description="If true, only include task runs without tags"
    )

    @root_validator
    def check_all_and_is_null_are_not_both_supplied(cls, values):
        if values.get("all_") is not None and values.get("is_null_"):
            raise ValueError("Cannot provide tags all_ with is_null_ = True")
        return values

    def as_sql_filter(self):
        if self.all_ is not None:
            return json_has_all_keys(orm.TaskRun.tags, self.all_)
        elif self.is_null_:
            return orm.TaskRun.tags == []
        raise ValueError("No sql filter available. all_ and is_null_ are not set")


class TaskRunFilterStateTypes(PrefectBaseModel):
    any_: List[schemas.states.StateType] = Field(
        None, description="A list of task run state types to include"
    )

    def as_sql_filter(self):
        return orm.TaskRun.state_type.in_(self.any_)


class TaskRunFilterStartTime(PrefectBaseModel):
    before_: datetime.datetime = Field(
        None, description="Only include task runs starting at or before this time"
    )
    after_: datetime.datetime = Field(
        None, description="Only include task runs starting at or after this time"
    )

    @root_validator
    def test_before_and_after_are_not_mutually_exclusive(cls, values):
        if values.get("before_") is not None and values.get("after_") is not None:
            if values.get("before_") <= values.get("after_"):
                raise ValueError("Start time before_ must be greater than after_")
        return values

    def as_sql_filter(self):
        if self.before_ and self.after_:
            return orm.TaskRun.start_time.between(self.after_, self.before_)
        elif self.before_:
            return orm.TaskRun.start_time <= self.before_
        elif self.after_:
            return orm.TaskRun.start_time >= self.after_
        raise ValueError("Must specify before or after criteria for start time")


class TaskRunFilter(PrefectBaseModel):
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
