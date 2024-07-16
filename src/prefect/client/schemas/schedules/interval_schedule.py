import datetime
from typing import Annotated, Optional

import pendulum
from pydantic import AfterValidator, ConfigDict, Field, model_validator
from pydantic_extra_types.pendulum_dt import DateTime

from prefect._internal.schemas.bases import PrefectBaseModel
from prefect._internal.schemas.validators import (
    default_anchor_date,
    default_timezone,
)


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

    model_config = ConfigDict(extra="forbid", exclude_none=True)

    interval: datetime.timedelta = Field(gt=datetime.timedelta(0))
    anchor_date: Annotated[DateTime, AfterValidator(default_anchor_date)] = Field(
        default_factory=lambda: pendulum.now("UTC"),
        examples=["2020-01-01T00:00:00Z"],
    )
    timezone: Optional[str] = Field(default=None, examples=["America/New_York"])

    @model_validator(mode="after")
    def validate_timezone(self):
        self.timezone = default_timezone(self.timezone, self.model_dump())
        return self
