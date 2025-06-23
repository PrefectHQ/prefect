"""
Schemas that define Prefect REST API filtering operations.

Each filter schema includes logic for transforming itself into a SQL `where` clause.
"""

from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING, ClassVar, Optional
from uuid import UUID

from pydantic import ConfigDict, Field
from sqlalchemy.sql.functions import coalesce

import prefect.server.schemas as schemas
from prefect.server.utilities.database import db_injector
from prefect.server.utilities.schemas.bases import PrefectBaseModel
from prefect.types import DateTime
from prefect.utilities.collections import AutoEnum
from prefect.utilities.importtools import lazy_import

if TYPE_CHECKING:
    import sqlalchemy as sa
    from sqlalchemy.dialects import postgresql

    from prefect.server.database import PrefectDBInterface
else:
    sa = lazy_import("sqlalchemy")
    postgresql = lazy_import("sqlalchemy.dialects.postgresql")

# TODO: Consider moving the `as_sql_filter` functions out of here since they are a
#       database model level function and do not properly separate concerns when
#       present in the schemas module


def _as_array(elems: Sequence[str]) -> sa.ColumnElement[Sequence[str]]:
    return sa.cast(postgresql.array(elems), type_=postgresql.ARRAY(sa.String()))


class Operator(AutoEnum):
    """Operators for combining filter criteria."""

    and_ = AutoEnum.auto()
    or_ = AutoEnum.auto()


class PrefectFilterBaseModel(PrefectBaseModel):
    """Base model for Prefect filters"""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    @db_injector
    def as_sql_filter(self, db: "PrefectDBInterface") -> sa.ColumnElement[bool]:
        """Generate SQL filter from provided filter parameters. If no filters parameters are available, return a TRUE filter."""
        filters = self._get_filter_list(db)
        if not filters:
            return sa.true()
        return sa.and_(*filters)

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        """Return a list of boolean filter statements based on filter parameters"""
        raise NotImplementedError("_get_filter_list must be implemented")


class PrefectOperatorFilterBaseModel(PrefectFilterBaseModel):
    """Base model for Prefect filters that combines criteria with a user-provided operator"""

    operator: Operator = Field(
        default=Operator.and_,
        description="Operator for combining filter criteria. Defaults to 'and_'.",
    )

    @db_injector
    def as_sql_filter(self, db: "PrefectDBInterface") -> sa.ColumnElement[bool]:
        filters = self._get_filter_list(db)
        if not filters:
            return sa.true()
        return sa.and_(*filters) if self.operator == Operator.and_ else sa.or_(*filters)


class FlowFilterId(PrefectFilterBaseModel):
    """Filter by `Flow.id`."""

    any_: Optional[list[UUID]] = Field(
        default=None, description="A list of flow ids to include"
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(db.Flow.id.in_(self.any_))
        return filters


class FlowFilterDeployment(PrefectOperatorFilterBaseModel):
    """Filter by flows by deployment"""

    is_null_: Optional[bool] = Field(
        default=None,
        description="If true, only include flows without deployments",
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []

        if self.is_null_ is not None:
            deployments_subquery = (
                sa.select(db.Deployment.flow_id).distinct().subquery()
            )

            if self.is_null_:
                filters.append(
                    db.Flow.id.not_in(sa.select(deployments_subquery.c.flow_id))
                )
            else:
                filters.append(
                    db.Flow.id.in_(sa.select(deployments_subquery.c.flow_id))
                )

        return filters


class FlowFilterName(PrefectFilterBaseModel):
    """Filter by `Flow.name`."""

    any_: Optional[list[str]] = Field(
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

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(db.Flow.name.in_(self.any_))
        if self.like_ is not None:
            filters.append(db.Flow.name.ilike(f"%{self.like_}%"))
        return filters


class FlowFilterTags(PrefectOperatorFilterBaseModel):
    """Filter by `Flow.tags`."""

    all_: Optional[list[str]] = Field(
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

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.all_ is not None:
            filters.append(db.Flow.tags.has_all(_as_array(self.all_)))
        if self.is_null_ is not None:
            filters.append(db.Flow.tags == [] if self.is_null_ else db.Flow.tags != [])
        return filters


class FlowFilter(PrefectOperatorFilterBaseModel):
    """Filter for flows. Only flows matching all criteria will be returned."""

    id: Optional[FlowFilterId] = Field(
        default=None, description="Filter criteria for `Flow.id`"
    )
    deployment: Optional[FlowFilterDeployment] = Field(
        default=None, description="Filter criteria for Flow deployments"
    )
    name: Optional[FlowFilterName] = Field(
        default=None, description="Filter criteria for `Flow.name`"
    )
    tags: Optional[FlowFilterTags] = Field(
        default=None, description="Filter criteria for `Flow.tags`"
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []

        if self.id is not None:
            filters.append(self.id.as_sql_filter())
        if self.deployment is not None:
            filters.append(self.deployment.as_sql_filter())
        if self.name is not None:
            filters.append(self.name.as_sql_filter())
        if self.tags is not None:
            filters.append(self.tags.as_sql_filter())

        return filters


class FlowRunFilterId(PrefectFilterBaseModel):
    """Filter by `FlowRun.id`."""

    any_: Optional[list[UUID]] = Field(
        default=None, description="A list of flow run ids to include"
    )
    not_any_: Optional[list[UUID]] = Field(
        default=None, description="A list of flow run ids to exclude"
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(db.FlowRun.id.in_(self.any_))
        if self.not_any_ is not None:
            filters.append(db.FlowRun.id.not_in(self.not_any_))
        return filters


class FlowRunFilterName(PrefectFilterBaseModel):
    """Filter by `FlowRun.name`."""

    any_: Optional[list[str]] = Field(
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

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(db.FlowRun.name.in_(self.any_))
        if self.like_ is not None:
            filters.append(db.FlowRun.name.ilike(f"%{self.like_}%"))
        return filters


class FlowRunFilterTags(PrefectOperatorFilterBaseModel):
    """Filter by `FlowRun.tags`."""

    all_: Optional[list[str]] = Field(
        default=None,
        examples=[["tag-1", "tag-2"]],
        description=(
            "A list of tags. Flow runs will be returned only if their tags are a"
            " superset of the list"
        ),
    )

    any_: Optional[list[str]] = Field(
        default=None,
        examples=[["tag-1", "tag-2"]],
        description="A list of tags to include",
    )

    is_null_: Optional[bool] = Field(
        default=None, description="If true, only include flow runs without tags"
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        def as_array(elems: Sequence[str]) -> sa.ColumnElement[Sequence[str]]:
            return sa.cast(postgresql.array(elems), type_=postgresql.ARRAY(sa.String()))

        filters: list[sa.ColumnElement[bool]] = []
        if self.all_ is not None:
            filters.append(db.FlowRun.tags.has_all(as_array(self.all_)))
        if self.any_ is not None:
            filters.append(db.FlowRun.tags.has_any(as_array(self.any_)))
        if self.is_null_ is not None:
            filters.append(
                db.FlowRun.tags == [] if self.is_null_ else db.FlowRun.tags != []
            )
        return filters


class FlowRunFilterDeploymentId(PrefectOperatorFilterBaseModel):
    """Filter by `FlowRun.deployment_id`."""

    any_: Optional[list[UUID]] = Field(
        default=None, description="A list of flow run deployment ids to include"
    )
    is_null_: Optional[bool] = Field(
        default=None,
        description="If true, only include flow runs without deployment ids",
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(db.FlowRun.deployment_id.in_(self.any_))
        if self.is_null_ is not None:
            filters.append(
                db.FlowRun.deployment_id.is_(None)
                if self.is_null_
                else db.FlowRun.deployment_id.is_not(None)
            )
        return filters


class FlowRunFilterWorkQueueName(PrefectOperatorFilterBaseModel):
    """Filter by `FlowRun.work_queue_name`."""

    any_: Optional[list[str]] = Field(
        default=None,
        description="A list of work queue names to include",
        examples=[["work_queue_1", "work_queue_2"]],
    )
    is_null_: Optional[bool] = Field(
        default=None,
        description="If true, only include flow runs without work queue names",
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(db.FlowRun.work_queue_name.in_(self.any_))
        if self.is_null_ is not None:
            filters.append(
                db.FlowRun.work_queue_name.is_(None)
                if self.is_null_
                else db.FlowRun.work_queue_name.is_not(None)
            )
        return filters


class FlowRunFilterStateType(PrefectFilterBaseModel):
    """Filter by `FlowRun.state_type`."""

    any_: Optional[list[schemas.states.StateType]] = Field(
        default=None, description="A list of flow run state types to include"
    )
    not_any_: Optional[list[schemas.states.StateType]] = Field(
        default=None, description="A list of flow run state types to exclude"
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(db.FlowRun.state_type.in_(self.any_))
        if self.not_any_ is not None:
            filters.append(db.FlowRun.state_type.not_in(self.not_any_))
        return filters


class FlowRunFilterStateName(PrefectFilterBaseModel):
    """Filter by `FlowRun.state_name`."""

    any_: Optional[list[str]] = Field(
        default=None, description="A list of flow run state names to include"
    )
    not_any_: Optional[list[str]] = Field(
        default=None, description="A list of flow run state names to exclude"
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(db.FlowRun.state_name.in_(self.any_))
        if self.not_any_ is not None:
            filters.append(db.FlowRun.state_name.not_in(self.not_any_))
        return filters


class FlowRunFilterState(PrefectOperatorFilterBaseModel):
    """Filter by `FlowRun.state_type` and `FlowRun.state_name`."""

    type: Optional[FlowRunFilterStateType] = Field(
        default=None, description="Filter criteria for `FlowRun.state_type`"
    )
    name: Optional[FlowRunFilterStateName] = Field(
        default=None, description="Filter criteria for `FlowRun.state_name`"
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.type is not None:
            filter = self.type.as_sql_filter()
            if isinstance(filter, sa.BinaryExpression):
                filters.append(filter)
        if self.name is not None:
            filter = self.name.as_sql_filter()
            if isinstance(filter, sa.BinaryExpression):
                filters.append(filter)
        return filters


class FlowRunFilterFlowVersion(PrefectFilterBaseModel):
    """Filter by `FlowRun.flow_version`."""

    any_: Optional[list[str]] = Field(
        default=None, description="A list of flow run flow_versions to include"
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(db.FlowRun.flow_version.in_(self.any_))
        return filters


class FlowRunFilterStartTime(PrefectFilterBaseModel):
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

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.before_ is not None:
            filters.append(
                coalesce(db.FlowRun.start_time, db.FlowRun.expected_start_time)
                <= self.before_
            )
        if self.after_ is not None:
            filters.append(
                coalesce(db.FlowRun.start_time, db.FlowRun.expected_start_time)
                >= self.after_
            )
        if self.is_null_ is not None:
            filters.append(
                db.FlowRun.start_time.is_(None)
                if self.is_null_
                else db.FlowRun.start_time.is_not(None)
            )
        return filters


class FlowRunFilterEndTime(PrefectFilterBaseModel):
    """Filter by `FlowRun.end_time`."""

    before_: Optional[DateTime] = Field(
        default=None,
        description="Only include flow runs ending at or before this time",
    )
    after_: Optional[DateTime] = Field(
        default=None,
        description="Only include flow runs ending at or after this time",
    )
    is_null_: Optional[bool] = Field(
        default=None, description="If true, only return flow runs without an end time"
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.before_ is not None:
            filters.append(db.FlowRun.end_time <= self.before_)
        if self.after_ is not None:
            filters.append(db.FlowRun.end_time >= self.after_)
        if self.is_null_ is not None:
            filters.append(
                db.FlowRun.end_time.is_(None)
                if self.is_null_
                else db.FlowRun.end_time.is_not(None)
            )
        return filters


class FlowRunFilterExpectedStartTime(PrefectFilterBaseModel):
    """Filter by `FlowRun.expected_start_time`."""

    before_: Optional[DateTime] = Field(
        default=None,
        description="Only include flow runs scheduled to start at or before this time",
    )
    after_: Optional[DateTime] = Field(
        default=None,
        description="Only include flow runs scheduled to start at or after this time",
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.before_ is not None:
            filters.append(db.FlowRun.expected_start_time <= self.before_)
        if self.after_ is not None:
            filters.append(db.FlowRun.expected_start_time >= self.after_)
        return filters


class FlowRunFilterNextScheduledStartTime(PrefectFilterBaseModel):
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

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.before_ is not None:
            filters.append(db.FlowRun.next_scheduled_start_time <= self.before_)
        if self.after_ is not None:
            filters.append(db.FlowRun.next_scheduled_start_time >= self.after_)
        return filters


class FlowRunFilterParentFlowRunId(PrefectOperatorFilterBaseModel):
    """Filter for subflows of a given flow run"""

    any_: Optional[list[UUID]] = Field(
        default=None, description="A list of parent flow run ids to include"
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(
                db.FlowRun.id.in_(
                    sa.select(db.FlowRun.id)
                    .join(
                        db.TaskRun,
                        sa.and_(
                            db.TaskRun.id == db.FlowRun.parent_task_run_id,
                        ),
                    )
                    .where(db.TaskRun.flow_run_id.in_(self.any_))
                )
            )
        return filters


class FlowRunFilterParentTaskRunId(PrefectOperatorFilterBaseModel):
    """Filter by `FlowRun.parent_task_run_id`."""

    any_: Optional[list[UUID]] = Field(
        default=None, description="A list of flow run parent_task_run_ids to include"
    )
    is_null_: Optional[bool] = Field(
        default=None,
        description="If true, only include flow runs without parent_task_run_id",
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(db.FlowRun.parent_task_run_id.in_(self.any_))
        if self.is_null_ is not None:
            filters.append(
                db.FlowRun.parent_task_run_id.is_(None)
                if self.is_null_
                else db.FlowRun.parent_task_run_id.is_not(None)
            )
        return filters


class FlowRunFilterIdempotencyKey(PrefectFilterBaseModel):
    """Filter by FlowRun.idempotency_key."""

    any_: Optional[list[str]] = Field(
        default=None, description="A list of flow run idempotency keys to include"
    )
    not_any_: Optional[list[str]] = Field(
        default=None, description="A list of flow run idempotency keys to exclude"
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(db.FlowRun.idempotency_key.in_(self.any_))
        if self.not_any_ is not None:
            filters.append(db.FlowRun.idempotency_key.not_in(self.not_any_))
        return filters


class FlowRunFilter(PrefectOperatorFilterBaseModel):
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
    end_time: Optional[FlowRunFilterEndTime] = Field(
        default=None, description="Filter criteria for `FlowRun.end_time`"
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

    def only_filters_on_id(self) -> bool:
        return bool(
            self.id is not None
            and (self.id.any_ and not self.id.not_any_)
            and self.name is None
            and self.tags is None
            and self.deployment_id is None
            and self.work_queue_name is None
            and self.state is None
            and self.flow_version is None
            and self.start_time is None
            and self.end_time is None
            and self.expected_start_time is None
            and self.next_scheduled_start_time is None
            and self.parent_flow_run_id is None
            and self.parent_task_run_id is None
            and self.idempotency_key is None
        )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []

        if self.id is not None:
            filters.append(self.id.as_sql_filter())
        if self.name is not None:
            filters.append(self.name.as_sql_filter())
        if self.tags is not None:
            filters.append(self.tags.as_sql_filter())
        if self.deployment_id is not None:
            filters.append(self.deployment_id.as_sql_filter())
        if self.work_queue_name is not None:
            filters.append(self.work_queue_name.as_sql_filter())
        if self.flow_version is not None:
            filters.append(self.flow_version.as_sql_filter())
        if self.state is not None:
            filters.append(self.state.as_sql_filter())
        if self.start_time is not None:
            filters.append(self.start_time.as_sql_filter())
        if self.end_time is not None:
            filters.append(self.end_time.as_sql_filter())
        if self.expected_start_time is not None:
            filters.append(self.expected_start_time.as_sql_filter())
        if self.next_scheduled_start_time is not None:
            filters.append(self.next_scheduled_start_time.as_sql_filter())
        if self.parent_flow_run_id is not None:
            filters.append(self.parent_flow_run_id.as_sql_filter())
        if self.parent_task_run_id is not None:
            filters.append(self.parent_task_run_id.as_sql_filter())
        if self.idempotency_key is not None:
            filters.append(self.idempotency_key.as_sql_filter())

        return filters


class TaskRunFilterFlowRunId(PrefectOperatorFilterBaseModel):
    """Filter by `TaskRun.flow_run_id`."""

    any_: Optional[list[UUID]] = Field(
        default=None, description="A list of task run flow run ids to include"
    )

    is_null_: Optional[bool] = Field(
        default=False, description="Filter for task runs with None as their flow run id"
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.is_null_ is True:
            filters.append(db.TaskRun.flow_run_id.is_(None))
        elif self.is_null_ is False and self.any_ is None:
            filters.append(db.TaskRun.flow_run_id.is_not(None))
        else:
            if self.any_ is not None:
                filters.append(db.TaskRun.flow_run_id.in_(self.any_))
        return filters


class TaskRunFilterId(PrefectFilterBaseModel):
    """Filter by `TaskRun.id`."""

    any_: Optional[list[UUID]] = Field(
        default=None, description="A list of task run ids to include"
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(db.TaskRun.id.in_(self.any_))
        return filters


class TaskRunFilterName(PrefectFilterBaseModel):
    """Filter by `TaskRun.name`."""

    any_: Optional[list[str]] = Field(
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

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(db.TaskRun.name.in_(self.any_))
        if self.like_ is not None:
            filters.append(db.TaskRun.name.ilike(f"%{self.like_}%"))
        return filters


class TaskRunFilterTags(PrefectOperatorFilterBaseModel):
    """Filter by `TaskRun.tags`."""

    all_: Optional[list[str]] = Field(
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

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnElement[bool]] = []
        if self.all_ is not None:
            filters.append(db.TaskRun.tags.has_all(_as_array(self.all_)))
        if self.is_null_ is not None:
            filters.append(
                db.TaskRun.tags == [] if self.is_null_ else db.TaskRun.tags != []
            )
        return filters


class TaskRunFilterStateType(PrefectFilterBaseModel):
    """Filter by `TaskRun.state_type`."""

    any_: Optional[list[schemas.states.StateType]] = Field(
        default=None, description="A list of task run state types to include"
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(db.TaskRun.state_type.in_(self.any_))
        return filters


class TaskRunFilterStateName(PrefectFilterBaseModel):
    """Filter by `TaskRun.state_name`."""

    any_: Optional[list[str]] = Field(
        default=None, description="A list of task run state names to include"
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(db.TaskRun.state_name.in_(self.any_))
        return filters


class TaskRunFilterState(PrefectOperatorFilterBaseModel):
    """Filter by `TaskRun.type` and `TaskRun.name`."""

    type: Optional[TaskRunFilterStateType] = Field(
        default=None, description="Filter criteria for `TaskRun.state_type`"
    )
    name: Optional[TaskRunFilterStateName] = Field(
        default=None, description="Filter criteria for `TaskRun.state_name`"
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.type is not None:
            filter = self.type.as_sql_filter()
            if isinstance(filter, sa.BinaryExpression):
                filters.append(filter)
        if self.name is not None:
            filter = self.name.as_sql_filter()
            if isinstance(filter, sa.BinaryExpression):
                filters.append(filter)
        return filters


class TaskRunFilterSubFlowRuns(PrefectFilterBaseModel):
    """Filter by `TaskRun.subflow_run`."""

    exists_: Optional[bool] = Field(
        default=None,
        description=(
            "If true, only include task runs that are subflow run parents; if false,"
            " exclude parent task runs"
        ),
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.exists_ is True:
            filters.append(db.TaskRun.subflow_run.has())
        elif self.exists_ is False:
            filters.append(sa.not_(db.TaskRun.subflow_run.has()))
        return filters


class TaskRunFilterStartTime(PrefectFilterBaseModel):
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

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.before_ is not None:
            filters.append(db.TaskRun.start_time <= self.before_)
        if self.after_ is not None:
            filters.append(db.TaskRun.start_time >= self.after_)
        if self.is_null_ is not None:
            filters.append(
                db.TaskRun.start_time.is_(None)
                if self.is_null_
                else db.TaskRun.start_time.is_not(None)
            )
        return filters


class TaskRunFilterExpectedStartTime(PrefectFilterBaseModel):
    """Filter by `TaskRun.expected_start_time`."""

    before_: Optional[DateTime] = Field(
        default=None,
        description="Only include task runs expected to start at or before this time",
    )
    after_: Optional[DateTime] = Field(
        default=None,
        description="Only include task runs expected to start at or after this time",
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.before_ is not None:
            filters.append(db.TaskRun.expected_start_time <= self.before_)
        if self.after_ is not None:
            filters.append(db.TaskRun.expected_start_time >= self.after_)
        return filters


class TaskRunFilter(PrefectOperatorFilterBaseModel):
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
    expected_start_time: Optional[TaskRunFilterExpectedStartTime] = Field(
        default=None, description="Filter criteria for `TaskRun.expected_start_time`"
    )
    subflow_runs: Optional[TaskRunFilterSubFlowRuns] = Field(
        default=None, description="Filter criteria for `TaskRun.subflow_run`"
    )
    flow_run_id: Optional[TaskRunFilterFlowRunId] = Field(
        default=None, description="Filter criteria for `TaskRun.flow_run_id`"
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []

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
        if self.expected_start_time is not None:
            filters.append(self.expected_start_time.as_sql_filter())
        if self.subflow_runs is not None:
            filters.append(self.subflow_runs.as_sql_filter())
        if self.flow_run_id is not None:
            filters.append(self.flow_run_id.as_sql_filter())

        return filters


class DeploymentFilterId(PrefectFilterBaseModel):
    """Filter by `Deployment.id`."""

    any_: Optional[list[UUID]] = Field(
        default=None, description="A list of deployment ids to include"
    )
    not_any_: Optional[list[UUID]] = Field(
        default=None, description="A list of deployment ids to exclude"
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(db.Deployment.id.in_(self.any_))
        if self.not_any_ is not None:
            filters.append(db.Deployment.id.not_in(self.not_any_))
        return filters


class DeploymentFilterName(PrefectFilterBaseModel):
    """Filter by `Deployment.name`."""

    any_: Optional[list[str]] = Field(
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

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(db.Deployment.name.in_(self.any_))
        if self.like_ is not None:
            filters.append(db.Deployment.name.ilike(f"%{self.like_}%"))
        return filters


class DeploymentOrFlowNameFilter(PrefectFilterBaseModel):
    """Filter by `Deployment.name` or `Flow.name` with a single input string for ilike filtering."""

    like_: Optional[str] = Field(
        default=None,
        description=(
            "A case-insensitive partial match on deployment or flow names. For example, "
            "passing 'example' might match deployments or flows with 'example' in their names."
        ),
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.like_ is not None:
            deployment_name_filter = db.Deployment.name.ilike(f"%{self.like_}%")

            flow_name_filter = db.Deployment.flow.has(
                db.Flow.name.ilike(f"%{self.like_}%")
            )
            filters.append(sa.or_(deployment_name_filter, flow_name_filter))
        return filters


class DeploymentFilterPaused(PrefectFilterBaseModel):
    """Filter by `Deployment.paused`."""

    eq_: Optional[bool] = Field(
        default=None,
        description="Only returns where deployment is/is not paused",
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.eq_ is not None:
            filters.append(db.Deployment.paused.is_(self.eq_))
        return filters


class DeploymentFilterWorkQueueName(PrefectFilterBaseModel):
    """Filter by `Deployment.work_queue_name`."""

    any_: Optional[list[str]] = Field(
        default=None,
        description="A list of work queue names to include",
        examples=[["work_queue_1", "work_queue_2"]],
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(db.Deployment.work_queue_name.in_(self.any_))
        return filters


class DeploymentFilterConcurrencyLimit(PrefectFilterBaseModel):
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

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> list[sa.ColumnElement[bool]]:
        # This used to filter on an `int` column that was moved to a `ForeignKey` relationship
        # This filter is now deprecated rather than support filtering on the new relationship
        return []


class DeploymentFilterTags(PrefectOperatorFilterBaseModel):
    """Filter by `Deployment.tags`."""

    all_: Optional[list[str]] = Field(
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

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        from prefect.server.database import orm_models

        filters: list[sa.ColumnElement[bool]] = []
        if self.all_ is not None:
            filters.append(orm_models.Deployment.tags.has_all(_as_array(self.all_)))
        if self.any_ is not None:
            filters.append(orm_models.Deployment.tags.has_any(_as_array(self.any_)))
        if self.is_null_ is not None:
            filters.append(
                db.Deployment.tags == [] if self.is_null_ else db.Deployment.tags != []
            )
        return filters


class DeploymentFilter(PrefectOperatorFilterBaseModel):
    """Filter for deployments. Only deployments matching all criteria will be returned."""

    id: Optional[DeploymentFilterId] = Field(
        default=None, description="Filter criteria for `Deployment.id`"
    )
    name: Optional[DeploymentFilterName] = Field(
        default=None, description="Filter criteria for `Deployment.name`"
    )
    flow_or_deployment_name: Optional[DeploymentOrFlowNameFilter] = Field(
        default=None, description="Filter criteria for `Deployment.name` or `Flow.name`"
    )
    paused: Optional[DeploymentFilterPaused] = Field(
        default=None, description="Filter criteria for `Deployment.paused`"
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

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.id is not None:
            filters.append(self.id.as_sql_filter())
        if self.name is not None:
            filters.append(self.name.as_sql_filter())
        if self.flow_or_deployment_name is not None:
            filters.append(self.flow_or_deployment_name.as_sql_filter())
        if self.paused is not None:
            filters.append(self.paused.as_sql_filter())
        if self.tags is not None:
            filters.append(self.tags.as_sql_filter())
        if self.work_queue_name is not None:
            filters.append(self.work_queue_name.as_sql_filter())

        return filters


class DeploymentScheduleFilterActive(PrefectFilterBaseModel):
    """Filter by `DeploymentSchedule.active`."""

    eq_: Optional[bool] = Field(
        default=None,
        description="Only returns where deployment schedule is/is not active",
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.eq_ is not None:
            filters.append(db.DeploymentSchedule.active.is_(self.eq_))
        return filters


class DeploymentScheduleFilter(PrefectOperatorFilterBaseModel):
    """Filter for deployments. Only deployments matching all criteria will be returned."""

    active: Optional[DeploymentScheduleFilterActive] = Field(
        default=None, description="Filter criteria for `DeploymentSchedule.active`"
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []

        if self.active is not None:
            filters.append(self.active.as_sql_filter())

        return filters


class LogFilterName(PrefectFilterBaseModel):
    """Filter by `Log.name`."""

    any_: Optional[list[str]] = Field(
        default=None,
        description="A list of log names to include",
        examples=[["prefect.logger.flow_runs", "prefect.logger.task_runs"]],
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(db.Log.name.in_(self.any_))
        return filters


class LogFilterLevel(PrefectFilterBaseModel):
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

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.ge_ is not None:
            filters.append(db.Log.level >= self.ge_)
        if self.le_ is not None:
            filters.append(db.Log.level <= self.le_)
        return filters


class LogFilterTimestamp(PrefectFilterBaseModel):
    """Filter by `Log.timestamp`."""

    before_: Optional[DateTime] = Field(
        default=None,
        description="Only include logs with a timestamp at or before this time",
    )
    after_: Optional[DateTime] = Field(
        default=None,
        description="Only include logs with a timestamp at or after this time",
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.before_ is not None:
            filters.append(db.Log.timestamp <= self.before_)
        if self.after_ is not None:
            filters.append(db.Log.timestamp >= self.after_)
        return filters


class LogFilterFlowRunId(PrefectFilterBaseModel):
    """Filter by `Log.flow_run_id`."""

    any_: Optional[list[UUID]] = Field(
        default=None, description="A list of flow run IDs to include"
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(db.Log.flow_run_id.in_(self.any_))
        return filters


class LogFilterTaskRunId(PrefectFilterBaseModel):
    """Filter by `Log.task_run_id`."""

    any_: Optional[list[UUID]] = Field(
        default=None, description="A list of task run IDs to include"
    )

    is_null_: Optional[bool] = Field(
        default=None,
        description="If true, only include logs without a task run id",
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(db.Log.task_run_id.in_(self.any_))
        if self.is_null_ is not None:
            filters.append(
                db.Log.task_run_id.is_(None)
                if self.is_null_
                else db.Log.task_run_id.is_not(None)
            )
        return filters


class LogFilter(PrefectOperatorFilterBaseModel):
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

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []

        if self.level is not None:
            filters.append(self.level.as_sql_filter())
        if self.timestamp is not None:
            filters.append(self.timestamp.as_sql_filter())
        if self.flow_run_id is not None:
            filters.append(self.flow_run_id.as_sql_filter())
        if self.task_run_id is not None:
            filters.append(self.task_run_id.as_sql_filter())

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

    like_: Optional[str] = Field(
        default=None,
        description=(
            "A case-insensitive partial match. For example, "
            " passing 'marvin' will match "
            "'marvin', 'sad-Marvin', and 'marvin-robot'."
        ),
        examples=["marvin"],
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.like_ is not None:
            filters.append(db.BlockType.name.ilike(f"%{self.like_}%"))
        return filters


class BlockTypeFilterSlug(PrefectFilterBaseModel):
    """Filter by `BlockType.slug`"""

    any_: Optional[list[str]] = Field(
        default=None, description="A list of slugs to match"
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(db.BlockType.slug.in_(self.any_))

        return filters


class BlockTypeFilter(PrefectFilterBaseModel):
    """Filter BlockTypes"""

    name: Optional[BlockTypeFilterName] = Field(
        default=None, description="Filter criteria for `BlockType.name`"
    )

    slug: Optional[BlockTypeFilterSlug] = Field(
        default=None, description="Filter criteria for `BlockType.slug`"
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []

        if self.name is not None:
            filters.append(self.name.as_sql_filter())
        if self.slug is not None:
            filters.append(self.slug.as_sql_filter())

        return filters


class BlockSchemaFilterBlockTypeId(PrefectFilterBaseModel):
    """Filter by `BlockSchema.block_type_id`."""

    any_: Optional[list[UUID]] = Field(
        default=None, description="A list of block type ids to include"
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(db.BlockSchema.block_type_id.in_(self.any_))
        return filters


class BlockSchemaFilterId(PrefectFilterBaseModel):
    """Filter by BlockSchema.id"""

    any_: Optional[list[UUID]] = Field(
        default=None, description="A list of IDs to include"
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(db.BlockSchema.id.in_(self.any_))
        return filters


class BlockSchemaFilterCapabilities(PrefectFilterBaseModel):
    """Filter by `BlockSchema.capabilities`"""

    all_: Optional[list[str]] = Field(
        default=None,
        examples=[["write-storage", "read-storage"]],
        description=(
            "A list of block capabilities. Block entities will be returned only if an"
            " associated block schema has a superset of the defined capabilities."
        ),
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnElement[bool]] = []
        if self.all_ is not None:
            filters.append(db.BlockSchema.capabilities.has_all(_as_array(self.all_)))
        return filters


class BlockSchemaFilterVersion(PrefectFilterBaseModel):
    """Filter by `BlockSchema.capabilities`"""

    any_: Optional[list[str]] = Field(
        default=None,
        examples=[["2.0.0", "2.1.0"]],
        description="A list of block schema versions.",
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnElement[bool]] = []
        if self.any_ is not None:
            filters.append(db.BlockSchema.version.in_(self.any_))
        return filters


class BlockSchemaFilter(PrefectOperatorFilterBaseModel):
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

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []

        if self.block_type_id is not None:
            filters.append(self.block_type_id.as_sql_filter())
        if self.block_capabilities is not None:
            filters.append(self.block_capabilities.as_sql_filter())
        if self.id is not None:
            filters.append(self.id.as_sql_filter())
        if self.version is not None:
            filters.append(self.version.as_sql_filter())

        return filters


class BlockDocumentFilterIsAnonymous(PrefectFilterBaseModel):
    """Filter by `BlockDocument.is_anonymous`."""

    eq_: Optional[bool] = Field(
        default=None,
        description=(
            "Filter block documents for only those that are or are not anonymous."
        ),
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.eq_ is not None:
            filters.append(db.BlockDocument.is_anonymous.is_(self.eq_))
        return filters


class BlockDocumentFilterBlockTypeId(PrefectFilterBaseModel):
    """Filter by `BlockDocument.block_type_id`."""

    any_: Optional[list[UUID]] = Field(
        default=None, description="A list of block type ids to include"
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(db.BlockDocument.block_type_id.in_(self.any_))
        return filters


class BlockDocumentFilterId(PrefectFilterBaseModel):
    """Filter by `BlockDocument.id`."""

    any_: Optional[list[UUID]] = Field(
        default=None, description="A list of block ids to include"
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(db.BlockDocument.id.in_(self.any_))
        return filters


class BlockDocumentFilterName(PrefectFilterBaseModel):
    """Filter by `BlockDocument.name`."""

    any_: Optional[list[str]] = Field(
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

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(db.BlockDocument.name.in_(self.any_))
        if self.like_ is not None:
            filters.append(db.BlockDocument.name.ilike(f"%{self.like_}%"))
        return filters


class BlockDocumentFilter(PrefectOperatorFilterBaseModel):
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

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.id is not None:
            filters.append(self.id.as_sql_filter())
        if self.is_anonymous is not None:
            filters.append(self.is_anonymous.as_sql_filter())
        if self.block_type_id is not None:
            filters.append(self.block_type_id.as_sql_filter())
        if self.name is not None:
            filters.append(self.name.as_sql_filter())
        return filters


class WorkQueueFilterId(PrefectFilterBaseModel):
    """Filter by `WorkQueue.id`."""

    any_: Optional[list[UUID]] = Field(
        default=None,
        description="A list of work queue ids to include",
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(db.WorkQueue.id.in_(self.any_))
        return filters


class WorkQueueFilterName(PrefectFilterBaseModel):
    """Filter by `WorkQueue.name`."""

    any_: Optional[list[str]] = Field(
        default=None,
        description="A list of work queue names to include",
        examples=[["wq-1", "wq-2"]],
    )

    startswith_: Optional[list[str]] = Field(
        default=None,
        description=(
            "A list of case-insensitive starts-with matches. For example, "
            " passing 'marvin' will match "
            "'marvin', and 'Marvin-robot', but not 'sad-marvin'."
        ),
        examples=[["marvin", "Marvin-robot"]],
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(db.WorkQueue.name.in_(self.any_))
        if self.startswith_ is not None:
            filters.append(
                sa.or_(
                    *[db.WorkQueue.name.ilike(f"{item}%") for item in self.startswith_]
                )
            )
        return filters


class WorkQueueFilter(PrefectOperatorFilterBaseModel):
    """Filter work queues. Only work queues matching all criteria will be
    returned"""

    id: Optional[WorkQueueFilterId] = Field(
        default=None, description="Filter criteria for `WorkQueue.id`"
    )

    name: Optional[WorkQueueFilterName] = Field(
        default=None, description="Filter criteria for `WorkQueue.name`"
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []

        if self.id is not None:
            filters.append(self.id.as_sql_filter())
        if self.name is not None:
            filters.append(self.name.as_sql_filter())

        return filters


class WorkPoolFilterId(PrefectFilterBaseModel):
    """Filter by `WorkPool.id`."""

    any_: Optional[list[UUID]] = Field(
        default=None, description="A list of work pool ids to include"
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(db.WorkPool.id.in_(self.any_))
        return filters


class WorkPoolFilterName(PrefectFilterBaseModel):
    """Filter by `WorkPool.name`."""

    any_: Optional[list[str]] = Field(
        default=None, description="A list of work pool names to include"
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(db.WorkPool.name.in_(self.any_))
        return filters


class WorkPoolFilterType(PrefectFilterBaseModel):
    """Filter by `WorkPool.type`."""

    any_: Optional[list[str]] = Field(
        default=None, description="A list of work pool types to include"
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(db.WorkPool.type.in_(self.any_))
        return filters


class WorkPoolFilter(PrefectOperatorFilterBaseModel):
    """Filter work pools. Only work pools matching all criteria will be returned"""

    id: Optional[WorkPoolFilterId] = Field(
        default=None, description="Filter criteria for `WorkPool.id`"
    )
    name: Optional[WorkPoolFilterName] = Field(
        default=None, description="Filter criteria for `WorkPool.name`"
    )
    type: Optional[WorkPoolFilterType] = Field(
        default=None, description="Filter criteria for `WorkPool.type`"
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []

        if self.id is not None:
            filters.append(self.id.as_sql_filter())
        if self.name is not None:
            filters.append(self.name.as_sql_filter())
        if self.type is not None:
            filters.append(self.type.as_sql_filter())

        return filters


class WorkerFilterWorkPoolId(PrefectFilterBaseModel):
    """Filter by `Worker.worker_config_id`."""

    any_: Optional[list[UUID]] = Field(
        default=None, description="A list of work pool ids to include"
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(db.Worker.work_pool_id.in_(self.any_))
        return filters


class WorkerFilterStatus(PrefectFilterBaseModel):
    """Filter by `Worker.status`."""

    any_: Optional[list[schemas.statuses.WorkerStatus]] = Field(
        default=None, description="A list of worker statuses to include"
    )
    not_any_: Optional[list[schemas.statuses.WorkerStatus]] = Field(
        default=None, description="A list of worker statuses to exclude"
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(db.Worker.status.in_(self.any_))
        if self.not_any_ is not None:
            filters.append(db.Worker.status.notin_(self.not_any_))
        return filters


class WorkerFilterLastHeartbeatTime(PrefectFilterBaseModel):
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

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.before_ is not None:
            filters.append(db.Worker.last_heartbeat_time <= self.before_)
        if self.after_ is not None:
            filters.append(db.Worker.last_heartbeat_time >= self.after_)
        return filters


class WorkerFilter(PrefectOperatorFilterBaseModel):
    """Filter by `Worker.last_heartbeat_time`."""

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

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []

        if self.last_heartbeat_time is not None:
            filters.append(self.last_heartbeat_time.as_sql_filter())

        if self.status is not None:
            filters.append(self.status.as_sql_filter())

        return filters


class ArtifactFilterId(PrefectFilterBaseModel):
    """Filter by `Artifact.id`."""

    any_: Optional[list[UUID]] = Field(
        default=None, description="A list of artifact ids to include"
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(db.Artifact.id.in_(self.any_))
        return filters


class ArtifactFilterKey(PrefectFilterBaseModel):
    """Filter by `Artifact.key`."""

    any_: Optional[list[str]] = Field(
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

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(db.Artifact.key.in_(self.any_))
        if self.like_ is not None:
            filters.append(db.Artifact.key.ilike(f"%{self.like_}%"))
        if self.exists_ is not None:
            filters.append(
                db.Artifact.key.isnot(None)
                if self.exists_
                else db.Artifact.key.is_(None)
            )
        return filters


class ArtifactFilterFlowRunId(PrefectFilterBaseModel):
    """Filter by `Artifact.flow_run_id`."""

    any_: Optional[list[UUID]] = Field(
        default=None, description="A list of flow run IDs to include"
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(db.Artifact.flow_run_id.in_(self.any_))
        return filters


class ArtifactFilterTaskRunId(PrefectFilterBaseModel):
    """Filter by `Artifact.task_run_id`."""

    any_: Optional[list[UUID]] = Field(
        default=None, description="A list of task run IDs to include"
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(db.Artifact.task_run_id.in_(self.any_))
        return filters


class ArtifactFilterType(PrefectFilterBaseModel):
    """Filter by `Artifact.type`."""

    any_: Optional[list[str]] = Field(
        default=None, description="A list of artifact types to include"
    )
    not_any_: Optional[list[str]] = Field(
        default=None, description="A list of artifact types to exclude"
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(db.Artifact.type.in_(self.any_))
        if self.not_any_ is not None:
            filters.append(db.Artifact.type.notin_(self.not_any_))
        return filters


class ArtifactFilter(PrefectOperatorFilterBaseModel):
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

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []

        if self.id is not None:
            filters.append(self.id.as_sql_filter())
        if self.key is not None:
            filters.append(self.key.as_sql_filter())
        if self.flow_run_id is not None:
            filters.append(self.flow_run_id.as_sql_filter())
        if self.task_run_id is not None:
            filters.append(self.task_run_id.as_sql_filter())
        if self.type is not None:
            filters.append(self.type.as_sql_filter())

        return filters


class ArtifactCollectionFilterLatestId(PrefectFilterBaseModel):
    """Filter by `ArtifactCollection.latest_id`."""

    any_: Optional[list[UUID]] = Field(
        default=None, description="A list of artifact ids to include"
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(db.ArtifactCollection.latest_id.in_(self.any_))
        return filters


class ArtifactCollectionFilterKey(PrefectFilterBaseModel):
    """Filter by `ArtifactCollection.key`."""

    any_: Optional[list[str]] = Field(
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

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(db.ArtifactCollection.key.in_(self.any_))
        if self.like_ is not None:
            filters.append(db.ArtifactCollection.key.ilike(f"%{self.like_}%"))
        if self.exists_ is not None:
            filters.append(
                db.ArtifactCollection.key.isnot(None)
                if self.exists_
                else db.ArtifactCollection.key.is_(None)
            )
        return filters


class ArtifactCollectionFilterFlowRunId(PrefectFilterBaseModel):
    """Filter by `ArtifactCollection.flow_run_id`."""

    any_: Optional[list[UUID]] = Field(
        default=None, description="A list of flow run IDs to include"
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(db.ArtifactCollection.flow_run_id.in_(self.any_))
        return filters


class ArtifactCollectionFilterTaskRunId(PrefectFilterBaseModel):
    """Filter by `ArtifactCollection.task_run_id`."""

    any_: Optional[list[UUID]] = Field(
        default=None, description="A list of task run IDs to include"
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(db.ArtifactCollection.task_run_id.in_(self.any_))
        return filters


class ArtifactCollectionFilterType(PrefectFilterBaseModel):
    """Filter by `ArtifactCollection.type`."""

    any_: Optional[list[str]] = Field(
        default=None, description="A list of artifact types to include"
    )
    not_any_: Optional[list[str]] = Field(
        default=None, description="A list of artifact types to exclude"
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(db.ArtifactCollection.type.in_(self.any_))
        if self.not_any_ is not None:
            filters.append(db.ArtifactCollection.type.notin_(self.not_any_))
        return filters


class ArtifactCollectionFilter(PrefectOperatorFilterBaseModel):
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

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []

        if self.latest_id is not None:
            filters.append(self.latest_id.as_sql_filter())
        if self.key is not None:
            filters.append(self.key.as_sql_filter())
        if self.flow_run_id is not None:
            filters.append(self.flow_run_id.as_sql_filter())
        if self.task_run_id is not None:
            filters.append(self.task_run_id.as_sql_filter())
        if self.type is not None:
            filters.append(self.type.as_sql_filter())

        return filters


class VariableFilterId(PrefectFilterBaseModel):
    """Filter by `Variable.id`."""

    any_: Optional[list[UUID]] = Field(
        default=None, description="A list of variable ids to include"
    )

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(db.Variable.id.in_(self.any_))
        return filters


class VariableFilterName(PrefectFilterBaseModel):
    """Filter by `Variable.name`."""

    any_: Optional[list[str]] = Field(
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

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []
        if self.any_ is not None:
            filters.append(db.Variable.name.in_(self.any_))
        if self.like_ is not None:
            filters.append(db.Variable.name.ilike(f"%{self.like_}%"))
        return filters


class VariableFilterTags(PrefectOperatorFilterBaseModel):
    """Filter by `Variable.tags`."""

    all_: Optional[list[str]] = Field(
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

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnElement[bool]] = []
        if self.all_ is not None:
            filters.append(db.Variable.tags.has_all(_as_array(self.all_)))
        if self.is_null_ is not None:
            filters.append(
                db.Variable.tags == [] if self.is_null_ else db.Variable.tags != []
            )
        return filters


class VariableFilter(PrefectOperatorFilterBaseModel):
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

    def _get_filter_list(
        self, db: "PrefectDBInterface"
    ) -> Iterable[sa.ColumnExpressionArgument[bool]]:
        filters: list[sa.ColumnExpressionArgument[bool]] = []

        if self.id is not None:
            filters.append(self.id.as_sql_filter())
        if self.name is not None:
            filters.append(self.name.as_sql_filter())
        if self.tags is not None:
            filters.append(self.tags.as_sql_filter())
        return filters
