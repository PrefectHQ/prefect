import sys
from datetime import datetime, timezone
from typing import List, Optional, cast

import pendulum
import sqlalchemy as sa
from fastapi import Depends, HTTPException, status
from pydantic import Field, model_serializer
from pydantic_extra_types.pendulum_dt import DateTime

import prefect.server.schemas as schemas
from prefect._internal.schemas.bases import PrefectBaseModel
from prefect.logging import get_logger
from prefect.server import models
from prefect.server.database.dependencies import provide_database_interface
from prefect.server.database.interface import PrefectDBInterface
from prefect.server.utilities.server import PrefectRouter

logger = get_logger("orion.api.ui.task_runs")

router = PrefectRouter(prefix="/ui/task_runs", tags=["Task Runs", "UI"])

FAILED_STATES = [schemas.states.StateType.CRASHED, schemas.states.StateType.FAILED]


class TaskRunCount(PrefectBaseModel):
    completed: int = Field(
        default=..., description="The number of completed task runs."
    )
    failed: int = Field(default=..., description="The number of failed task runs.")

    @model_serializer
    def ser_model(self) -> dict:
        return {
            "completed": int(self.completed),
            "failed": int(self.failed),
        }


def _postgres_bucket_expression(
    db: PrefectDBInterface, delta: pendulum.Duration, start_datetime: datetime
):
    # asyncpg under Python 3.7 doesn't support timezone-aware datetimes for the EXTRACT
    # function, so we will send it as a naive datetime in UTC
    if sys.version_info < (3, 8):
        start_datetime = start_datetime.astimezone(timezone.utc).replace(tzinfo=None)

    return sa.func.floor(
        (
            sa.func.extract("epoch", db.TaskRun.start_time)
            - sa.func.extract("epoch", start_datetime)
        )
        / delta.total_seconds()
    ).label("bucket")


def _sqlite_bucket_expression(
    db: PrefectDBInterface, delta: pendulum.Duration, start_datetime: datetime
):
    return sa.func.floor(
        (
            (
                sa.func.strftime("%s", db.TaskRun.start_time)
                - sa.func.strftime("%s", start_datetime)
            )
            / delta.total_seconds()
        )
    ).label("bucket")


@router.post("/dashboard/counts")
async def read_dashboard_task_run_counts(
    task_runs: schemas.filters.TaskRunFilter,
    flows: Optional[schemas.filters.FlowFilter] = None,
    flow_runs: Optional[schemas.filters.FlowRunFilter] = None,
    deployments: Optional[schemas.filters.DeploymentFilter] = None,
    work_pools: Optional[schemas.filters.WorkPoolFilter] = None,
    work_queues: Optional[schemas.filters.WorkQueueFilter] = None,
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> List[TaskRunCount]:
    if task_runs.start_time is None or task_runs.start_time.after_ is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="task_runs.start_time.after_ is required",
        )

    # We only care about task runs that are in a terminal state, all others
    # should be ignored.
    task_runs.state = schemas.filters.TaskRunFilterState(
        type=schemas.filters.TaskRunFilterStateType(
            any_=list(schemas.states.TERMINAL_STATES)
        )
    )

    bucket_count = 20
    start_time = task_runs.start_time.after_.start_of("minute")
    end_time = cast(
        DateTime,
        (
            task_runs.start_time.before_.end_of("minute")
            if task_runs.start_time.before_
            else pendulum.now("UTC").end_of("minute")
        ),
    )
    window = end_time - start_time
    delta = window.as_timedelta() / bucket_count

    async with db.session_context(begin_transaction=False) as session:
        # Gather the raw counts. The counts are divided into buckets of time
        # and each bucket contains the number of successful and failed task
        # runs.
        # SQLAlchemy doesn't play nicely with our DateTime type so we convert it
        # to a datetime object.
        start_datetime = datetime(
            start_time.year,
            start_time.month,
            start_time.day,
            start_time.hour,
            start_time.minute,
            start_time.second,
            start_time.microsecond,
            start_time.timezone,
        )
        bucket_expression = (
            _sqlite_bucket_expression(db, delta, start_datetime)
            if db.dialect.name == "sqlite"
            else _postgres_bucket_expression(db, delta, start_datetime)
        )

        raw_counts = (
            (
                await models.task_runs._apply_task_run_filters(
                    sa.select(
                        bucket_expression,
                        sa.func.min(db.TaskRun.end_time).label("oldest"),
                        sa.func.sum(
                            sa.case(
                                (
                                    db.TaskRun.state_type.in_(FAILED_STATES),
                                    1,
                                ),
                                else_=0,
                            )
                        ).label("failed_count"),
                        sa.func.sum(
                            sa.case(
                                (
                                    db.TaskRun.state_type.notin_(FAILED_STATES),
                                    1,
                                ),
                                else_=0,
                            )
                        ).label("successful_count"),
                    ),
                    flow_filter=flows,
                    flow_run_filter=flow_runs,
                    task_run_filter=task_runs,
                    deployment_filter=deployments,
                    work_pool_filter=work_pools,
                    work_queue_filter=work_queues,
                )
            )
            .group_by("bucket", db.TaskRun.start_time)
            .subquery()
        )

        # Aggregate the raw counts by bucket
        query = (
            sa.select(
                raw_counts.c.bucket.label("bucket"),
                sa.func.min(raw_counts.c.oldest).label("oldest"),
                sa.func.sum(raw_counts.c.failed_count).label("failed_count"),
                sa.func.sum(raw_counts.c.successful_count).label("successful_count"),
            )
            .select_from(raw_counts)
            .group_by(raw_counts.c.bucket)
            .order_by(sa.asc("oldest"))
        )

        result = await session.execute(query)

    # Ensure that all buckets of time are present in the result even if no
    # matching task runs occurred during the given time period.
    buckets = [TaskRunCount(completed=0, failed=0) for _ in range(bucket_count)]

    for row in result:
        index = int(row.bucket)
        buckets[index].completed = row.successful_count
        buckets[index].failed = row.failed_count

    return buckets


@router.post("/count")
async def read_task_run_counts_by_state(
    flows: Optional[schemas.filters.FlowFilter] = None,
    flow_runs: Optional[schemas.filters.FlowRunFilter] = None,
    task_runs: Optional[schemas.filters.TaskRunFilter] = None,
    deployments: Optional[schemas.filters.DeploymentFilter] = None,
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> schemas.states.CountByState:
    async with db.session_context(begin_transaction=False) as session:
        return await models.task_runs.count_task_runs_by_state(
            session=session,
            flow_filter=flows,
            flow_run_filter=flow_runs,
            task_run_filter=task_runs,
            deployment_filter=deployments,
        )
