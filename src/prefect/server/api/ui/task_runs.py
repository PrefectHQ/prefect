from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID

import sqlalchemy as sa
from fastapi import Depends, HTTPException, Path, status
from pydantic import Field, model_serializer

import prefect.server.schemas as schemas
from prefect.logging import get_logger
from prefect.server import models
from prefect.server.database import PrefectDBInterface, provide_database_interface
from prefect.server.utilities.schemas.bases import PrefectBaseModel
from prefect.server.utilities.server import PrefectRouter
from prefect.types._datetime import end_of_period, now

if TYPE_CHECKING:
    import logging

logger: "logging.Logger" = get_logger("server.api.ui.task_runs")

router: PrefectRouter = PrefectRouter(prefix="/ui/task_runs", tags=["Task Runs", "UI"])

FAILED_STATES = [schemas.states.StateType.CRASHED, schemas.states.StateType.FAILED]


class TaskRunCount(PrefectBaseModel):
    completed: int = Field(
        default=..., description="The number of completed task runs."
    )
    failed: int = Field(default=..., description="The number of failed task runs.")

    @model_serializer
    def ser_model(self) -> dict[str, int]:
        return {
            "completed": int(self.completed),
            "failed": int(self.failed),
        }


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
    start_time = task_runs.start_time.after_.replace(microsecond=0, second=0)
    end_time = (
        end_of_period(task_runs.start_time.before_, "minute")
        if task_runs.start_time.before_
        else end_of_period(now("UTC"), "minute")
    )
    window = end_time - start_time
    delta = window / bucket_count

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
            start_time.tzinfo,
        )
        bucket_expression = sa.func.floor(
            sa.func.date_diff_seconds(db.TaskRun.start_time, start_datetime)
            / delta.total_seconds()
        ).label("bucket")

        raw_counts = (
            (
                await models.task_runs._apply_task_run_filters(
                    db,
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


@router.get("/{id:uuid}")
async def read_task_run_with_flow_run_name(
    task_run_id: UUID = Path(..., description="The task run id", alias="id"),
    db: PrefectDBInterface = Depends(provide_database_interface),
) -> schemas.ui.UITaskRun:
    """
    Get a task run by id.
    """
    async with db.session_context() as session:
        task_run = await models.task_runs.read_task_run_with_flow_run_name(
            session=session, task_run_id=task_run_id
        )

    if not task_run:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")

    return schemas.ui.UITaskRun.model_validate(task_run)
