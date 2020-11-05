from typing import Any

from marshmallow import fields, post_dump, post_load

import prefect
from prefect.serialization import schedule_compat
from prefect.utilities.serialization import (
    DateTimeTZ,
    JSONCompatible,
    ObjectSchema,
    OneOfSchema,
    StatefulFunctionReference,
)

FILTERS = [
    prefect.schedules.filters.on_datetime,
    prefect.schedules.filters.on_date,
    prefect.schedules.filters.at_time,
    prefect.schedules.filters.between_datetimes,
    prefect.schedules.filters.between_dates,
    prefect.schedules.filters.between_times,
    prefect.schedules.filters.is_weekday,
    prefect.schedules.filters.is_weekend,
    prefect.schedules.filters.is_month_end,
    prefect.schedules.filters.is_day_of_week,
    prefect.schedules.filters.is_month_start,
]

ADJUSTMENTS = [
    prefect.schedules.adjustments.add,
    prefect.schedules.adjustments.next_weekday,
]


class IntervalClockSchema(ObjectSchema):
    class Meta:
        object_class = prefect.schedules.clocks.IntervalClock

    start_date = DateTimeTZ(allow_none=True)
    end_date = DateTimeTZ(allow_none=True)
    interval = fields.TimeDelta(precision="microseconds", required=True)
    parameter_defaults = fields.Dict(
        key=fields.Str(), values=JSONCompatible(), allow_none=True
    )
    labels = fields.List(fields.Str(), allow_none=True)

    @post_dump
    def _interval_validation(self, data: dict, **kwargs: Any) -> dict:
        """
        Ensures interval is at least one minute in length
        """
        if data["interval"] / 1e6 < 60:
            raise ValueError(
                "Interval can not be less than one minute when deploying to Prefect Cloud."
            )
        return data

    @post_load
    def create_object(self, data: dict, **kwargs: Any):
        if data["interval"].total_seconds() < 60:
            raise ValueError(
                "Interval can not be less than one minute when deploying to Prefect Cloud."
            )
        base_obj = super().create_object(data)
        return base_obj


class CronClockSchema(ObjectSchema):
    class Meta:
        object_class = prefect.schedules.clocks.CronClock

    start_date = DateTimeTZ(allow_none=True)
    end_date = DateTimeTZ(allow_none=True)
    cron = fields.String(required=True)
    parameter_defaults = fields.Dict(
        key=fields.Str(), values=JSONCompatible(), allow_none=True
    )
    labels = fields.List(fields.Str(), allow_none=True)
    day_or = fields.Boolean(allow_none=True)


class DatesClockSchema(ObjectSchema):
    class Meta:
        object_class = prefect.schedules.clocks.DatesClock

    dates = fields.List(DateTimeTZ(), required=True)
    parameter_defaults = fields.Dict(
        key=fields.Str(), values=JSONCompatible(), allow_none=True
    )
    labels = fields.List(fields.Str(), allow_none=True)


class ClockSchema(OneOfSchema):
    """
    Field that chooses between several nested schemas
    """

    # map class name to schema
    type_schemas = {
        "IntervalClock": IntervalClockSchema,
        "CronClock": CronClockSchema,
        "DatesClock": DatesClockSchema,
    }


class NewScheduleSchema(ObjectSchema):
    """
    This schedule schema is the "true" schedule schema; however we use a
    backwards-compatible one to support old-style schedules.
    """

    class Meta:
        object_class = prefect.schedules.Schedule

    clocks = fields.Nested(ClockSchema, required=True, many=True)
    filters = fields.List(
        StatefulFunctionReference(
            valid_functions=FILTERS, reject_invalid=True, allow_none=True
        )
    )
    or_filters = fields.List(
        StatefulFunctionReference(
            valid_functions=FILTERS, reject_invalid=True, allow_none=True
        )
    )
    not_filters = fields.List(
        StatefulFunctionReference(
            valid_functions=FILTERS, reject_invalid=True, allow_none=True
        )
    )
    adjustments = fields.List(
        StatefulFunctionReference(
            valid_functions=ADJUSTMENTS, reject_invalid=True, allow_none=True
        )
    )


class ScheduleSchema(OneOfSchema):
    """
    Field that chooses between several nested schemas. This class is preserved for pre-0.6.1
    compatibility, and is deprecated in favor of NewScheduleSchema.
    """

    # map class name to schema
    type_schemas = {
        "Schedule": NewScheduleSchema,
        "IntervalSchedule": schedule_compat.IntervalScheduleSchema,
        "CronSchedule": schedule_compat.CronScheduleSchema,
        "OneTimeSchedule": schedule_compat.OneTimeScheduleSchema,
        "UnionSchedule": schedule_compat.UnionScheduleSchema,
    }
