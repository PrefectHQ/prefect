import asyncio
import datetime
from typing import List, Set, Union

import pendulum
import pytz
from croniter import croniter
from dateutil import rrule
from pydantic import Field, conint, validator

from prefect.orion.utilities.schemas import PrefectBaseModel

MAX_ITERATIONS = 10000


class IntervalSchedule(PrefectBaseModel):
    class Config:
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
    ) -> List[datetime.datetime]:
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

        # daylight savings time boundaries can create a situation where the next date is before
        # the start date, so we advance it if necessary
        while next_date < start:
            next_date = next_date.add(days=interval_days, seconds=interval_seconds)

        counter = 0
        dates = []

        while True:

            # if the end date was exceeded, exit
            if end and next_date > end:
                break

            dates.append(next_date)

            # if enough dates have been collected or enough attempts were made, exit
            if len(dates) >= n or counter > MAX_ITERATIONS:
                break

            counter += 1

            next_date = next_date.add(days=interval_days, seconds=interval_seconds)

            # yield event loop control
            await asyncio.sleep(0)

        return dates


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
        if not croniter.is_valid(v):
            raise ValueError(f'Invalid cron string: "{v}"')
        return v

    async def get_dates(
        self,
        n: int = None,
        start: datetime.datetime = None,
        end: datetime.datetime = None,
    ) -> List[datetime.datetime]:
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
        dates = []
        counter = 0

        while True:

            next_date = pendulum.instance(cron.get_next(datetime.datetime))
            # if the end date was exceeded, exit
            if end and next_date > end:
                break
            # check for duplicates; weird things can happen with DST and cron
            if next_date not in dates:
                dates.append(next_date)

            # if enough dates have been collected or enough attempts were made, exit
            if len(dates) >= n or counter > MAX_ITERATIONS:
                break

            counter += 1

            # yield event loop control
            await asyncio.sleep(0)

        return dates


class RRuleSchedule(PrefectBaseModel):

    rrule: str
    timezone: str = Field(None, example="America/New_York")

    @classmethod
    def from_rrule(cls, rrule: rrule.rrule):
        if rrule._dtstart.tzinfo is not None:
            timezone = rrule._dtstart.tzinfo.name
        else:
            timezone = "UTC"
        return RRuleSchedule(rrule=str(rrule), timezone=timezone)

    @validator("rrule", pre=True, always=True)
    def set_start_date(cls, v, *, values, **kwargs):
        # if the rrule string doesn't include a start date, create one using `now`
        if "DTSTART" not in v:
            v = f'DTSTART{pendulum.now().strftime("%Y%m%dT%H%M%S")}\n{v}'
        return v

    @validator("timezone", always=True)
    def valid_timezone(cls, v):
        if v and v not in pendulum.tz.timezones:
            raise ValueError(f'Invalid timezone: "{v}"')
        elif v is None:
            return "UTC"
        return v

    def _rrule_dates_iterator(self):
        """Imitates cache logic in the rrule library"""
        rrule_obj = rrule.rrulestr(self.rrule, cache=True)
        if rrule_obj._cache_complete:
            gen = rrule_obj._cache
        else:
            gen = rrule_obj
        yield from gen

    async def get_dates(
        self,
        n: int = None,
        start: datetime.datetime = None,
        end: datetime.datetime = None,
    ) -> List[datetime.datetime]:
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

        dates = []
        counter = 0

        for next_date in self._rrule_dates_iterator():

            next_date = pendulum.instance(next_date)

            # if the start date has not been reached, continue
            if next_date < start:
                continue

            # if the end date was exceeded, exit
            if end and next_date > end:
                break

            dates.append(next_date)

            # if enough dates have been collected or enough attempts were made, exit
            if len(dates) >= n or counter > MAX_ITERATIONS:
                break

            counter += 1

            # yield event loop control
            await asyncio.sleep(0)

        return dates


SCHEDULE_TYPES = Union[IntervalSchedule, CronSchedule, RRuleSchedule]
