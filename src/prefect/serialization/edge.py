from marshmallow import fields, pre_load

import prefect
from prefect.serialization.task import TaskSchema
from prefect.utilities.serialization import ObjectSchema


class EdgeSchema(ObjectSchema):
    class Meta:
        object_class = lambda: prefect.core.Edge

    @pre_load(pass_many=True)
    def drop_edges_with_bad_task_schemas(self, data, **kwargs):
        new_data = []
        for seredge in data:
            if isinstance(seredge["upstream_task"], dict) and isinstance(
                seredge["downstream_task"], dict
            ):
                new_data.append(seredge)
        return new_data

    upstream_task = fields.Nested(TaskSchema, only=["slug"])
    downstream_task = fields.Nested(TaskSchema, only=["slug"])
    key = fields.String(allow_none=True)
    mapped = fields.Boolean(allow_none=True)
    flattened = fields.Boolean(allow_none=True)
