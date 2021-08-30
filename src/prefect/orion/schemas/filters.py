import pendulum
import sqlalchemy as sa
import datetime
from typing import List, Dict
from uuid import UUID

from pydantic import Field

from prefect.orion.utilities.database import json_has_all_keys
from prefect.orion import schemas
from prefect.orion.utilities.schemas import PrefectBaseModel
from prefect.orion.models import orm


class FlowFilter(PrefectBaseModel):
    ids: List[UUID] = None
    names: List[str] = None
    tags: List[str] = None

    def as_sql_filter(self) -> List:
        filters = []

        if self.ids is not None:
            filters.append(orm.Flow.id.in_(self.ids))
        if self.names is not None:
            filters.append(orm.Flow.name.in_(self.names))
        if self.tags is not None:
            filters.append(json_has_all_keys(orm.Flow.tags, self.tags))

        return sa.and_(*filters)


class FlowRunFilter(PrefectBaseModel):
    ids: List[UUID] = None
    tags: List[str] = None
    states: List[schemas.states.StateType] = None
    flow_versions: List[str] = None
    before: datetime.datetime = None
    after: datetime.datetime = None
    before_relative: datetime.timedelta = None
    after_relative: datetime.timedelta = None
    parent_task_run_id: List[str] = None

    def as_sql_filter(self) -> List:
        filters = []

        if self.ids is not None:
            filters.append(orm.FlowRun.id.in_(self.ids))
        if self.tags is not None:
            filters.append(json_has_all_keys(orm.FlowRun.tags, self.tags))
        if self.flow_versions is not None:
            filters.append(orm.FlowRun.flow_version.in_(self.flow_versions))
        if self.states is not None:
            filters.append(
                orm.FlowRun.state.has(orm.FlowRunState.type.in_(self.states))
            )
        # TODO: use canonical start time instead of timestamp

        # if self.before is not None:
        #     filters.append(
        #         orm.FlowRun.state.has(orm.FlowRunState.timestamp <= self.before)
        #     )
        # if self.after is not None:
        #     filters.append(
        #         orm.FlowRun.state.has(orm.FlowRunState.timestamp >= self.after)
        #     )

        # if self.before_relative is not None:
        #     filters.append(
        #         orm.FlowRun.state.has(
        #             orm.FlowRunState.timestamp
        #             <= pendulum.now("utc") + self.before_relative
        #         )
        #     )
        # if self.after_relative is not None:
        #     filters.append(
        #         orm.FlowRun.state.has(
        #             orm.FlowRunState.timestamp
        #             >= pendulum.now("utc") + self.after_relative
        #         )
        #     )

        return sa.and_(*filters)


class TaskRunFilter(PrefectBaseModel):
    id: List[UUID] = None
    name: List[str] = None
    tags: List[str] = None
    state: List[schemas.states.StateType] = None
    before: datetime.datetime = None
    after: datetime.datetime = None
    before_relative: datetime.timedelta = None
    after_relative: datetime.timedelta = None
