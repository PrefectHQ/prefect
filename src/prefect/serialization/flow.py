from typing import Set
from marshmallow import fields, post_load, pre_dump, utils

import prefect
from prefect.serialization.edge import EdgeSchema
from prefect.serialization.environment import EnvironmentSchema
from prefect.serialization.schedule import ScheduleSchema
from prefect.serialization.task import ParameterSchema, TaskSchema
from prefect.utilities.serialization import (
    JSONCompatible,
    Nested,
    ObjectSchema,
    to_qualified_name,
)


def get_parameters(obj: prefect.Flow, context: dict) -> Set:
    if isinstance(obj, prefect.Flow):
        return {p for p in obj.tasks if isinstance(p, prefect.core.task.Parameter)}
    else:
        return utils.get_value(obj, "parameters")


def get_reference_tasks(obj: prefect.Flow, context: dict) -> Set:
    if isinstance(obj, prefect.Flow):
        return obj._reference_tasks
    else:
        return utils.get_value(obj, "reference_tasks")


class FlowSchema(ObjectSchema):
    class Meta:
        object_class = lambda: prefect.core.Flow
        exclude_fields = ["id", "type", "parameters"]
        # ordered to make sure Task objects are loaded before Edge objects, due to Task caching
        ordered = True

    id = fields.String()
    project = fields.String(allow_none=True)
    name = fields.String(required=True, allow_none=True)
    version = fields.String(allow_none=True)
    description = fields.String(allow_none=True)
    type = fields.Function(lambda flow: to_qualified_name(type(flow)), lambda x: x)
    schedule = fields.Nested(ScheduleSchema, allow_none=True)
    parameters = Nested(ParameterSchema, value_selection_fn=get_parameters, many=True)
    tasks = fields.Nested(TaskSchema, many=True)
    edges = fields.Nested(EdgeSchema, many=True)
    reference_tasks = Nested(
        TaskSchema, value_selection_fn=get_reference_tasks, many=True, only=["id"]
    )
    environment = fields.Nested(EnvironmentSchema, allow_none=True)

    @post_load
    def create_object(self, data: dict) -> prefect.core.Flow:
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
        if "id" in data:
            flow.id = data["id"]
        return flow
