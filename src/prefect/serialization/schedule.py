import warnings
from typing import TYPE_CHECKING, Any

import marshmallow
from marshmallow import fields, post_load

import prefect
from prefect.schedules import schedules, old_schedules
from prefect.serialization import old_schedule
from prefect.utilities.serialization import (
    DateTimeTZ,
    ObjectSchema,
    OneOfSchema,
    StatefulFunctionReference,
    to_qualified_name,
)


FILTERS = [
    prefect.schedules.filters.between_datetimes,
    prefect.schedules.filters.between_dates,
    prefect.schedules.filters.between_times,
    prefect.schedules.filters.is_weekday,
    prefect.schedules.filters.is_weekend,
    prefect.schedules.filters.is_month_end,
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


class CronClockSchema(ObjectSchema):
    class Meta:
        object_class = prefect.schedules.clocks.CronClock

    start_date = DateTimeTZ(allow_none=True)
    end_date = DateTimeTZ(allow_none=True)
    cron = fields.String(required=True)


class DatesClockSchema(ObjectSchema):
    class Meta:
        object_class = prefect.schedules.clocks.DatesClock

    start_date = DateTimeTZ(allow_none=True)
    end_date = DateTimeTZ(allow_none=True)
    dates = DateTimeTZ(required=True, many=True)


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
    Once pre-0.6.0 schedules are deprecated, this will become the main serialization class
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
    NOTE: this schedule is DEPRECATED. In the future, the `NewScheduleSchema` will
    become the default.
    """

    # map class name to schema
    type_schemas = {
        "Schedule": NewScheduleSchema,
        "IntervalSchedule": old_schedule.IntervalScheduleSchema,
        "CronSchedule": old_schedule.CronScheduleSchema,
        "OneTimeSchedule": old_schedule.OneTimeScheduleSchema,
        "UnionSchedule": old_schedule.UnionScheduleSchema,
    }

    def get_obj_type(self, obj: Any) -> str:
        """Returns name of object schema"""
        name = obj.__class__.__name__
        if name != "Schedule":
            warnings.warn(
                "This type of Schedule is deprecated and will be removed from "
                "Prefect. Use a prefect.schedules.Schedule instead.",
                UserWarning,
            )
        return name
