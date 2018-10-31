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


@version("0.3.2")
class NoScheduleSchema(VersionedSchema):
    class Meta:
        object_class = prefect.schedules.NoSchedule


@version("0.3.2")
class IntervalScheduleSchema(VersionedSchema):
    class Meta:
        object_class = prefect.schedules.IntervalSchedule

    start_date = fields.DateTime(required=True)
    interval = fields.TimeDelta(required=True)


@version("0.3.2")
class CronScheduleSchema(VersionedSchema):
    class Meta:
        object_class = prefect.schedules.CronSchedule

    cron = fields.String(required=True)


@version("0.3.2")
class DateScheduleSchema(VersionedSchema):
    class Meta:
        object_class = prefect.schedules.DateSchedule

    dates = fields.List(fields.DateTime(), required=True)


class ScheduleSchema(OneOfSchema):
    """
    Field that chooses between several nested schemas
    """

    # map class name to schema
    type_schemas = {
        "NoSchedule": NoScheduleSchema,
        "IntervalSchedule": IntervalScheduleSchema,
        "CronSchedule": CronScheduleSchema,
        "DateSchedule": DateScheduleSchema,
    }
