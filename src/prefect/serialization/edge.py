from marshmallow import fields
import prefect
from prefect.utilities.serialization import VersionedSchema, version
from prefect.serialization.task import TaskSchema


@version("0.3.3")
class EdgeSchema(VersionedSchema):
    class Meta:
        object_class = lambda: prefect.core.Edge

    upstream_task = fields.Nested(TaskSchema, only=["id"])
    downstream_task = fields.Nested(TaskSchema, only=["id"])
    key = fields.String(allow_none=True)
    mapped = fields.Boolean(allow_none=True)
