import datetime
from typing import Any, Optional, Union
from typing_extensions import TypeAlias, TypeGuard
from pydantic_extra_types.pendulum_dt import DateTime

from .cron_schedule import CronSchedule
from .interval_schedule import IntervalSchedule
from .no_schedule import NoSchedule
from .r_rule_schedule import RRuleSchedule

SCHEDULE_TYPES: TypeAlias = Union[
    IntervalSchedule, CronSchedule, RRuleSchedule, NoSchedule
]


def is_schedule_type(obj: Any) -> TypeGuard[SCHEDULE_TYPES]:
    return isinstance(obj, (IntervalSchedule, CronSchedule, RRuleSchedule, NoSchedule))


def construct_schedule(
    interval: Optional[Union[int, float, datetime.timedelta]] = None,
    anchor_date: Optional[Union[datetime.datetime, str]] = None,
    cron: Optional[str] = None,
    rrule: Optional[str] = None,
    timezone: Optional[str] = None,
) -> SCHEDULE_TYPES:
    """
    Construct a schedule from the provided arguments.

    Args:
        interval: An interval on which to schedule runs. Accepts either a number
            or a timedelta object. If a number is given, it will be interpreted as seconds.
        anchor_date: The start date for an interval schedule.
        cron: A cron schedule for runs.
        rrule: An rrule schedule of when to execute runs of this flow.
        timezone: A timezone to use for the schedule. Defaults to UTC.
    """
    num_schedules = sum(1 for entry in (interval, cron, rrule) if entry is not None)
    if num_schedules > 1:
        raise ValueError("Only one of interval, cron, or rrule can be provided.")

    if anchor_date and not interval:
        raise ValueError(
            "An anchor date can only be provided with an interval schedule"
        )

    if timezone and not (interval or cron or rrule):
        raise ValueError(
            "A timezone can only be provided with interval, cron, or rrule"
        )

    schedule = None
    if interval:
        if isinstance(interval, (int, float)):
            interval = datetime.timedelta(seconds=interval)
        if not anchor_date:
            anchor_date = DateTime.now()
        schedule = IntervalSchedule(
            interval=interval, anchor_date=anchor_date, timezone=timezone
        )
    elif cron:
        schedule = CronSchedule(cron=cron, timezone=timezone)
    elif rrule:
        schedule = RRuleSchedule(rrule=rrule, timezone=timezone)

    if schedule is None:
        raise ValueError("Either interval, cron, or rrule must be provided")

    return schedule
