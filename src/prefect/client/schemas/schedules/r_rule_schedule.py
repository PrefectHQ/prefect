from typing import Optional

import dateutil
import dateutil.rrule
import pendulum
from pydantic import ConfigDict, Field, field_validator

from prefect._internal.schemas.bases import PrefectBaseModel
from prefect._internal.schemas.validators import (
    validate_rrule_string,
)

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

    model_config = ConfigDict(extra="forbid")

    rrule: str
    timezone: Optional[str] = Field(
        default="UTC", examples=["America/New_York"], validate_default=True
    )

    @field_validator("rrule")
    @classmethod
    def validate_rrule_str(cls, v):
        return validate_rrule_string(v)

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

    @field_validator("timezone")
    def valid_timezone(cls, v):
        """
        Validate that the provided timezone is a valid IANA timezone.

        Unfortunately this list is slightly different from the list of valid
        timezones in pendulum that we use for cron and interval timezone validation.
        """
        from prefect._internal.pytz import HAS_PYTZ

        if HAS_PYTZ:
            import pytz
        else:
            from prefect._internal import pytz

        if v and v not in pytz.all_timezones_set:
            raise ValueError(f'Invalid timezone: "{v}"')
        elif v is None:
            return "UTC"
        return v
