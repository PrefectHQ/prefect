from typing import TYPE_CHECKING, Any

import marshmallow
from marshmallow import fields, post_load

import prefect
from prefect.utilities.serialization import (
    DateTimeTZ,
    ObjectSchema,
    OneOfSchema,
    to_qualified_name,
)

if TYPE_CHECKING:
    import prefect.schedules


class IntervalScheduleSchema(ObjectSchema):
    class Meta:
        object_class = prefect.schedules.IntervalSchedule

    start_date = DateTimeTZ(required=True)
    end_date = DateTimeTZ(allow_none=True)
    interval = fields.TimeDelta(precision="microseconds", required=True)


class CronScheduleSchema(ObjectSchema):
    class Meta:
        object_class = prefect.schedules.CronSchedule

    start_date = DateTimeTZ(allow_none=True)
    end_date = DateTimeTZ(allow_none=True)
    cron = fields.String(required=True)


class OneTimeScheduleSchema(ObjectSchema):
    class Meta:
        object_class = prefect.schedules.OneTimeSchedule

    start_date = DateTimeTZ(required=True)


class UnionScheduleSchema(ObjectSchema):
    class Meta:
        object_class = prefect.schedules.UnionSchedule

    start_date = DateTimeTZ(required=True)
    end_date = DateTimeTZ(allow_none=True)
    schedules = fields.Nested(
        "prefect.serialization.schedule.ScheduleSchema", many=True
    )

    @post_load
    def create_object(
        self, data: dict, **kwargs: Any
    ) -> prefect.schedules.UnionSchedule:
        schedules = data.pop("schedules", [])
        base_obj = super().create_object({"schedules": schedules})
        return base_obj


class ScheduleSchema(OneOfSchema):
    """
    Field that chooses between several nested schemas
    """

    # map class name to schema
    type_schemas = {
        "IntervalSchedule": IntervalScheduleSchema,
        "CronSchedule": CronScheduleSchema,
        "OneTimeSchedule": OneTimeScheduleSchema,
        "UnionSchedule": UnionScheduleSchema,
    }
