from typing import Any

import marshmallow
from marshmallow import fields

import prefect
from prefect.utilities.serialization import (
    OneOfSchema,
    VersionedSchema,
    to_qualified_name,
    version,
)


@version("0.3.3")
class IntervalScheduleSchema(VersionedSchema):
    class Meta:
        object_class = prefect.schedules.IntervalSchedule

    start_date = fields.DateTime(required=True)
    end_date = fields.DateTime(allow_none=True)
    interval = fields.TimeDelta(required=True)


@version("0.3.3")
class CronScheduleSchema(VersionedSchema):
    class Meta:
        object_class = prefect.schedules.CronSchedule

    start_date = fields.DateTime(allow_none=True)
    end_date = fields.DateTime(allow_none=True)
    cron = fields.String(required=True)


class ScheduleSchema(OneOfSchema):
    """
    Field that chooses between several nested schemas
    """

    # map class name to schema
    type_schemas = {
        "IntervalSchedule": IntervalScheduleSchema,
        "CronSchedule": CronScheduleSchema,
    }
