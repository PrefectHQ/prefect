from typing import Any, List

from marshmallow import fields, post_load, utils, missing

import prefect
from prefect.serialization.edge import EdgeSchema
from prefect.serialization.run_config import RunConfigSchema
from prefect.serialization.schedule import ScheduleSchema
from prefect.serialization.storage import StorageSchema
from prefect.serialization.task import ParameterSchema, TaskSchema
from prefect.utilities.serialization import (
    Nested,
    ObjectSchema,
    to_qualified_name,
)


def get_parameters(obj: prefect.Flow, context: dict) -> List:
    if isinstance(obj, prefect.Flow):
        params = obj.parameters()
    else:
        params = utils.get_value(obj, "parameters")

    if params is missing:
        return params

    return sorted(params, key=lambda p: p.slug)


def get_reference_tasks(obj: prefect.Flow, context: dict) -> List:
    if isinstance(obj, prefect.Flow):
        tasks = obj._reference_tasks
    else:
        tasks = utils.get_value(obj, "reference_tasks")

    if tasks is missing:
        return tasks

    return sorted(tasks, key=lambda t: t.slug)


def get_tasks(obj: prefect.Flow, context: dict) -> List:
    if isinstance(obj, prefect.Flow):
        tasks = obj.tasks
    else:
        tasks = utils.get_value(obj, "tasks")

    if tasks is missing:
        return tasks

    return list(sorted(tasks, key=lambda t: t.slug))


def get_edges(obj: prefect.Flow, context: dict) -> List:
    if isinstance(obj, prefect.Flow):
        edges = obj.edges
    else:
        edges = utils.get_value(obj, "edges")

    if edges is missing:
        return edges

    return list(
        sorted(
            edges,
            key=lambda e: (e.upstream_task.slug, e.downstream_task.slug, e.key or ""),
        )
    )


class FlowSchema(ObjectSchema):
    # All nested 'many' types that are stored as a `Set` in the `Flow` must be sorted
    # using a `value_selection_fn` so `Flow.serialized_hash()` is deterministic

    class Meta:
        object_class = lambda: prefect.core.Flow
        exclude_fields = ["type", "parameters"]
        # ordered to make sure Task objects are loaded before Edge objects, due to Task caching
        ordered = True

    project = fields.String(allow_none=True)
    name = fields.String(required=True, allow_none=True)
    version = fields.String(allow_none=True)
    description = fields.String(allow_none=True)
    type = fields.Function(lambda flow: to_qualified_name(type(flow)), lambda x: x)
    schedule = fields.Nested(ScheduleSchema, allow_none=True)
    parameters = Nested(ParameterSchema, value_selection_fn=get_parameters, many=True)
    tasks = Nested(TaskSchema, value_selection_fn=get_tasks, many=True)
    edges = Nested(EdgeSchema, value_selection_fn=get_edges, many=True)
    reference_tasks = Nested(
        TaskSchema, value_selection_fn=get_reference_tasks, many=True, only=["slug"]
    )
    run_config = fields.Nested(RunConfigSchema, allow_none=True)
    storage = fields.Nested(StorageSchema, allow_none=True)

    @post_load
    def create_object(self, data: dict, **kwargs: Any) -> prefect.core.Flow:
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
        return flow
