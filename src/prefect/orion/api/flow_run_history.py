import datetime
import json
from typing import List

import pendulum
import sqlalchemy as sa
from fastapi import Body, Depends

from prefect.orion import models, schemas
from prefect.orion.api import dependencies
from prefect.orion.utilities.database import Timestamp, get_dialect
from prefect.utilities.logging import get_logger

logger = get_logger("orion.api")


def sqlite_timestamp_intervals(
    start_time: datetime.datetime,
    end_time: datetime.datetime,
    interval: datetime.timedelta,
):
    # validate inputs
    start_time = pendulum.instance(start_time)
    end_time = pendulum.instance(end_time)
    assert isinstance(interval, datetime.timedelta)

    return (
        sa.text(
            r"""
            WITH RECURSIVE intervals(interval_start, interval_end) AS (
                VALUES(strftime('%Y-%m-%d %H:%M:%f000+00:00', :start_time), strftime('%Y-%m-%d %H:%M:%f000+00:00', :start_time, :interval))
                UNION ALL
                SELECT interval_end, strftime('%Y-%m-%d %H:%M:%f000+00:00', interval_end, :interval)
                FROM intervals
                -- subtract interval because recursive where clauses are effectively
                -- evaluated on a t-1 lag
                WHERE interval_start < strftime('%Y-%m-%d %H:%M:%f000+00:00', :end_time, :negative_interval)
            )
            SELECT * FROM intervals
            """
        )
        .bindparams(
            start_time=str(start_time),
            end_time=str(end_time),
            interval=f"+{interval.total_seconds()} seconds",
            negative_interval=f"-{interval.total_seconds()} seconds",
        )
        .columns(interval_start=Timestamp(), interval_end=Timestamp())
    )


def postgres_timestamp_intervals(
    start_time: datetime.datetime,
    end_time: datetime.datetime,
    interval: datetime.timedelta,
):
    # validate inputs
    start_time = pendulum.instance(start_time)
    end_time = pendulum.instance(end_time)
    assert isinstance(interval, datetime.timedelta)
    return (
        sa.select(
            sa.literal_column("dt").label("interval_start"),
            (sa.literal_column("dt") + interval).label("interval_end"),
        )
        .select_from(
            sa.func.generate_series(start_time, end_time, interval).alias("dt")
        )
        .where(sa.literal_column("dt") < end_time)
    )


# this is added to a router in api/flow_runs.py to ensure
# it is given the correct route priority
async def flow_run_history(
    history_start: datetime.datetime = Body(
        ..., description="The history's start time."
    ),
    history_end: datetime.datetime = Body(..., description="The history's end time."),
    history_interval: datetime.timedelta = Body(
        ...,
        description="The size of each history interval, in seconds.",
        alias="history_interval_seconds",
    ),
    flows: schemas.filters.FlowFilter = None,
    flow_runs: schemas.filters.FlowRunFilter = None,
    task_runs: schemas.filters.TaskRunFilter = None,
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> List[schemas.responses.HistoryResponse]:
    """
    Produce a history of flow runs aggregated by state
    """

    # compute all intervals as a CTE
    if get_dialect(session=session).name == "sqlite":
        intervals = sqlite_timestamp_intervals(
            history_start, history_end, history_interval
        ).cte("intervals")
    elif get_dialect(session=session).name == "postgresql":
        intervals = postgres_timestamp_intervals(
            history_start, history_end, history_interval
        ).cte("intervals")

    # apply filters prior to outer join on intervals
    filtered_runs = models.flow_runs._apply_flow_run_filters(
        sa.select(models.orm.FlowRun),
        flow_filter=flows,
        flow_run_filter=flow_runs,
        task_run_filter=task_runs,
    ).alias("filtered_runs")

    # select the count of each state within each interval by performing an
    # outer join against all intervals and filtering appropriately
    counts_query = (
        sa.select(
            intervals.c.interval_start,
            intervals.c.interval_end,
            sa.func.coalesce(
                filtered_runs.c.state_type.cast(sa.String()),
                "NO_STATE",
            ).label("state"),
            sa.func.count(filtered_runs.c.id).label("count"),
        )
        .select_from(intervals)
        .join(
            filtered_runs,
            sa.and_(
                filtered_runs.c.expected_start_time >= intervals.c.interval_start,
                filtered_runs.c.expected_start_time < intervals.c.interval_end,
            ),
            isouter=True,
        )
        .group_by(
            intervals.c.interval_start,
            intervals.c.interval_end,
            filtered_runs.c.state_type,
        )
        .alias("counts_query")
    )

    # aggregate all state / count pairs into a JSON object, removing the empty
    # placeholders for NO_STATE
    if get_dialect(session=session).name == "postgresql":
        json_col = (
            sa.func.jsonb_object_agg(counts_query.c.state, counts_query.c.count)
            - "NO_STATE"
        )
    elif get_dialect(session=session).name == "sqlite":
        json_col = sa.func.json_remove(
            sa.func.json_group_object(counts_query.c.state, counts_query.c.count),
            "$.NO_STATE",
        )

    final_query = (
        sa.select(
            counts_query.c.interval_start,
            counts_query.c.interval_end,
            json_col.label("states"),
        )
        .select_from(counts_query)
        .group_by(counts_query.c.interval_start, counts_query.c.interval_end)
        .order_by(counts_query.c.interval_start)
        # return no more than 500 bars
        .limit(500)
    )

    result = await session.execute(final_query)
    records = result.all()

    # sqlite returns JSON as strings
    if get_dialect(session=session).name == "sqlite":
        all_records = []
        for r in records:
            r = dict(r)
            r["states"] = json.loads(r["states"])
            all_records.append(r)
        return all_records
    else:
        return records
