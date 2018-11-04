from typing import Any
import marshmallow
import prefect
from marshmallow_oneofschema import OneOfSchema
from marshmallow import fields
from prefect.serialization.versioned_schema import (
    VersionedSchema,
    version,
    to_qualified_name,
)


@version("0.3.3")
class IntervalScheduleSchema(VersionedSchema):
    class Meta:
        object_class = prefect.schedules.IntervalSchedule

    start_date = fields.DateTime(required=True)
    interval = fields.TimeDelta(required=True)


@version("0.3.3")
class CronScheduleSchema(VersionedSchema):
    class Meta:
        object_class = prefect.schedules.CronSchedule

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
