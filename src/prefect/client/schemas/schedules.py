"""
Schedule schemas
"""

import datetime
from typing import TYPE_CHECKING, Annotated, Any, ClassVar, Optional, Union
from zoneinfo import ZoneInfo

import dateutil
import dateutil.rrule
import dateutil.tz
from pydantic import AfterValidator, ConfigDict, Field, field_validator, model_validator
from typing_extensions import TypeAlias, TypeGuard

from prefect._internal.schemas.bases import PrefectBaseModel
from prefect._internal.schemas.validators import (
    default_anchor_date,
    default_timezone,
    validate_cron_string,
    validate_rrule_string,
)
from prefect.types._datetime import Date, DateTime, now

MAX_ITERATIONS = 1000
# approx. 1 years worth of RDATEs + buffer
MAX_RRULE_LENGTH = 6500


def is_valid_timezone(v: str) -> bool:
    """
    Validate that the provided timezone is a valid IANA timezone.

    Unfortunately this list is slightly different from the list of valid
    timezones we use for cron and interval timezone validation.
    """
    from prefect._internal.pytz import HAS_PYTZ

    if HAS_PYTZ:
        import pytz
    else:
        from prefect._internal import pytz

    return v in pytz.all_timezones_set


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
        anchor_date (DateTime, optional): an anchor date to schedule increments against;
            if not provided, the current timestamp will be used
        timezone (str, optional): a valid timezone string
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    interval: datetime.timedelta = Field(gt=datetime.timedelta(0))
    anchor_date: Annotated[DateTime, AfterValidator(default_anchor_date)] = Field(  # pyright: ignore[reportAssignmentType] DateTime is split into two types depending on Python version
        default_factory=lambda: now("UTC"),
        examples=["2020-01-01T00:00:00Z"],
    )
    timezone: Optional[str] = Field(default=None, examples=["America/New_York"])

    @model_validator(mode="after")
    def validate_timezone(self):
        self.timezone = default_timezone(self.timezone, self.model_dump())
        return self

    if TYPE_CHECKING:
        # The model accepts str or datetime values for `anchor_date`
        def __init__(
            self,
            /,
            interval: datetime.timedelta,
            anchor_date: Optional[Union[DateTime, datetime.datetime, str]] = None,
            timezone: Optional[str] = None,
        ) -> None: ...


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

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, v: Optional[str]) -> Optional[str]:
        return default_timezone(v)

    @field_validator("cron")
    @classmethod
    def valid_cron_string(cls, v: str) -> str:
        return validate_cron_string(v)


DEFAULT_ANCHOR_DATE = Date(2020, 1, 1)


def _rrule_dt(
    rrule: dateutil.rrule.rrule, name: str = "_dtstart"
) -> Optional[datetime.datetime]:
    return getattr(rrule, name, None)


def _rrule(
    rruleset: dateutil.rrule.rruleset, name: str = "_rrule"
) -> list[dateutil.rrule.rrule]:
    return getattr(rruleset, name, [])


def _rdates(
    rrule: dateutil.rrule.rruleset, name: str = "_rdate"
) -> list[datetime.datetime]:
    return getattr(rrule, name, [])


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
    timezone: Optional[str] = Field(
        default="UTC", examples=["America/New_York"], validate_default=True
    )

    @field_validator("rrule")
    @classmethod
    def validate_rrule_str(cls, v: str) -> str:
        return validate_rrule_string(v)

    @classmethod
    def from_rrule(
        cls, rrule: Union[dateutil.rrule.rrule, dateutil.rrule.rruleset]
    ) -> "RRuleSchedule":
        if isinstance(rrule, dateutil.rrule.rrule):
            dtstart = _rrule_dt(rrule)
            if dtstart and dtstart.tzinfo is not None:
                timezone = dtstart.tzinfo.tzname(dtstart)
            else:
                timezone = "UTC"
            return RRuleSchedule(rrule=str(rrule), timezone=timezone)
        rrules = _rrule(rrule)
        dtstarts = [dts for rr in rrules if (dts := _rrule_dt(rr)) is not None]
        unique_dstarts = set(d.astimezone(ZoneInfo("UTC")) for d in dtstarts)
        unique_timezones = set(d.tzinfo for d in dtstarts if d.tzinfo is not None)

        if len(unique_timezones) > 1:
            raise ValueError(
                f"rruleset has too many dtstart timezones: {unique_timezones}"
            )

        if len(unique_dstarts) > 1:
            raise ValueError(f"rruleset has too many dtstarts: {unique_dstarts}")

        if unique_dstarts and unique_timezones:
            [unique_tz] = unique_timezones
            timezone = unique_tz.tzname(dtstarts[0])
        else:
            timezone = "UTC"

        rruleset_string = ""
        if rrules:
            rruleset_string += "\n".join(str(r) for r in rrules)
        if exrule := _rrule(rrule, "_exrule"):
            rruleset_string += "\n" if rruleset_string else ""
            rruleset_string += "\n".join(str(r) for r in exrule).replace(
                "RRULE", "EXRULE"
            )
        if rdates := _rdates(rrule):
            rruleset_string += "\n" if rruleset_string else ""
            rruleset_string += "RDATE:" + ",".join(
                rd.strftime("%Y%m%dT%H%M%SZ") for rd in rdates
            )
        if exdates := _rdates(rrule, "_exdate"):
            rruleset_string += "\n" if rruleset_string else ""
            rruleset_string += "EXDATE:" + ",".join(
                exd.strftime("%Y%m%dT%H%M%SZ") for exd in exdates
            )
        return RRuleSchedule(rrule=rruleset_string, timezone=timezone)

    def to_rrule(self) -> Union[dateutil.rrule.rrule, dateutil.rrule.rruleset]:
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
            dtstart = _rrule_dt(rrule)
            assert dtstart is not None
            kwargs: dict[str, Any] = dict(dtstart=dtstart.replace(tzinfo=timezone))
            if until := _rrule_dt(rrule, "_until"):
                kwargs.update(
                    until=until.replace(tzinfo=timezone),
                )
            return rrule.replace(**kwargs)  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType] missing type hints

        # update rrules
        localized_rrules: list[dateutil.rrule.rrule] = []
        for rr in _rrule(rrule):
            dtstart = _rrule_dt(rr)
            assert dtstart is not None
            kwargs: dict[str, Any] = dict(dtstart=dtstart.replace(tzinfo=timezone))
            if until := _rrule_dt(rr, "_until"):
                kwargs.update(until=until.replace(tzinfo=timezone))
            localized_rrules.append(rr.replace(**kwargs))  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType] missing type hints
        setattr(rrule, "_rrule", localized_rrules)

        # update exrules
        localized_exrules: list[dateutil.rrule.rruleset] = []
        for exr in _rrule(rrule, "_exrule"):
            dtstart = _rrule_dt(exr)
            assert dtstart is not None
            kwargs = dict(dtstart=dtstart.replace(tzinfo=timezone))
            if until := _rrule_dt(exr, "_until"):
                kwargs.update(until=until.replace(tzinfo=timezone))
            localized_exrules.append(exr.replace(**kwargs))  # pyright: ignore[reportUnknownArgumentType, reportUnknownMemberType] missing type hints
        setattr(rrule, "_exrule", localized_exrules)

        # update rdates
        localized_rdates: list[datetime.datetime] = []
        for rd in _rdates(rrule):
            localized_rdates.append(rd.replace(tzinfo=timezone))
        setattr(rrule, "_rdate", localized_rdates)

        # update exdates
        localized_exdates: list[datetime.datetime] = []
        for exd in _rdates(rrule, "_exdate"):
            localized_exdates.append(exd.replace(tzinfo=timezone))
        setattr(rrule, "_exdate", localized_exdates)

        return rrule

    @field_validator("timezone")
    def valid_timezone(cls, v: Optional[str]) -> str:
        """
        Validate that the provided timezone is a valid IANA timezone.

        Unfortunately this list is slightly different from the list of valid
        timezones we use for cron and interval timezone validation.
        """
        if v is None:
            return "UTC"

        if is_valid_timezone(v):
            return v

        raise ValueError(f'Invalid timezone: "{v}"')


class NoSchedule(PrefectBaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")


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
            anchor_date = now()
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
