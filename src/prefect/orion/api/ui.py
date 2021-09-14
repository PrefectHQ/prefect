import pendulum
import json
import datetime
from typing import Dict, List

import sqlalchemy as sa
from fastapi import Body, Depends

from prefect.orion import models, schemas
from prefect.orion.api import dependencies
from prefect.orion.utilities.database import Timestamp
from prefect.orion.utilities.schemas import PrefectBaseModel
from prefect.utilities.logging import get_logger

logger = get_logger("orion.api")


def sqlite_timestamp_intervals(
    start_time: datetime.datetime, end_time: datetime.datetime, interval: str
):
    # validate inputs
    start_time = pendulum.instance(start_time)
    end_time = pendulum.instance(end_time)

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
    interval: str,
):
    # validate inputs
    start_time = pendulum.instance(start_time)
    end_time = pendulum.instance(end_time)
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


class TimelineResponse(PrefectBaseModel):
    interval_start: datetime.datetime
    interval_end: datetime.datetime
    states: Dict[schemas.states.StateType, int]


async def flow_run_timeline(
    start_time: datetime.datetime = Body(..., description="The timeline's start time."),
    end_time: datetime.datetime = Body(..., description="The timeline's end time."),
    interval: datetime.timedelta = Body(
        ..., description="The timeline's grouping interval."
    ),
    flows: schemas.filters.FlowFilter = None,
    flow_runs: schemas.filters.FlowRunFilter = None,
    task_runs: schemas.filters.TaskRunFilter = None,
    session: sa.orm.Session = Depends(dependencies.get_session),
) -> List[TimelineResponse]:
    """
    Produce a timeline of flow runs
    """

    # compute all intervals as a CTE
    if session.bind.dialect.name == "sqlite":
        intervals = sqlite_timestamp_intervals(start_time, end_time, interval).cte(
            "intervals"
        )
    elif session.bind.dialect.name == "postgresql":
        intervals = postgres_timestamp_intervals(start_time, end_time, interval).cte(
            "intervals"
        )

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
    if session.bind.dialect.name == "postgresql":
        json_col = (
            sa.func.jsonb_object_agg(counts_query.c.state, counts_query.c.count)
            - "NO_STATE"
        )
    elif session.bind.dialect.name == "sqlite":
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

    breakpoint()
    result = await session.execute(final_query)
    records = result.all()

    # sqlite returns JSON as strings
    if session.bind.dialect.name == "sqlite":
        all_records = []
        for r in records:
            r = dict(r)
            r["states"] = json.loads(r["states"])
            all_records.append(r)
        return all_records
    else:
        return records
