"""
This module ensures that old-style schedules (pre-0.6.1) can be deserialized as new-style
schedules. It is deprecated.
"""
from typing import Any

from marshmallow import fields, post_load

import prefect
from prefect.utilities.serialization import (
    DateTimeTZ,
    ObjectSchema,
)


class IntervalScheduleSchema(ObjectSchema):
    class Meta:
        object_class = lambda: prefect.schedules.IntervalSchedule

    start_date = DateTimeTZ(required=True)
    end_date = DateTimeTZ(allow_none=True)
    interval = fields.TimeDelta(precision="microseconds", required=True)


class CronScheduleSchema(ObjectSchema):
    class Meta:
        object_class = lambda: prefect.schedules.CronSchedule

    start_date = DateTimeTZ(allow_none=True)
    end_date = DateTimeTZ(allow_none=True)
    cron = fields.String(required=True)
    day_or = fields.Boolean(allow_none=True)


class OneTimeScheduleSchema(ObjectSchema):
    class Meta:
        object_class = lambda: prefect.schedules.OneTimeSchedule

    start_date = DateTimeTZ(required=True)


class UnionScheduleSchema(ObjectSchema):
    class Meta:
        object_class = lambda: prefect.schedules.UnionSchedule

    start_date = DateTimeTZ(required=True)
    end_date = DateTimeTZ(allow_none=True)
    schedules = fields.Nested(
        "prefect.serialization.schedule.ScheduleSchema", many=True
    )

    @post_load
    def create_object(self, data: dict, **kwargs: Any) -> prefect.schedules.Schedule:
        return super().create_object({"schedules": data.pop("schedules", [])})
