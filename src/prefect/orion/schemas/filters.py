import datetime
from typing import List
from uuid import UUID

import sqlalchemy as sa
from pydantic import Field, conint

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


class FlowFilter(PrefectBaseModel):
    """Filter for flows. Only flows matching all criteria will be returned"""

    ids: List[UUID] = Field(None, description="A list of flow ids to include")
    names: List[str] = Field(
        None,
        example=["my-flow-1", "my-flow-2"],
        description="A list of flow names to include",
    )
    tags_all: List[str] = Field(
        None,
        example=["tag-1", "tag-2"],
        description="A list of tags. Flows will be returned only if their tags are a superset of the list",
    )

    def as_sql_filter(self) -> List:
        filters = []

        if self.ids is not None:
            filters.append(orm.Flow.id.in_(self.ids))
        if self.names is not None:
            filters.append(orm.Flow.name.in_(self.names))
        if self.tags_all is not None:
            if self.tags_all == []:
                filters.append(orm.Flow.tags == [])
            else:
                filters.append(json_has_all_keys(orm.Flow.tags, self.tags_all))

        return sa.and_(*filters) if filters else sa.and_(True)


class FlowRunFilter(PrefectBaseModel):
    """Filter flow runs. Only flow runs matching all criteria will be returned"""

    ids: List[UUID] = Field(None, description="A list of flow run ids to include")
    tags_all: List[str] = Field(
        None,
        example=["tag-1", "tag-2"],
        description="A list of tags. Flow runs will be returned only if their tags are a superset of the list",
    )
    deployment_ids: List[UUID] = Field(
        None, description="A list of deployment IDs to include"
    )
    states: List[schemas.states.StateType] = Field(
        None, description="A list of state types to include"
    )
    flow_versions: List[str] = Field(
        None, description="A list of flow versions to include"
    )
    start_time_before: datetime.datetime = None
    start_time_after: datetime.datetime = None
    parent_task_run_ids: List[UUID] = Field(
        None, description="A list of parent task run ids to include"
    )

    def as_sql_filter(self) -> List:
        filters = []

        if self.ids is not None:
            filters.append(orm.FlowRun.id.in_(self.ids))
        if self.tags_all is not None:
            if self.tags_all == []:
                filters.append(orm.FlowRun.tags == [])
            else:
                filters.append(json_has_all_keys(orm.FlowRun.tags, self.tags_all))
        if self.deployment_ids is not None:
            filters.append(orm.FlowRun.deployment_id.in_(self.deployment_ids))
        if self.flow_versions is not None:
            filters.append(orm.FlowRun.flow_version.in_(self.flow_versions))
        if self.states is not None:
            filters.append(
                orm.FlowRun.state.has(orm.FlowRunState.type.in_(self.states))
            )
        if self.parent_task_run_ids is not None:
            filters.append(orm.FlowRun.parent_task_run_id.in_(self.parent_task_run_ids))

        # TODO: use canonical start time instead of timestamp
        if self.start_time_before is not None:
            filters.append(
                orm.FlowRun.state.has(
                    orm.FlowRunState.timestamp <= self.start_time_before
                )
            )
        if self.start_time_after is not None:
            filters.append(
                orm.FlowRun.state.has(
                    orm.FlowRunState.timestamp >= self.start_time_after
                )
            )

        return sa.and_(*filters) if filters else sa.and_(True)


class TaskRunFilter(PrefectBaseModel):
    """Filter task runs. Only task runs matching all criteria will be returned"""

    ids: List[UUID] = Field(None, description="A list of task run ids to include")
    tags_all: List[str] = Field(
        None,
        example=["tag-1", "tag-2"],
        description="A list of tags. Task runs will be returned only if their tags are a superset of the list",
    )
    states: List[schemas.states.StateType] = Field(
        None, description="A list of state types to include"
    )
    start_time_before: datetime.datetime = None
    start_time_after: datetime.datetime = None

    def as_sql_filter(self) -> List:
        filters = []

        if self.ids is not None:
            filters.append(orm.TaskRun.id.in_(self.ids))
        if self.tags_all is not None:
            if self.tags_all == []:
                filters.append(orm.TaskRun.tags == [])
            else:
                filters.append(json_has_all_keys(orm.TaskRun.tags, self.tags_all))
        if self.states is not None:
            filters.append(
                orm.TaskRun.state.has(orm.TaskRunState.type.in_(self.states))
            )

        # TODO: use canonical start time instead of timestamp
        if self.start_time_before is not None:
            filters.append(
                orm.TaskRun.state.has(
                    orm.TaskRunState.timestamp <= self.start_time_before
                )
            )
        if self.start_time_after is not None:
            filters.append(
                orm.TaskRun.state.has(
                    orm.TaskRunState.timestamp >= self.start_time_after
                )
            )

        return sa.and_(*filters) if filters else sa.and_(True)
