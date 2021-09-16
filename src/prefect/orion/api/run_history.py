import datetime
import json
from typing import List
from typing_extensions import Literal

import pendulum
import sqlalchemy as sa

from prefect.orion import models, schemas
from prefect.orion.api import dependencies
from prefect.orion.utilities.database import Timestamp, get_dialect, JSON, Base
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
                VALUES(
                    strftime('%Y-%m-%d %H:%M:%f000+00:00', :start_time), 
                    strftime('%Y-%m-%d %H:%M:%f000+00:00', :start_time, :interval)
                    )
                
                UNION ALL
                
                SELECT interval_end, strftime('%Y-%m-%d %H:%M:%f000+00:00', interval_end, :interval)
                FROM intervals
                -- subtract interval because recursive where clauses are effectively evaluated on a t-1 lag
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


async def run_history(
    session: sa.orm.Session,
    run_type: Literal["flow_run", "task_run"],
    history_start: datetime.datetime,
    history_end: datetime.datetime,
    history_interval: datetime.timedelta,
    flows: schemas.filters.FlowFilter = None,
    flow_runs: schemas.filters.FlowRunFilter = None,
    task_runs: schemas.filters.TaskRunFilter = None,
) -> List[schemas.responses.HistoryResponse]:
    """
    Produce a history of runs aggregated by interval and state
    """
    # prepare run-specific models
    if run_type == "flow_run":
        run_model = models.orm.FlowRun
        state_model = models.orm.FlowRunState
        run_filter_function = models.flow_runs._apply_flow_run_filters
    elif run_type == "task_run":
        run_model = models.orm.TaskRun
        state_model = models.orm.TaskRunState
        run_filter_function = models.task_runs._apply_task_run_filters

    # prepare dialect-independent functions
    if get_dialect(session=session).name == "postgresql":
        make_timestamp_intervals = postgres_timestamp_intervals
        json_arr_agg = sa.func.jsonb_agg
        json_build_object = sa.func.jsonb_build_object
        json_cast = lambda x: x
    elif get_dialect(session=session).name == "sqlite":
        make_timestamp_intervals = sqlite_timestamp_intervals
        json_arr_agg = sa.func.json_group_array
        json_build_object = sa.func.json_object
        json_cast = sa.func.json

    # create a CTE for timestamp intervals
    intervals = make_timestamp_intervals(
        history_start,
        history_end,
        history_interval,
    ).cte("intervals")

    # apply filters to the flow runs
    filtered_runs = run_filter_function(
        sa.select(
            run_model.id,
            run_model.state_id,
            run_model.expected_start_time,
            run_model.state_type,
        ),
        flow_filter=flows,
        flow_run_filter=flow_runs,
        task_run_filter=task_runs,
    ).alias("filtered_runs")

    # outer join intervals to the filtered runs (and states) to create a dataset
    # of each interval and any runs it contains. Aggregate the runs into a a JSON
    # object that represents each state type / name / count.
    counts = (
        sa.select(
            intervals.c.interval_start,
            intervals.c.interval_end,
            sa.case(
                (sa.func.count(filtered_runs.c.id) == 0, None),
                else_=json_build_object(
                    "type",
                    state_model.type,
                    "name",
                    state_model.name,
                    "count",
                    sa.func.count(filtered_runs.c.id),
                ),
            ).label("state_agg"),
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
        .join(
            state_model,
            filtered_runs.c.state_id == state_model.id,
            isouter=True,
        )
        .group_by(
            intervals.c.interval_start,
            intervals.c.interval_end,
            state_model.type,
            state_model.name,
        )
    ).alias("counts")

    # aggregate all state counts into a single array for each interval,
    # ensuring that intervals with no runs have an empty array
    query = (
        sa.select(
            counts.c.interval_start,
            counts.c.interval_end,
            sa.func.coalesce(
                json_arr_agg(json_cast(counts.c.state_agg)).filter(
                    counts.c.state_agg.is_not(None)
                ),
                sa.text("'[]'"),
            ).label("states"),
        )
        .group_by(counts.c.interval_start, counts.c.interval_end)
        .order_by(counts.c.interval_start)
        # return no more than 500 bars
        .limit(500)
    )

    result = await session.execute(query)
    records = result.all()

    # sqlite returns JSON as strings so we have to load
    # and parse the record
    if get_dialect(session=session).name == "sqlite":
        records = [dict(r) for r in records]
        for r in records:
            r["states"] = json.loads(r["states"])
        return records
    else:
        return records
