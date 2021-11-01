"""
Utilities for querying flow and task run history.
"""

import datetime
import json
from typing import List
from typing_extensions import Literal

import sqlalchemy as sa

import pydantic
from prefect.orion import models, schemas
from prefect.utilities.logging import get_logger
from prefect.orion.database.dependencies import inject_db_interface

logger = get_logger("orion.api")


@inject_db_interface
async def run_history(
    session: sa.orm.Session,
    run_type: Literal["flow_run", "task_run"],
    history_start: datetime.datetime,
    history_end: datetime.datetime,
    history_interval: datetime.timedelta,
    flows: schemas.filters.FlowFilter = None,
    flow_runs: schemas.filters.FlowRunFilter = None,
    task_runs: schemas.filters.TaskRunFilter = None,
    deployments: schemas.filters.DeploymentFilter = None,
    db_interface=None,
) -> List[schemas.responses.HistoryResponse]:
    """
    Produce a history of runs aggregated by interval and state
    """

    # SQLite has issues with very small intervals
    # (by 0.001 seconds it stops incrementing the interval)
    if history_interval < datetime.timedelta(seconds=1):
        raise ValueError("History interval must not be less than 1 second.")

    # prepare run-specific models
    if run_type == "flow_run":
        run_model = db_interface.FlowRun
        state_model = db_interface.FlowRunState
        run_filter_function = models.flow_runs._apply_flow_run_filters
    elif run_type == "task_run":
        run_model = db_interface.TaskRun
        state_model = db_interface.TaskRunState
        run_filter_function = models.task_runs._apply_task_run_filters

    make_timestamp_intervals = db_interface.make_timestamp_intervals
    json_arr_agg = db_interface.json_arr_agg
    json_build_object = db_interface.json_build_object
    json_cast = db_interface.json_cast
    greatest = db_interface.greatest

    # create a CTE for timestamp intervals
    intervals = make_timestamp_intervals(
        history_start,
        history_end,
        history_interval,
    ).cte("intervals")

    # apply filters to the flow runs (and related states)
    runs = (
        await run_filter_function(
            sa.select(
                run_model.id,
                run_model.expected_start_time,
                run_model.estimated_run_time,
                run_model.estimated_start_time_delta,
                state_model.type.label("state_type"),
                state_model.name.label("state_name"),
            )
            .select_from(run_model)
            .join(state_model, run_model.state_id == state_model.id),
            flow_filter=flows,
            flow_run_filter=flow_runs,
            task_run_filter=task_runs,
            deployment_filter=deployments,
        )
    ).alias("runs")
    # outer join intervals to the filtered runs to create a dataset composed of
    # every interval and the aggregate of all its runs. The runs aggregate is represented
    # by a descriptive JSON object
    counts = (
        sa.select(
            intervals.c.interval_start,
            intervals.c.interval_end,
            # build a JSON object, ignoring the case where the count of runs is 0
            sa.case(
                (sa.func.count(runs.c.id) == 0, None),
                else_=json_build_object(
                    "state_type",
                    runs.c.state_type,
                    "state_name",
                    runs.c.state_name,
                    "count_runs",
                    sa.func.count(runs.c.id),
                    # estimated run times only includes positive run times (to avoid any unexpected corner cases)
                    "sum_estimated_run_time",
                    sa.func.sum(
                        greatest(0, sa.extract("epoch", runs.c.estimated_run_time))
                    ),
                    # estimated lateness is the sum of any positive start time deltas
                    "sum_estimated_lateness",
                    sa.func.sum(
                        greatest(
                            0, sa.extract("epoch", runs.c.estimated_start_time_delta)
                        )
                    ),
                ),
            ).label("state_agg"),
        )
        .select_from(intervals)
        .join(
            runs,
            sa.and_(
                runs.c.expected_start_time >= intervals.c.interval_start,
                runs.c.expected_start_time < intervals.c.interval_end,
            ),
            isouter=True,
        )
        .group_by(
            intervals.c.interval_start,
            intervals.c.interval_end,
            runs.c.state_type,
            runs.c.state_name,
        )
    ).alias("counts")

    # aggregate all state-aggregate objects into a single array for each interval,
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

    # issue the query
    result = await session.execute(query)
    records = result.all()

    # load and parse the record if the database returns JSON as strings
    if db_interface.uses_json_strings:
        records = [dict(r) for r in records]
        for r in records:
            r["states"] = json.loads(r["states"])

    return pydantic.parse_obj_as(List[schemas.responses.HistoryResponse], records)
