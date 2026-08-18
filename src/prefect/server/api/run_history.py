"""
Utilities for querying flow and task run history.
"""

import datetime
from collections import defaultdict
from typing import TYPE_CHECKING, Any, List, Optional

import pydantic
import sqlalchemy as sa
from typing_extensions import Literal

import prefect.server.models as models
import prefect.server.schemas as schemas
from prefect.logging import get_logger
from prefect.server.database import PrefectDBInterface, db_injector
from prefect.types import DateTime

if TYPE_CHECKING:
    import logging

logger: "logging.Logger" = get_logger("server.api")


@db_injector
async def run_history(
    db: PrefectDBInterface,
    session: sa.orm.Session,
    run_type: Literal["flow_run", "task_run"],
    history_start: DateTime,
    history_end: DateTime,
    history_interval: datetime.timedelta,
    flows: Optional[schemas.filters.FlowFilter] = None,
    flow_runs: Optional[schemas.filters.FlowRunFilter] = None,
    task_runs: Optional[schemas.filters.TaskRunFilter] = None,
    deployments: Optional[schemas.filters.DeploymentFilter] = None,
    work_pools: Optional[schemas.filters.WorkPoolFilter] = None,
    work_queues: Optional[schemas.filters.WorkQueueFilter] = None,
) -> list[schemas.responses.HistoryResponse]:
    """
    Produce a history of runs aggregated by interval and state
    """

    # Pendulum intervals do not support floor division by a timedelta.
    history_interval = datetime.timedelta(seconds=history_interval.total_seconds())
    elapsed = history_end - history_start
    elapsed = datetime.timedelta(seconds=elapsed.total_seconds())

    # SQLite has issues with very small intervals
    # (by 0.001 seconds it stops incrementing the interval)
    if history_interval < datetime.timedelta(seconds=1):
        raise ValueError("History interval must not be less than 1 second.")

    # prepare run-specific models
    if run_type == "flow_run":
        run_model = db.FlowRun
        run_filter_function = models.flow_runs._apply_flow_run_filters
    elif run_type == "task_run":
        run_model = db.TaskRun
        run_filter_function = models.task_runs._apply_task_run_filters
    else:
        raise ValueError(
            f"Unknown run type {run_type!r}. Expected 'flow_run' or 'task_run'."
        )

    interval_count = (
        min(-((-elapsed) // history_interval), 500)
        if elapsed > datetime.timedelta(0)
        else 0
    )
    if interval_count == 0:
        return []

    history_query_end = history_start + interval_count * history_interval

    # apply filters to the flow runs (and related states)
    runs = await run_filter_function(
        db,
        sa.select(
            run_model.id,
            run_model.expected_start_time,
            run_model.estimated_run_time,
            run_model.estimated_start_time_delta,
            run_model.state_type,
            run_model.state_name,
            db.queries.make_timestamp_bucket_index(
                run_model.expected_start_time,
                history_start,
                history_interval,
            ).label("bucket_index"),
        )
        .select_from(run_model)
        .where(
            run_model.expected_start_time >= history_start,
            run_model.expected_start_time < history_query_end,
        ),
        flow_filter=flows,
        flow_run_filter=flow_runs,
        task_run_filter=task_runs,
        deployment_filter=deployments,
        work_pool_filter=work_pools,
        work_queue_filter=work_queues,
    )
    runs = runs.alias("runs")

    counts = sa.select(
        runs.c.bucket_index,
        runs.c.state_type,
        runs.c.state_name,
        sa.func.count(runs.c.id).label("count_runs"),
        # estimated run times only includes positive run times (to avoid any unexpected corner cases)
        sa.func.sum(
            sa.func.greatest(0, sa.extract("epoch", runs.c.estimated_run_time))
        ).label("sum_estimated_run_time"),
        # estimated lateness is the sum of any positive start time deltas
        sa.func.sum(
            sa.func.greatest(0, sa.extract("epoch", runs.c.estimated_start_time_delta))
        ).label("sum_estimated_lateness"),
    ).group_by(
        runs.c.bucket_index,
        runs.c.state_type,
        runs.c.state_name,
    )

    # issue the query
    result = await session.execute(counts)
    states_by_bucket: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for record in result.mappings():
        states_by_bucket[record["bucket_index"]].append(
            {
                "state_type": record["state_type"],
                "state_name": record["state_name"],
                "count_runs": record["count_runs"],
                "sum_estimated_run_time": record["sum_estimated_run_time"],
                "sum_estimated_lateness": record["sum_estimated_lateness"],
            }
        )

    records = [
        {
            "interval_start": history_start + i * history_interval,
            "interval_end": history_start + (i + 1) * history_interval,
            "states": states_by_bucket[i],
        }
        for i in range(interval_count)
    ]

    return pydantic.TypeAdapter(
        List[schemas.responses.HistoryResponse]
    ).validate_python(records)
