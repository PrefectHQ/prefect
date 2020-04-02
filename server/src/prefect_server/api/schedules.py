# Licensed under the Prefect Community License, available at
# https://www.prefect.io/legal/prefect-community-license


import pendulum

import prefect
from prefect_server import api, utilities
from prefect_server.database import hasura, models
from prefect.serialization.schedule import ScheduleSchema

logger = utilities.logging.get_logger("api.schedules")
schedule_schema = ScheduleSchema()


async def set_active(schedule_id: str) -> bool:
    """
    Sets a flow schedule to active

    Args:
        - schedule_id (str): the schedule ID

    Returns:
        bool: if the update succeeded
    """

    result = await models.Schedule.where(id=schedule_id).update(set={"active": True})
    if not result.affected_rows:
        return False

    await schedule_flow_runs(schedule_id=schedule_id)
    return bool(result.affected_rows)


async def set_inactive(schedule_id: str) -> bool:
    """
    Sets a flow schedule to inactive

    Args:
        - schedule_id (str): the schedule ID

    Returns:
        bool: if the update succeeded
    """

    result = await models.Schedule.where(id=schedule_id).update(
        set={"active": False, "last_scheduled_run_time": None},
        selection_set={"affected_rows": True, "returning": {"flow_id"}},
    )
    if not result.affected_rows:
        raise ValueError(f'Schedule not found: "{schedule_id}"')

    await models.FlowRun.where(
        {
            "flow_id": {"_eq": result.returning[0].flow_id},
            "state": {"_eq": "Scheduled"},
            "auto_scheduled": {"_eq": True},
        }
    ).delete()
    return bool(result.affected_rows)


async def schedule_flow_runs(
    schedule_id: str, max_runs: int = None, seconds_since_last_checked: int = 0
) -> int:
    """
    Schedule the next `max_runs` runs for this schedule.
    Each scheduled run updates the "last scheduled run"

    Args:
        - schedule_id (str): the schedule ID
        - max_runs (int): the maximum number of runs to schedule. Runs will not be scheduled
            if they are earlier than the `last_checked_run`, so that this function can be
            called multiple times safely
        - seconds_since_last_checked (int): if provided, no runs will be scheduled unless
            this many seconds have passed since the last time the schedule was scheduled.
            For example, if `seconds_since_last_checked=60`, then running this function twice
            within 60 seconds will have no effect.

    Returns:
        - List[str]: the ids of the new runs
    """

    if max_runs is None:
        max_runs = 10

    run_ids = []

    now = pendulum.now("utc")
    schedule = await models.Schedule.where(
        {
            # match the provided ID
            "id": {"_eq": schedule_id},
            # schedule is active
            "active": {"_eq": True},
            # flow is not archived
            "flow": {"archived": {"_eq": False}},
            # it's been at least `seconds_since_last_checked` seconds since the last scheduling attempt
            "_or": [
                {
                    "last_checked": {
                        "_lte": str(now.subtract(seconds=seconds_since_last_checked))
                    }
                },
                {"last_checked": {"_is_null": True}},
            ],
        }
    ).update(
        set={"last_checked": now},
        selection_set={
            "affected_rows": True,
            "returning": {"schedule", "last_scheduled_run_time", "flow_id"},
        },
    )

    if not schedule.affected_rows:
        logger.debug(f"Schedule {schedule_id} was not ready for new scheduling.")
        return run_ids
    else:
        try:
            schedule = models.Schedule(**schedule.returning[0])
            schedule.schedule = schedule_schema.load(schedule.schedule)
        except Exception as exc:
            logger.error(exc)
            logger.critical(
                f"Failed to deserialize schedule {schedule_id}: {schedule.returning[0]}"
            )

    last_scheduled_run_time = schedule.last_scheduled_run_time

    mutations = []
    for i, event in enumerate(schedule.schedule.next(n=max_runs, return_events=True)):

        # if this run was already scheduled, continue
        if last_scheduled_run_time and event.start_time <= last_scheduled_run_time:
            continue

        run_id = await api.runs.create_flow_run(
            flow_id=schedule.flow_id,
            scheduled_start_time=event.start_time,
            parameters=event.parameter_defaults,
        )

        logger.debug(
            f"Flow run {run_id} of flow {schedule.flow_id} scheduled for {event.start_time}"
        )

        mutations.append(
            await models.Schedule.where(id=schedule_id).update(
                set={"last_scheduled_run_time": event.start_time},
                run_mutation=False,
                alias=f"update_schedule_{i}",
            )
        )
        last_scheduled_run_time = event.start_time

        run_ids.append(run_id)

    # for performance, defer all of these queries as long as possible (saves 0.4 seconds / unit test)
    await models.FlowRun.where({"id": {"_in": run_ids}}).update(
        set={"auto_scheduled": True}
    )
    if mutations:
        await hasura.client.execute_mutations_in_transaction(mutations)

    return run_ids
