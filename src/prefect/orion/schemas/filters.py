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
    id_in: List[UUID] = None
    name_in: List[str] = None
    tags_eq: List[str] = None

    def as_sql_filter(self) -> List:
        filters = []

        if self.id_in is not None:
            filters.append(orm.Flow.id.in_(self.id_in))
        if self.name_in is not None:
            filters.append(orm.Flow.name.in_(self.name_in))
        if self.tags_eq is not None:
            filters.append(json_has_all_keys(orm.Flow.tags_eq, self.tags_eq))

        return sa.and_(*filters)


class FlowRunFilter(PrefectBaseModel):
    id_in: List[UUID] = None
    tags_eq: List[str] = None
    state_in: List[schemas.states.StateType] = None
    flow_version_in: List[str] = None
    start_time_gte: datetime.datetime = None
    start_time_lte: datetime.datetime = None
    parent_task_run_id_in: List[str] = None

    def as_sql_filter(self) -> List:
        filters = []

        if self.id_in is not None:
            filters.append(orm.FlowRun.id.in_(self.id_in))
        if self.tags_eq is not None:
            filters.append(json_has_all_keys(orm.FlowRun.tags_eq, self.tags_eq))
        if self.flow_version_in is not None:
            filters.append(orm.FlowRun.flow_version.in_(self.flow_version_in))
        if self.state_in is not None:
            filters.append(
                orm.FlowRun.state.has(orm.FlowRunState.type.in_(self.state_in))
            )
        # TODO: use canonical start time instead of timestamp

        if self.start_time_lte is not None:
            filters.append(
                orm.FlowRun.state.has(orm.FlowRunState.timestamp <= self.start_time_lte)
            )
        if self.start_time_gte is not None:
            filters.append(
                orm.FlowRun.state.has(orm.FlowRunState.timestamp >= self.start_time_gte)
            )

        return sa.and_(*filters)


class TaskRunFilter(PrefectBaseModel):
    id_in: List[UUID] = None
    name_in: List[str] = None
    tags_eq: List[str] = None
    state_in: List[schemas.states.StateType] = None
    start_time_gte: datetime.datetime = None
    start_time_lte: datetime.datetime = None
