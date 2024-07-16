from typing import Optional

from pydantic import ConfigDict, Field, field_validator

from prefect._internal.schemas.bases import PrefectBaseModel
from prefect._internal.schemas.validators import (
    default_timezone,
    validate_cron_string,
)


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

    model_config = ConfigDict(extra="forbid")

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
    def valid_timezone(cls, v):
        return default_timezone(v)

    @field_validator("cron")
    @classmethod
    def valid_cron_string(cls, v):
        return validate_cron_string(v)
