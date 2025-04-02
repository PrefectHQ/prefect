"""
This module contains functionality for creating schedules for deployments.
"""

from __future__ import annotations

import dataclasses
import datetime
from functools import partial
from typing import Any

from prefect._internal.schemas.validators import (
    validate_cron_string,
    validate_rrule_string,
)


@dataclasses.dataclass(frozen=True)
class Schedule:
    """
    A dataclass representing a schedule.

    Note that only one of `interval`, `cron`, or `rrule` can be defined at a time.

    Attributes:
        interval: A timedelta representing the frequency of the schedule.
        cron: A valid cron string (e.g. "0 0 * * *").
        rrule: A valid RRule string (e.g. "RRULE:FREQ=DAILY;INTERVAL=1").
        timezone: A valid timezone string in IANA tzdata format (e.g. America/New_York).
        anchor_date: An anchor date to schedule increments against; if not provided,
            the current timestamp will be used.
        day_or: Control how `day` and `day_of_week` entries are handled.
            Defaults to True, matching cron which connects those values using
            OR. If the switch is set to False, the values are connected using AND.
            This behaves like fcron and enables you to e.g. define a job that
            executes each 2nd friday of a month by setting the days of month and
            the weekday.
        active: Whether or not the schedule is active.
        parameters: A dictionary containing parameter overrides for the schedule.
        slug: A unique identifier for the schedule.
    """

    interval: datetime.timedelta | None = None
    cron: str | None = None
    rrule: str | None = None
    timezone: str | None = None
    anchor_date: datetime.datetime = dataclasses.field(
        default_factory=partial(datetime.datetime.now, tz=datetime.timezone.utc)
    )
    day_or: bool = True
    active: bool = True
    parameters: dict[str, Any] = dataclasses.field(default_factory=dict)
    slug: str | None = None

    def __post_init__(self) -> None:
        defined_fields = [
            field
            for field in ["interval", "cron", "rrule"]
            if getattr(self, field) is not None
        ]
        if len(defined_fields) > 1:
            raise ValueError(
                f"Only one schedule type can be defined at a time. Found: {', '.join(defined_fields)}"
            )

        if self.cron is not None:
            validate_cron_string(self.cron)
        if self.rrule is not None:
            validate_rrule_string(self.rrule)


def Cron(
    cron: str,
    /,
    timezone: str | None = None,
    day_or: bool = True,
    active: bool = True,
    parameters: dict[str, Any] | None = None,
    slug: str | None = None,
) -> Schedule:
    """
    Creates a cron schedule.

    Args:
        cron: A valid cron string (e.g. "0 0 * * *").
        timezone: A valid timezone string in IANA tzdata format (e.g. America/New_York).
        day_or: Control how `day` and `day_of_week` entries are handled.
            Defaults to True, matching cron which connects those values using
            OR. If the switch is set to False, the values are connected using AND.
            This behaves like fcron and enables you to e.g. define a job that
            executes each 2nd friday of a month by setting the days of month and
            the weekday.
        active: Whether or not the schedule is active.
        parameters: A dictionary containing parameter overrides for the schedule.
        slug: A unique identifier for the schedule.

    Returns:
        A cron schedule.

    Examples:
        Create a cron schedule that runs every day at 12:00 AM UTC:
        ```python
        from prefect.schedules import Cron

        Cron("0 0 * * *")
        ```

        Create a cron schedule that runs every Monday at 8:00 AM in the America/New_York timezone:
        ```python
        from prefect.schedules import Cron

        Cron("0 8 * * 1", timezone="America/New_York")
        ```

    """
    if parameters is None:
        parameters = {}
    return Schedule(
        cron=cron,
        timezone=timezone,
        day_or=day_or,
        active=active,
        parameters=parameters,
        slug=slug,
    )


def Interval(
    interval: datetime.timedelta | float | int,
    /,
    anchor_date: datetime.datetime | None = None,
    timezone: str | None = None,
    active: bool = True,
    parameters: dict[str, Any] | None = None,
    slug: str | None = None,
) -> Schedule:
    """
    Creates an interval schedule.

    Args:
        interval: The interval to use for the schedule. If an integer is provided,
            it will be interpreted as seconds.
        anchor_date: The anchor date to use for the schedule.
        timezone: A valid timezone string in IANA tzdata format (e.g. America/New_York).
        active: Whether or not the schedule is active.
        parameters: A dictionary containing parameter overrides for the schedule.
        slug: A unique identifier for the schedule.

    Returns:
        An interval schedule.

    Examples:
        Create an interval schedule that runs every hour:
        ```python
        from datetime import timedelta

        from prefect.schedules import Interval

        Interval(timedelta(hours=1))
        ```

        Create an interval schedule that runs every 60 seconds starting at a specific date:
        ```python
        from datetime import datetime

        from prefect.schedules import Interval

        Interval(60, anchor_date=datetime(2024, 1, 1))
        ```
    """
    if isinstance(interval, (float, int)):
        interval = datetime.timedelta(seconds=interval)
    if anchor_date is None:
        anchor_date = datetime.datetime.now(tz=datetime.timezone.utc)
    if parameters is None:
        parameters = {}
    return Schedule(
        interval=interval,
        anchor_date=anchor_date,
        timezone=timezone,
        active=active,
        parameters=parameters,
        slug=slug,
    )


def RRule(
    rrule: str,
    /,
    timezone: str | None = None,
    active: bool = True,
    parameters: dict[str, Any] | None = None,
    slug: str | None = None,
) -> Schedule:
    """
    Creates an RRule schedule.

    Args:
        rrule: A valid RRule string (e.g. "RRULE:FREQ=DAILY;INTERVAL=1").
        timezone: A valid timezone string in IANA tzdata format (e.g. America/New_York).
        active: Whether or not the schedule is active.
        parameters: A dictionary containing parameter overrides for the schedule.
        slug: A unique identifier for the schedule.

    Returns:
        An RRule schedule.

    Examples:
        Create an RRule schedule that runs every day at 12:00 AM UTC:
        ```python
        from prefect.schedules import RRule

        RRule("RRULE:FREQ=DAILY;INTERVAL=1")
        ```

        Create an RRule schedule that runs every 2nd friday of the month in the America/Chicago timezone:
        ```python
        from prefect.schedules import RRule

        RRule("RRULE:FREQ=MONTHLY;INTERVAL=1;BYDAY=2FR", timezone="America/Chicago")
        ```
    """
    if parameters is None:
        parameters = {}
    return Schedule(
        rrule=rrule,
        timezone=timezone,
        active=active,
        parameters=parameters,
        slug=slug,
    )
