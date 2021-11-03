from marshmallow import fields, pre_load

import prefect
from prefect.serialization.task import TaskSchema
from prefect.utilities.serialization import ObjectSchema


class EdgeSchema(ObjectSchema):
    class Meta:
        object_class = lambda: prefect.core.Edge

    @pre_load(pass_many=True)
    def cast_task_slug_strings_to_task_schema_dicts(self, data, **kwargs):
        for seredge in data:
            if not isinstance(seredge, dict):
                continue
            upstream_task = seredge.get("upstream_task")
            downstream_task = seredge.get("downstream_task")
            if isinstance(upstream_task, str):
                seredge["upstream_task"] = {"slug": upstream_task}
            if isinstance(upstream_task, str):
                seredge["downstream_task"] = {"slug": downstream_task}

        return data

    upstream_task = fields.Nested(TaskSchema, only=["slug"])
    downstream_task = fields.Nested(TaskSchema, only=["slug"])
    key = fields.String(allow_none=True)
    mapped = fields.Boolean(allow_none=True)
    flattened = fields.Boolean(allow_none=True)
