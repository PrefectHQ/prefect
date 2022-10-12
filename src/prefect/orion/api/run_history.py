"""
Utilities for querying flow and task run history.
"""

import datetime
import json
from typing import List

import pydantic
import sqlalchemy as sa
from typing_extensions import Literal

import prefect.orion.models as models
import prefect.orion.schemas as schemas
from prefect.logging import get_logger
from prefect.orion.database.dependencies import inject_db
from prefect.orion.database.interface import OrionDBInterface
from prefect.orion.utilities.schemas import DateTimeTZ

logger = get_logger("orion.api")


@inject_db
async def run_history(
    session: sa.orm.Session,
    db: OrionDBInterface,
    run_type: Literal["flow_run", "task_run"],
    history_start: DateTimeTZ,
    history_end: DateTimeTZ,
    history_interval: datetime.timedelta,
    flows: schemas.filters.FlowFilter = None,
    flow_runs: schemas.filters.FlowRunFilter = None,
    task_runs: schemas.filters.TaskRunFilter = None,
    deployments: schemas.filters.DeploymentFilter = None,
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
        run_model = db.FlowRun
        run_filter_function = models.flow_runs._apply_flow_run_filters
    elif run_type == "task_run":
        run_model = db.TaskRun
        run_filter_function = models.task_runs._apply_task_run_filters

    # create a CTE for timestamp intervals
    intervals = db.make_timestamp_intervals(
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
                run_model.state_type,
                run_model.state_name,
            ).select_from(run_model),
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
                else_=db.build_json_object(
                    "state_type",
                    runs.c.state_type,
                    "state_name",
                    runs.c.state_name,
                    "count_runs",
                    sa.func.count(runs.c.id),
                    # estimated run times only includes positive run times (to avoid any unexpected corner cases)
                    "sum_estimated_run_time",
                    sa.func.sum(
                        db.greatest(0, sa.extract("epoch", runs.c.estimated_run_time))
                    ),
                    # estimated lateness is the sum of any positive start time deltas
                    "sum_estimated_lateness",
                    sa.func.sum(
                        db.greatest(
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
                db.json_arr_agg(db.cast_to_json(counts.c.state_agg)).filter(
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
    if db.uses_json_strings:
        records = [dict(r) for r in records]
        for r in records:
            r["states"] = json.loads(r["states"])

    return pydantic.parse_obj_as(List[schemas.responses.HistoryResponse], records)
