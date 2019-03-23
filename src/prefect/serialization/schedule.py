from typing import Any, TYPE_CHECKING

import marshmallow
from marshmallow import fields

import prefect
from prefect.utilities.serialization import (
    OneOfSchema,
    ObjectSchema,
    to_qualified_name,
    DateTimeTZ,
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


class ScheduleSchema(OneOfSchema):
    """
    Field that chooses between several nested schemas
    """

    # map class name to schema
    type_schemas = {
        "IntervalSchedule": IntervalScheduleSchema,
        "CronSchedule": CronScheduleSchema,
        "OneTimeSchedule": OneTimeScheduleSchema,
    }
