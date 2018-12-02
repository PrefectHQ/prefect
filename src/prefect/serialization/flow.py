from marshmallow import fields, post_load, pre_dump

import prefect
from prefect.serialization.edge import EdgeSchema
from prefect.serialization.environment import EnvironmentSchema
from prefect.serialization.schedule import ScheduleSchema
from prefect.serialization.task import ParameterSchema, TaskSchema
from prefect.utilities.serialization import (
    Nested,
    VersionedSchema,
    to_qualified_name,
    version,
)


@version("0.3.3")
class FlowSchema(VersionedSchema):
    class Meta:
        object_class = lambda: prefect.core.Flow
        object_class_exclude = ["id", "type", "parameters"]
        # ordered to make sure Task objects are loaded before Edge objects, due to Task caching
        ordered = True

    id = fields.String()
    project = fields.String(allow_none=True)
    name = fields.String(allow_none=True)
    version = fields.String(allow_none=True)
    description = fields.String(allow_none=True)
    type = fields.Function(lambda flow: to_qualified_name(type(flow)), lambda x: x)
    schedule = fields.Nested(ScheduleSchema, allow_none=True)
    environment = fields.Nested(EnvironmentSchema, allow_none=True)
    parameters = Nested(
        ParameterSchema,
        dump_fn=lambda obj, context: {
            p
            for p in getattr(obj, "tasks", [])
            if isinstance(p, prefect.core.task.Parameter)
        },
        many=True,
    )
    tasks = fields.Nested(TaskSchema, many=True)
    edges = fields.Nested(EdgeSchema, many=True)
    reference_tasks = Nested(
        TaskSchema,
        many=True,
        dump_fn=lambda obj, context: getattr(obj, "_reference_tasks", []),
        only=["id"],
    )

    @pre_dump
    def put_task_ids_in_context(self, flow: "prefect.core.Flow") -> "prefect.core.Flow":
        """
        Adds task ids to context so they may be used by nested TaskSchemas and EdgeSchemas.

        If the serialized object is not a Flow (like a dict), this step is skipped.
        """
        if isinstance(flow, prefect.core.Flow):
            self.context["task_ids"] = {t: i["id"] for t, i in flow.task_info.items()}
        return flow

    @post_load
    def create_object(self, data):
        """
        Flow edges are validated, for example to make sure the keys match Task inputs,
        but because we are deserializing all Tasks as base Tasks, the edge validation will
        fail (base Tasks have no inputs). Therefore we hold back the edges from Flow
        initialization and assign them explicitly.

        Args:
            - data (dict): the deserialized data

        Returns:
            - Flow

        """
        data["validate"] = False
        flow = super().create_object(data)
        flow._id = data.get("id", None)

        for t in flow.tasks:
            flow.task_info[t].update({"id": t._id, "type": t._type})

        return flow
