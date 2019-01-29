from marshmallow import fields

import prefect
from prefect.serialization.task import TaskSchema
from prefect.utilities.serialization import ObjectSchema


class EdgeSchema(ObjectSchema):
    class Meta:
        object_class = lambda: prefect.core.Edge

    upstream_task = fields.Nested(TaskSchema, only=["id"])
    downstream_task = fields.Nested(TaskSchema, only=["id"])
    key = fields.String(allow_none=True)
    mapped = fields.Boolean(allow_none=True)
