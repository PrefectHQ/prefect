"""
Schedule schemas
"""

from __future__ import annotations

import datetime
import sys
from typing import (
    Annotated,
    Any,
    ClassVar,
    Generator,
    List,
    Optional,
    Tuple,
    Union,
)
from zoneinfo import ZoneInfo

import dateutil
import dateutil.rrule
import pytz
from pydantic import ConfigDict, Field, field_validator, model_validator
from typing_extensions import TypeAlias

from prefect._internal.schemas.validators import (
    default_timezone,
    validate_cron_string,
    validate_rrule_string,
)
from prefect._vendor.croniter import croniter
from prefect.server.utilities.schemas.bases import PrefectBaseModel
from prefect.types import DateTime, TimeZone
from prefect.types._datetime import create_datetime_instance, now

MAX_ITERATIONS = 1000

if sys.version_info >= (3, 13):
    AnchorDate: TypeAlias = datetime.datetime
else:
    from pydantic import AfterValidator

    from prefect._internal.schemas.validators import default_anchor_date

    AnchorDate: TypeAlias = Annotated[DateTime, AfterValidator(default_anchor_date)]


def _prepare_scheduling_start_and_end(
    start: Any, end: Any, timezone: str
) -> Tuple[DateTime, Optional[DateTime]]:
    """Uniformly prepares the start and end dates for any Schedule's get_dates call,
    coercing the arguments into timezone-aware datetimes."""
    timezone = timezone or "UTC"

    if start is not None:
        if sys.version_info >= (3, 13):
            start = create_datetime_instance(start).astimezone(ZoneInfo(timezone))
        else:
            start = create_datetime_instance(start).in_tz(timezone)

    if end is not None:
        if sys.version_info >= (3, 13):
            end = create_datetime_instance(end).astimezone(ZoneInfo(timezone))
        else:
            end = create_datetime_instance(end).in_tz(timezone)

    return start, end


class IntervalSchedule(PrefectBaseModel):
    """
    A schedule formed by adding `interval` increments to an `anchor_date`. If no
    `anchor_date` is supplied, the current UTC time is used.  If a
    timezone-naive datetime is provided for `anchor_date`, it is assumed to be
    in the schedule's timezone (or UTC). Even if supplied with an IANA timezone,
    anchor dates are always stored as UTC offsets, so a `timezone` can be
    provided to determine localization behaviors like DST boundary handling. If
    none is provided it will be inferred from the anchor date.

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

    Args:
        interval (datetime.timedelta): an interval to schedule on.
        anchor_date (DateTime, optional): an anchor date to schedule increments against;
            if not provided, the current timestamp will be used.
        timezone (str, optional): a valid timezone string.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    interval: datetime.timedelta = Field(gt=datetime.timedelta(0))
    anchor_date: AnchorDate = Field(
        default_factory=lambda: now("UTC"),
        examples=["2020-01-01T00:00:00Z"],
    )
    timezone: Optional[str] = Field(default=None, examples=["America/New_York"])

    @model_validator(mode="after")
    def validate_timezone(self):
        self.timezone = default_timezone(self.timezone, self.model_dump())
        return self

    async def get_dates(
        self,
        n: Optional[int] = None,
        start: Optional[datetime.datetime] = None,
        end: Optional[datetime.datetime] = None,
    ) -> List[DateTime]:
        """Retrieves dates from the schedule. Up to 1,000 candidate dates are checked
        following the start date.

        Args:
            n (int): The number of dates to generate
            start (datetime.datetime, optional): The first returned date will be on or
                after this date. Defaults to None.  If a timezone-naive datetime is
                provided, it is assumed to be in the schedule's timezone.
            end (datetime.datetime, optional): The maximum scheduled date to return. If
                a timezone-naive datetime is provided, it is assumed to be in the
                schedule's timezone.

        Returns:
            List[DateTime]: A list of dates
        """
        return sorted(self._get_dates_generator(n=n, start=start, end=end))

    def _get_dates_generator(
        self,
        n: Optional[int] = None,
        start: Optional[datetime.datetime] = None,
        end: Optional[datetime.datetime] = None,
    ) -> Generator[DateTime, None, None]:
        """Retrieves dates from the schedule. Up to 1,000 candidate dates are checked
        following the start date.

        Args:
            n (Optional[int]): The number of dates to generate
            start (Optional[datetime.datetime]): The first returned date will be on or
                after this date. Defaults to None.  If a timezone-naive datetime is
                provided, it is assumed to be in the schedule's timezone.
            end (Optional[datetime.datetime]): The maximum scheduled date to return. If
                a timezone-naive datetime is provided, it is assumed to be in the
                schedule's timezone.

        Returns:
            List[DateTime]: a list of dates
        """
        if n is None:
            # if an end was supplied, we do our best to supply all matching dates (up to
            # MAX_ITERATIONS)
            if end is not None:
                n = MAX_ITERATIONS
            else:
                n = 1

        if sys.version_info >= (3, 13):
            # `pendulum` is not supported in Python 3.13, so we use `whenever` instead
            from whenever import LocalDateTime, ZonedDateTime

            if start is None:
                start = ZonedDateTime.now("UTC").py_datetime()

            if self.anchor_date.tzinfo is None:
                anchor_zdt = LocalDateTime.from_py_datetime(self.anchor_date).assume_tz(
                    "UTC"
                )
            elif isinstance(self.anchor_date.tzinfo, ZoneInfo):
                anchor_zdt = ZonedDateTime.from_py_datetime(self.anchor_date).to_tz(
                    self.timezone or "UTC"
                )
            else:
                # This case handles rogue tzinfo objects that `whenever` doesn't play will with
                anchor_zdt = ZonedDateTime.from_py_datetime(
                    self.anchor_date.replace(
                        tzinfo=ZoneInfo(self.anchor_date.tzname() or "UTC")
                    )
                ).to_tz(self.timezone or "UTC")

            if start.tzinfo is None:
                local_start = LocalDateTime.from_py_datetime(start).assume_tz("UTC")
            elif isinstance(start.tzinfo, ZoneInfo):
                local_start = ZonedDateTime.from_py_datetime(start).to_tz(
                    self.timezone or "UTC"
                )
            else:
                local_start = ZonedDateTime.from_py_datetime(
                    start.replace(tzinfo=ZoneInfo(start.tzname() or "UTC"))
                ).to_tz(self.timezone or "UTC")

            if end is None:
                local_end = None
            elif isinstance(end.tzinfo, ZoneInfo):
                local_end = ZonedDateTime.from_py_datetime(end).to_tz(
                    self.timezone or "UTC"
                )
            else:
                local_end = ZonedDateTime.from_py_datetime(
                    end.replace(tzinfo=ZoneInfo(end.tzname() or "UTC"))
                ).to_tz(self.timezone or "UTC")

            offset = (
                local_start - anchor_zdt
            ).in_seconds() / self.interval.total_seconds()
            next_date = anchor_zdt.add(
                seconds=self.interval.total_seconds() * int(offset)
            )

            # break the interval into `days` and `seconds` because the datetime
            # library will handle DST boundaries properly if days are provided, but not
            # if we add `total seconds`. Therefore, `next_date + self.interval`
            # fails while `next_date.add(days=days, seconds=seconds)` works.
            interval_days = self.interval.days
            interval_seconds = self.interval.total_seconds() - (
                interval_days * 24 * 60 * 60
            )

            while next_date < local_start:
                next_date = next_date.add(days=interval_days, seconds=interval_seconds)

            counter = 0
            dates: set[ZonedDateTime] = set()

            while True:
                # if the end date was exceeded, exit
                if local_end and next_date > local_end:
                    break

                # ensure no duplicates; weird things can happen with DST
                if next_date not in dates:
                    dates.add(next_date)
                    yield next_date.py_datetime()

                # if enough dates have been collected or enough attempts were made, exit
                if len(dates) >= n or counter > MAX_ITERATIONS:
                    break

                counter += 1

                next_date = next_date.add(days=interval_days, seconds=interval_seconds)

        else:
            if start is None:
                start = now("UTC")
            anchor_tz = self.anchor_date.in_tz(self.timezone)
            start, end = _prepare_scheduling_start_and_end(start, end, self.timezone)

            # compute the offset between the anchor date and the start date to jump to the
            # next date
            offset = (start - anchor_tz).total_seconds() / self.interval.total_seconds()
            next_date = anchor_tz.add(
                seconds=self.interval.total_seconds() * int(offset)
            )

            # break the interval into `days` and `seconds` because the datetime
            # library will handle DST boundaries properly if days are provided, but not
            # if we add `total seconds`. Therefore, `next_date + self.interval`
            # fails while `next_date.add(days=days, seconds=seconds)` works.
            interval_days = self.interval.days
            interval_seconds = self.interval.total_seconds() - (
                interval_days * 24 * 60 * 60
            )

            # daylight saving time boundaries can create a situation where the next date is
            # before the start date, so we advance it if necessary
            while next_date < start:
                next_date = next_date.add(days=interval_days, seconds=interval_seconds)

            counter = 0
            dates = set()

            while True:
                # if the end date was exceeded, exit
                if end and next_date > end:
                    break

                # ensure no duplicates; weird things can happen with DST
                if next_date not in dates:
                    dates.add(next_date)
                    yield next_date

                # if enough dates have been collected or enough attempts were made, exit
                if len(dates) >= n or counter > MAX_ITERATIONS:
                    break

                counter += 1

                next_date = next_date.add(days=interval_days, seconds=interval_seconds)


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
        timezone (str): a valid timezone string in IANA tzdata format (for example,
            America/New_York).
        day_or (bool, optional): Control how croniter handles `day` and `day_of_week`
            entries. Defaults to True, matching cron which connects those values using
            OR. If the switch is set to False, the values are connected using AND. This
            behaves like fcron and enables you to e.g. define a job that executes each
            2nd friday of a month by setting the days of month and the weekday.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    cron: str = Field(default=..., examples=["0 0 * * *"])
    timezone: Optional[str] = Field(default=None, examples=["America/New_York"])
    day_or: bool = Field(
        default=True,
        description=(
            "Control croniter behavior for handling day and day_of_week entries."
        ),
    )

    @model_validator(mode="after")
    def validate_timezone(self):
        self.timezone = default_timezone(self.timezone, self.model_dump())
        return self

    @field_validator("cron")
    @classmethod
    def valid_cron_string(cls, v: str) -> str:
        return validate_cron_string(v)

    async def get_dates(
        self,
        n: Optional[int] = None,
        start: Optional[datetime.datetime] = None,
        end: Optional[datetime.datetime] = None,
    ) -> List[DateTime]:
        """Retrieves dates from the schedule. Up to 1,000 candidate dates are checked
        following the start date.

        Args:
            n (int): The number of dates to generate
            start (datetime.datetime, optional): The first returned date will be on or
                after this date. Defaults to None.  If a timezone-naive datetime is
                provided, it is assumed to be in the schedule's timezone.
            end (datetime.datetime, optional): The maximum scheduled date to return. If
                a timezone-naive datetime is provided, it is assumed to be in the
                schedule's timezone.

        Returns:
            List[DateTime]: A list of dates
        """
        return sorted(self._get_dates_generator(n=n, start=start, end=end))

    def _get_dates_generator(
        self,
        n: Optional[int] = None,
        start: Optional[datetime.datetime] = None,
        end: Optional[datetime.datetime] = None,
    ) -> Generator[DateTime, None, None]:
        """Retrieves dates from the schedule. Up to 1,000 candidate dates are checked
        following the start date.

        Args:
            n (int): The number of dates to generate
            start (datetime.datetime, optional): The first returned date will be on or
                after this date. Defaults to the current date. If a timezone-naive
                datetime is provided, it is assumed to be in the schedule's timezone.
            end (datetime.datetime, optional): No returned date will exceed this date.
                If a timezone-naive datetime is provided, it is assumed to be in the
                schedule's timezone.

        Returns:
            List[DateTime]: a list of dates
        """
        if start is None:
            start = now("UTC")

        start, end = _prepare_scheduling_start_and_end(start, end, self.timezone)

        if n is None:
            # if an end was supplied, we do our best to supply all matching dates (up to
            # MAX_ITERATIONS)
            if end is not None:
                n = MAX_ITERATIONS
            else:
                n = 1

        if self.timezone:
            if sys.version_info >= (3, 13):
                start = start.astimezone(ZoneInfo(self.timezone or "UTC"))
            else:
                start = start.in_tz(self.timezone)

        # subtract one second from the start date, so that croniter returns it
        # as an event (if it meets the cron criteria)
        start = start - datetime.timedelta(seconds=1)

        # Respect microseconds by rounding up
        if start.microsecond > 0:
            start += datetime.timedelta(seconds=1)

        # croniter's DST logic interferes with all other datetime libraries except pytz
        if sys.version_info >= (3, 13):
            start_localized = start.astimezone(ZoneInfo(self.timezone or "UTC"))
            start_naive_tz = start.replace(tzinfo=None)
        else:
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
            start_naive_tz = start.naive()

        cron = croniter(self.cron, start_naive_tz, day_or=self.day_or)  # type: ignore
        dates = set()
        counter = 0

        while True:
            # croniter does not handle DST properly when the start time is
            # in and around when the actual shift occurs. To work around this,
            # we use the naive start time to get the next cron date delta, then
            # add that time to the original scheduling anchor.
            next_time = cron.get_next(datetime.datetime)
            delta = next_time - start_naive_tz
            if sys.version_info >= (3, 13):
                from whenever import ZonedDateTime

                # Use `whenever` to handle DST correctly
                next_date = (
                    ZonedDateTime.from_py_datetime(start_localized + delta)
                    .to_tz(self.timezone or "UTC")
                    .py_datetime()
                )
            else:
                next_date = create_datetime_instance(start_localized + delta)

            # if the end date was exceeded, exit
            if end and next_date > end:
                break
            # ensure no duplicates; weird things can happen with DST
            if next_date not in dates:
                dates.add(next_date)
                yield next_date

            # if enough dates have been collected or enough attempts were made, exit
            if len(dates) >= n or counter > MAX_ITERATIONS:
                break

            counter += 1


DEFAULT_ANCHOR_DATE = datetime.date(2020, 1, 1)


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

    Args:
        rrule (str): a valid RRule string
        timezone (str, optional): a valid timezone string
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    rrule: str
    timezone: Optional[TimeZone] = Field(default="UTC", examples=["America/New_York"])

    @field_validator("rrule")
    @classmethod
    def validate_rrule_str(cls, v: str) -> str:
        return validate_rrule_string(v)

    @classmethod
    def from_rrule(
        cls, rrule: dateutil.rrule.rrule | dateutil.rrule.rruleset
    ) -> "RRuleSchedule":
        if isinstance(rrule, dateutil.rrule.rrule):
            if rrule._dtstart.tzinfo is not None:
                timezone = getattr(rrule._dtstart.tzinfo, "name", None) or getattr(
                    rrule._dtstart.tzinfo, "key", "UTC"
                )
            else:
                timezone = "UTC"
            return RRuleSchedule(rrule=str(rrule), timezone=timezone)
        elif isinstance(rrule, dateutil.rrule.rruleset):
            dtstarts = [rr._dtstart for rr in rrule._rrule if rr._dtstart is not None]
            unique_dstarts = set(
                create_datetime_instance(d).astimezone(ZoneInfo("UTC"))
                for d in dtstarts
            )
            unique_timezones = set(d.tzinfo for d in dtstarts if d.tzinfo is not None)

            if len(unique_timezones) > 1:
                raise ValueError(
                    f"rruleset has too many dtstart timezones: {unique_timezones}"
                )

            if len(unique_dstarts) > 1:
                raise ValueError(f"rruleset has too many dtstarts: {unique_dstarts}")

            if unique_dstarts and unique_timezones:
                tzinfo = dtstarts[0].tzinfo
                timezone = getattr(tzinfo, "name", None) or getattr(
                    tzinfo, "key", "UTC"
                )
            else:
                timezone = "UTC"

            rruleset_string = ""
            if rrule._rrule:
                rruleset_string += "\n".join(str(r) for r in rrule._rrule)
            if rrule._exrule:
                rruleset_string += "\n" if rruleset_string else ""
                rruleset_string += "\n".join(str(r) for r in rrule._exrule).replace(
                    "RRULE", "EXRULE"
                )
            if rrule._rdate:
                rruleset_string += "\n" if rruleset_string else ""
                rruleset_string += "RDATE:" + ",".join(
                    rd.strftime("%Y%m%dT%H%M%SZ") for rd in rrule._rdate
                )
            if rrule._exdate:
                rruleset_string += "\n" if rruleset_string else ""
                rruleset_string += "EXDATE:" + ",".join(
                    exd.strftime("%Y%m%dT%H%M%SZ") for exd in rrule._exdate
                )
            return RRuleSchedule(rrule=rruleset_string, timezone=timezone)
        else:
            raise ValueError(f"Invalid RRule object: {rrule}")

    def to_rrule(self) -> dateutil.rrule.rrule:
        """
        Since rrule doesn't properly serialize/deserialize timezones, we localize dates
        here
        """
        rrule = dateutil.rrule.rrulestr(
            self.rrule,
            dtstart=DEFAULT_ANCHOR_DATE,
            cache=True,
        )
        timezone = dateutil.tz.gettz(self.timezone)
        if isinstance(rrule, dateutil.rrule.rrule):
            kwargs = dict(dtstart=rrule._dtstart.replace(tzinfo=timezone))
            if rrule._until:
                kwargs.update(
                    until=rrule._until.replace(tzinfo=timezone),
                )
            return rrule.replace(**kwargs)
        elif isinstance(rrule, dateutil.rrule.rruleset):
            # update rrules
            localized_rrules = []
            for rr in rrule._rrule:
                kwargs = dict(dtstart=rr._dtstart.replace(tzinfo=timezone))
                if rr._until:
                    kwargs.update(
                        until=rr._until.replace(tzinfo=timezone),
                    )
                localized_rrules.append(rr.replace(**kwargs))
            rrule._rrule = localized_rrules

            # update exrules
            localized_exrules = []
            for exr in rrule._exrule:
                kwargs = dict(dtstart=exr._dtstart.replace(tzinfo=timezone))
                if exr._until:
                    kwargs.update(
                        until=exr._until.replace(tzinfo=timezone),
                    )
                localized_exrules.append(exr.replace(**kwargs))
            rrule._exrule = localized_exrules

            # update rdates
            localized_rdates = []
            for rd in rrule._rdate:
                localized_rdates.append(rd.replace(tzinfo=timezone))
            rrule._rdate = localized_rdates

            # update exdates
            localized_exdates = []
            for exd in rrule._exdate:
                localized_exdates.append(exd.replace(tzinfo=timezone))
            rrule._exdate = localized_exdates

            return rrule

    async def get_dates(
        self,
        n: Optional[int] = None,
        start: datetime.datetime = None,
        end: datetime.datetime = None,
    ) -> List[DateTime]:
        """Retrieves dates from the schedule. Up to 1,000 candidate dates are checked
        following the start date.

        Args:
            n (int): The number of dates to generate
            start (datetime.datetime, optional): The first returned date will be on or
                after this date. Defaults to None.  If a timezone-naive datetime is
                provided, it is assumed to be in the schedule's timezone.
            end (datetime.datetime, optional): The maximum scheduled date to return. If
                a timezone-naive datetime is provided, it is assumed to be in the
                schedule's timezone.

        Returns:
            List[DateTime]: A list of dates
        """
        return sorted(self._get_dates_generator(n=n, start=start, end=end))

    def _get_dates_generator(
        self,
        n: Optional[int] = None,
        start: Optional[datetime.datetime] = None,
        end: Optional[datetime.datetime] = None,
    ) -> Generator[DateTime, None, None]:
        """Retrieves dates from the schedule. Up to 1,000 candidate dates are checked
        following the start date.

        Args:
            n (int): The number of dates to generate
            start (datetime.datetime, optional): The first returned date will be on or
                after this date. Defaults to the current date. If a timezone-naive
                datetime is provided, it is assumed to be in the schedule's timezone.
            end (datetime.datetime, optional): No returned date will exceed this date.
                If a timezone-naive datetime is provided, it is assumed to be in the
                schedule's timezone.

        Returns:
            List[DateTime]: a list of dates
        """
        if start is None:
            start = now("UTC")

        start, end = _prepare_scheduling_start_and_end(start, end, self.timezone)

        if n is None:
            # if an end was supplied, we do our best to supply all matching dates (up
            # to MAX_ITERATIONS)
            if end is not None:
                n = MAX_ITERATIONS
            else:
                n = 1

        dates = set()
        counter = 0

        # pass count = None to account for discrepancies with duplicates around DST
        # boundaries
        for next_date in self.to_rrule().xafter(start, count=None, inc=True):
            next_date = create_datetime_instance(next_date).astimezone(
                ZoneInfo(self.timezone)
            )

            # if the end date was exceeded, exit
            if end and next_date > end:
                break

            # ensure no duplicates; weird things can happen with DST
            if next_date not in dates:
                dates.add(next_date)
                yield next_date

            # if enough dates have been collected or enough attempts were made, exit
            if len(dates) >= n or counter > MAX_ITERATIONS:
                break

            counter += 1


SCHEDULE_TYPES = Union[IntervalSchedule, CronSchedule, RRuleSchedule]
