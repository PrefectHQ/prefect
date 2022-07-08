"""
Schedule schemas
"""

import asyncio
import datetime
from typing import List, Union

import pendulum
import pytz
from croniter import croniter
from dateutil import rrule
from dateutil import tz as dateutil_tz
from pydantic import Field, validator

from prefect.orion.utilities.schemas import PrefectBaseModel

MAX_ITERATIONS = 10000


class IntervalSchedule(PrefectBaseModel):
    """
    A schedule formed by adding `interval` increments to an `anchor_date`. If no
    `anchor_date` is supplied, January 1, 2020 at midnight UTC is used.

    NOTE: If the `IntervalSchedule` `anchor_date` or `timezone` is provided in a
    DST-observing timezone, then the schedule will adjust itself appropriately.
    Intervals greater than 24 hours will follow DST conventions, while intervals
    of less than 24 hours will follow UTC intervals. For example, an hourly
    schedule will fire every UTC hour, even across DST boundaries. When clocks
    are set back, this will result in two runs that *appear* to both be
    scheduled for 1am local time, even though they are an hour apart in UTC
    time. For longer intervals, like a daily schedule, the interval schedule
    will adjust for DST boundaries so that the clock-hour remains constant. This
    means that a daily schedule that always fires at 9am will observe DST and
    continue to fire at 9am in the local time zone.
    """

    class Config:
        extra = "forbid"
        exclude_none = True

    interval: datetime.timedelta
    timezone: str = Field(None, example="America/New_York")
    anchor_date: datetime.datetime = None

    @validator("interval")
    def interval_must_be_positive(cls, v):
        if v.total_seconds() <= 0:
            raise ValueError("The interval must be positive")
        return v

    @validator("timezone")
    def valid_timezone(cls, v):
        if v and v not in pendulum.tz.timezones:
            raise ValueError(f'Invalid timezone: "{v}"')
        return v

    @validator("anchor_date", pre=True, always=True)
    def default_anchor_with_timezone(cls, v, *, values, **kwargs):
        if v and values["timezone"]:
            raise ValueError("Specify an anchor date or a timezone, but not both.")
        return v or pendulum.datetime(2020, 1, 1, tz=values.get("timezone") or "UTC")

    async def get_dates(
        self,
        n: int = None,
        start: datetime.datetime = None,
        end: datetime.datetime = None,
    ) -> List[pendulum.DateTime]:
        """Retrieves dates from the schedule. Up to 10,000 candidate dates are checked
        following the start date.

        Args:
            n (int): The number of dates to generate
            start (datetime.datetime, optional): The first returned date will be on or after
                this date. Defaults to None.
            end (datetime.datetime, optional): The maximum scheduled date to return

        Returns:
            List[pendulum.DateTime]: a list of dates
        """
        if start is None:
            start = pendulum.now(self.timezone or "UTC")
        if n is None:
            # if an end was supplied, we do our best to supply all matching dates (up to MAX_ITERATIONS)
            if end is not None:
                n = MAX_ITERATIONS
            else:
                n = 1

        # compute the offset between the anchor date and the start date to jump to the next date
        offset = (
            start - self.anchor_date
        ).total_seconds() / self.interval.total_seconds()
        next_date = pendulum.instance(self.anchor_date).add(
            seconds=self.interval.total_seconds() * int(offset)
        )

        # break the interval into `days` and `seconds` because pendulum
        # will handle DST boundaries properly if days are provided, but not
        # if we add `total seconds`. Therefore, `next_date + self.interval`
        # fails while `next_date.add(days=days, seconds=seconds)` works.
        interval_days = self.interval.days
        interval_seconds = self.interval.total_seconds() - (
            interval_days * 24 * 60 * 60
        )

        # daylight saving time boundaries can create a situation where the next date is before
        # the start date, so we advance it if necessary
        while next_date < start:
            next_date = next_date.add(days=interval_days, seconds=interval_seconds)

        counter = 0
        dates = set()

        while True:

            # if the end date was exceeded, exit
            if end and next_date > end:
                break

            # ensure no duplicates; weird things can happen with DST
            dates.add(next_date)

            # if enough dates have been collected or enough attempts were made, exit
            if len(dates) >= n or counter > MAX_ITERATIONS:
                break

            counter += 1

            next_date = next_date.add(days=interval_days, seconds=interval_seconds)

            # yield event loop control
            await asyncio.sleep(0)

        return sorted(dates)


class CronSchedule(PrefectBaseModel):
    """
    Cron schedule

    NOTE: If the timezone is a DST-observing one, then the schedule will adjust
    itself appropriately. Cron's rules for DST are based on schedule times, not
    intervals. This means that an hourly cron schedule will fire on every new
    schedule hour, not every elapsed hour; for example, when clocks are set back
    this will result in a two-hour pause as the schedule will fire *the first
    time* 1am is reached and *the first time* 2am is reached, 120 minutes later.
    Longer schedules, such as one that fires at 9am every morning, will
    automatically adjust for DST.

    Args:
        cron (str): a valid cron string
        timezone (str): a valid timezone string
        day_or (bool, optional): Control how croniter handles `day` and `day_of_week` entries.
            Defaults to True, matching cron which connects those values using OR.
            If the switch is set to False, the values are connected using AND. This behaves like
            fcron and enables you to e.g. define a job that executes each 2nd friday of a month
            by setting the days of month and the weekday.

    """

    class Config:
        extra = "forbid"

    cron: str = Field(..., example="0 0 * * *")
    timezone: str = Field(None, example="America/New_York")
    day_or: bool = Field(
        True,
        description="Control croniter behavior for handling day and day_of_week entries.",
    )

    @validator("timezone")
    def valid_timezone(cls, v):
        if v and v not in pendulum.tz.timezones:
            raise ValueError(f'Invalid timezone: "{v}"')
        return v

    @validator("cron")
    def valid_cron_string(cls, v):
        # croniter allows "random" and "hashed" expressions
        # which we do not support https://github.com/kiorky/croniter
        if not croniter.is_valid(v):
            raise ValueError(f'Invalid cron string: "{v}"')
        elif any(c for c in v.split() if c.casefold() in ["R", "H", "r", "h"]):
            raise ValueError(
                f'Random and Hashed expressions are unsupported, recieved: "{v}"'
            )
        return v

    async def get_dates(
        self,
        n: int = None,
        start: datetime.datetime = None,
        end: datetime.datetime = None,
    ) -> List[pendulum.DateTime]:
        """Retrieves dates from the schedule. Up to 10,000 candidate dates are checked
        following the start date.

        Args:
            n (int): The number of dates to generate
            start (datetime.datetime, optional): The first returned date will be on or after
                this date. Defaults to the current date.
            end (datetime.datetime, optional): No returned date will exceed this date.

        Returns:
            List[pendulum.DateTime]: a list of dates
        """
        if start is None:
            start = pendulum.now(self.timezone or "UTC")

        if n is None:
            # if an end was supplied, we do our best to supply all matching dates (up to MAX_ITERATIONS)
            if end is not None:
                n = MAX_ITERATIONS
            else:
                n = 1

        elif self.timezone:
            start = start.in_tz(self.timezone)

        # subtract one second from the start date, so that croniter returns it
        # as an event (if it meets the cron criteria)
        start = start.subtract(seconds=1)

        # croniter's DST logic interferes with all other datetime libraries except pytz
        start_localized = pytz.timezone(start.tz.name).localize(
            datetime.datetime(
                year=start.year,
                month=start.month,
                day=start.day,
                hour=start.hour,
                minute=start.minute,
                second=start.second,
                microsecond=start.microsecond,
            )
        )

        # Respect microseconds by rounding up
        if start_localized.microsecond > 0:
            start_localized += datetime.timedelta(seconds=1)

        cron = croniter(self.cron, start_localized, day_or=self.day_or)  # type: ignore
        dates = set()
        counter = 0

        while True:

            next_date = pendulum.instance(cron.get_next(datetime.datetime))
            # if the end date was exceeded, exit
            if end and next_date > end:
                break
            # ensure no duplicates; weird things can happen with DST
            dates.add(next_date)

            # if enough dates have been collected or enough attempts were made, exit
            if len(dates) >= n or counter > MAX_ITERATIONS:
                break

            counter += 1

            # yield event loop control
            await asyncio.sleep(0)

        return sorted(dates)


class RRuleSchedule(PrefectBaseModel):
    """
    RRule schedule, based on the iCalendar standard
    ([RFC 5545](https://datatracker.ietf.org/doc/html/rfc5545)) as
    implemented in `dateutils.rrule`.

    RRules are appropriate for any kind of calendar-date manipulation, including
    irregular intervals, repetition, exclusions, week day or day-of-month
    adjustments, and more.

    Note that as a calendar-oriented standard, `RRuleSchedules` are sensitive to
    to the initial timezone provided. A 9am daily schedule with a daylight saving
    time-aware start date will maintain a local 9am time through DST boundaries;
    a 9am daily schedule with a UTC start date will maintain a 9am UTC time.
    """

    class Config:
        extra = "forbid"

    rrule: str
    timezone: str = Field(None, example="America/New_York")

    @classmethod
    def from_rrule(cls, rrule: rrule.rrule):
        if rrule._dtstart.tzinfo is not None:
            timezone = rrule._dtstart.tzinfo.name
        else:
            timezone = "UTC"
        return RRuleSchedule(rrule=str(rrule), timezone=timezone)

    def to_rrule(self) -> rrule.rrule:
        """
        Since rrule doesn't properly serialize/deserialize timezones, we localize dates here
        """
        rrule_obj = rrule.rrulestr(self.rrule, cache=True)
        kwargs = dict(
            dtstart=rrule_obj._dtstart.replace(tzinfo=dateutil_tz.gettz(self.timezone))
        )
        if rrule_obj._until:
            kwargs.update(
                until=rrule_obj._until.replace(tzinfo=dateutil_tz.gettz(self.timezone)),
            )
        return rrule_obj.replace(**kwargs)

    @validator("timezone", always=True)
    def valid_timezone(cls, v):
        if v and v not in pendulum.tz.timezones:
            raise ValueError(f'Invalid timezone: "{v}"')
        elif v is None:
            return "UTC"
        return v

    async def get_dates(
        self,
        n: int = None,
        start: datetime.datetime = None,
        end: datetime.datetime = None,
    ) -> List[pendulum.DateTime]:
        """Retrieves dates from the schedule. Up to 10,000 candidate dates are checked
        following the start date.

        Args:
            n (int): The number of dates to generate
            start (datetime.datetime, optional): The first returned date will be on or after
                this date. Defaults to the current date.
            end (datetime.datetime, optional): No returned date will exceed this date.

        Returns:
            List[pendulum.DateTime]: a list of dates
        """
        if start is None:
            start = pendulum.now(self.timezone or "UTC")
        else:
            start = start.in_tz(self.timezone)

        if n is None:
            # if an end was supplied, we do our best to supply all matching dates (up to MAX_ITERATIONS)
            if end is not None:
                n = MAX_ITERATIONS
            else:
                n = 1

        dates = set()
        counter = 0

        # pass count = None to account for discrepancies with duplicates around DST boundaries
        for next_date in self.to_rrule().xafter(start, count=None, inc=True):

            next_date = pendulum.instance(next_date).in_tz(self.timezone)

            # if the end date was exceeded, exit
            if end and next_date > end:
                break

            # ensure no duplicates; weird things can happen with DST
            dates.add(next_date)

            # if enough dates have been collected or enough attempts were made, exit
            if len(dates) >= n or counter > MAX_ITERATIONS:
                break

            counter += 1

            # yield event loop control
            await asyncio.sleep(0)

        return sorted(dates)


SCHEDULE_TYPES = Union[IntervalSchedule, CronSchedule, RRuleSchedule]
