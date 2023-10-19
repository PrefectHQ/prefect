"""
Schedule schemas
"""

import datetime
from typing import Optional, Union

import dateutil
import dateutil.rrule
import pendulum
from croniter import croniter

from prefect._internal.pydantic import HAS_PYDANTIC_V2

if HAS_PYDANTIC_V2:
    from pydantic.v1 import Field, validator
else:
    from pydantic import Field, validator

from prefect._internal.pytz import HAS_PYTZ

if HAS_PYTZ:
    import pytz
else:
    from prefect._internal import pytz


from prefect._internal.schemas.bases import PrefectBaseModel
from prefect._internal.schemas.fields import DateTimeTZ

MAX_ITERATIONS = 1000
# approx. 1 years worth of RDATEs + buffer
MAX_RRULE_LENGTH = 6500


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
        interval (datetime.timedelta): an interval to schedule on
        anchor_date (DateTimeTZ, optional): an anchor date to schedule increments against;
            if not provided, the current timestamp will be used
        timezone (str, optional): a valid timezone string
    """

    class Config:
        extra = "forbid"
        exclude_none = True

    interval: datetime.timedelta
    anchor_date: DateTimeTZ = None
    timezone: Optional[str] = Field(default=None, example="America/New_York")

    @validator("interval")
    def interval_must_be_positive(cls, v):
        if v.total_seconds() <= 0:
            raise ValueError("The interval must be positive")
        return v

    @validator("anchor_date", always=True)
    def default_anchor_date(cls, v):
        if v is None:
            return pendulum.now("UTC")
        return pendulum.instance(v)

    @validator("timezone", always=True)
    def default_timezone(cls, v, *, values, **kwargs):
        # if was provided, make sure its a valid IANA string
        if v and v not in pendulum.tz.timezones:
            raise ValueError(f'Invalid timezone: "{v}"')

        # otherwise infer the timezone from the anchor date
        elif v is None and values.get("anchor_date"):
            tz = values["anchor_date"].tz.name
            if tz in pendulum.tz.timezones:
                return tz
            # sometimes anchor dates have "timezones" that are UTC offsets
            # like "-04:00". This happens when parsing ISO8601 strings.
            # In this case we, the correct inferred localization is "UTC".
            else:
                return "UTC"

        return v


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

    class Config:
        extra = "forbid"

    cron: str = Field(default=..., example="0 0 * * *")
    timezone: Optional[str] = Field(default=None, example="America/New_York")
    day_or: bool = Field(
        default=True,
        description=(
            "Control croniter behavior for handling day and day_of_week entries."
        ),
    )

    @validator("timezone")
    def valid_timezone(cls, v):
        if v and v not in pendulum.tz.timezones:
            raise ValueError(
                f'Invalid timezone: "{v}" (specify in IANA tzdata format, for example,'
                " America/New_York)"
            )
        return v

    @validator("cron")
    def valid_cron_string(cls, v):
        # croniter allows "random" and "hashed" expressions
        # which we do not support https://github.com/kiorky/croniter
        if not croniter.is_valid(v):
            raise ValueError(f'Invalid cron string: "{v}"')
        elif any(c for c in v.split() if c.casefold() in ["R", "H", "r", "h"]):
            raise ValueError(
                f'Random and Hashed expressions are unsupported, received: "{v}"'
            )
        return v


DEFAULT_ANCHOR_DATE = pendulum.date(2020, 1, 1)


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

    class Config:
        extra = "forbid"

    rrule: str
    timezone: Optional[str] = Field(default=None, example="America/New_York")

    @validator("rrule")
    def validate_rrule_str(cls, v):
        # attempt to parse the rrule string as an rrule object
        # this will error if the string is invalid
        try:
            dateutil.rrule.rrulestr(v, cache=True)
        except ValueError as exc:
            # rrules errors are a mix of cryptic and informative
            # so reraise to be clear that the string was invalid
            raise ValueError(f'Invalid RRule string "{v}": {exc}')
        if len(v) > MAX_RRULE_LENGTH:
            raise ValueError(
                f'Invalid RRule string "{v[:40]}..."\n'
                f"Max length is {MAX_RRULE_LENGTH}, got {len(v)}"
            )
        return v

    @classmethod
    def from_rrule(cls, rrule: dateutil.rrule.rrule):
        if isinstance(rrule, dateutil.rrule.rrule):
            if rrule._dtstart.tzinfo is not None:
                timezone = rrule._dtstart.tzinfo.name
            else:
                timezone = "UTC"
            return RRuleSchedule(rrule=str(rrule), timezone=timezone)
        elif isinstance(rrule, dateutil.rrule.rruleset):
            dtstarts = [rr._dtstart for rr in rrule._rrule if rr._dtstart is not None]
            unique_dstarts = set(pendulum.instance(d).in_tz("UTC") for d in dtstarts)
            unique_timezones = set(d.tzinfo for d in dtstarts if d.tzinfo is not None)

            if len(unique_timezones) > 1:
                raise ValueError(
                    f"rruleset has too many dtstart timezones: {unique_timezones}"
                )

            if len(unique_dstarts) > 1:
                raise ValueError(f"rruleset has too many dtstarts: {unique_dstarts}")

            if unique_dstarts and unique_timezones:
                timezone = dtstarts[0].tzinfo.name
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

    @validator("timezone", always=True)
    def valid_timezone(cls, v):
        if v and v not in pytz.all_timezones_set:
            raise ValueError(f'Invalid timezone: "{v}"')
        elif v is None:
            return "UTC"
        return v


SCHEDULE_TYPES = Union[IntervalSchedule, CronSchedule, RRuleSchedule]


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
