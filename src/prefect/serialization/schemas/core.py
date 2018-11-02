from collections import OrderedDict
import marshmallow
import prefect
from marshmallow_oneofschema import OneOfSchema
from marshmallow import fields, pre_dump, post_load, pre_load
from prefect.serialization.versioned_schema import (
    VersionedSchema,
    version,
    to_qualified_name,
    from_qualified_name,
)
from prefect.serialization.schemas.schedule import ScheduleSchema


class FunctionReference(fields.Field):
    """
    Field that stores a reference to a function as a string and reloads it when
    deserialized.
    """

    def _serialize(self, value, attr, obj, **kwargs):
        return to_qualified_name(value)

    def _deserialize(self, value, attr, data, **kwargs):
        return from_qualified_name(value)


@version("0.3.3")
class TaskSchema(VersionedSchema):
    class Meta:
        object_class = lambda: prefect.core.Task
        object_class_exclude = ["id", "type"]

    id = fields.Method("dump_task_id", "load_task_id", allow_none=True)
    type = fields.Function(lambda task: to_qualified_name(type(task)), lambda x: x)
    name = fields.String(allow_none=True)
    slug = fields.String(allow_none=True)
    description = fields.String(allow_none=True)
    tags = fields.List(fields.String())
    max_retries = fields.Integer(allow_none=True)
    retry_delay = fields.TimeDelta(allow_none=True)
    timeout = fields.TimeDelta(allow_none=True)
    trigger = FunctionReference(allow_none=True)
    skip_on_upstream_skip = fields.Boolean(allow_none=True)
    cache_for = fields.TimeDelta(allow_none=True)
    cache_validator = FunctionReference(allow_none=True)

    def dump_task_id(self, obj):
        """
        Helper for serializing task IDs that may have been placed in the context dict

        Args:
            - obj (Task): the object being serialized

        Returns:
            - str: the object ID
        """
        if isinstance(obj, prefect.core.Task) and "task_ids" in self.context:
            return self.context["task_ids"].get(obj, None)

    def load_task_id(self, data):
        """
        Helper for loading task IDs (required because `id` is a Method field)

        Args:
            - data (str): the id of the object

        Returns:
            - str: the object ID
        """
        return data

    def get_attribute(self, obj, key, default):
        """
        By default, Marshmallow attempts to index an object, then get its attributes.
        Indexing a Task results in a new IndexTask, so for tasks we use getattr(). Otherwise
        we use the default method.
        """
        if isinstance(obj, prefect.Task):
            return getattr(obj, key, default)
        else:
            return super().get_attribute(obj, key, default)

    @post_load
    def create_object(self, data):
        """
        Sometimes we deserialize tasks and edges simultaneously (for example, when a
        Flow is being deserialized), in which case we check IDs to see if we already
        deserialized a matching task. In that case, we reload the task from a shared
        cache.
        """
        task_id = data.get("id", None)
        if task_id not in self.context.setdefault("task_cache", {}) or task_id is None:
            task = super().create_object(data)
            self.context["task_cache"][task_id] = task
        return self.context["task_cache"][task_id]


@version("0.3.3")
class EdgeSchema(VersionedSchema):
    class Meta:
        object_class = lambda: prefect.core.Edge

    upstream_task = fields.Nested(TaskSchema, only=["id"])
    downstream_task = fields.Nested(TaskSchema, only=["id"])
    key = fields.String(allow_none=True)
    mapped = fields.Boolean(allow_none=True)


@version("0.3.3")
class FlowSchema(VersionedSchema):
    class Meta:
        object_class = lambda: prefect.core.Flow
        object_class_exclude = ["id", "type"]
        # ordered to make sure Task objects are loaded before Edge objects, due to Task caching
        ordered = True

    id = fields.String()
    project = fields.String(allow_none=True)
    name = fields.String(allow_none=True)
    version = fields.String(allow_none=True)
    description = fields.String(allow_none=True)
    type = fields.Function(lambda flow: to_qualified_name(type(flow)), lambda x: x)
    schedule = fields.Nested(ScheduleSchema)
    # environment =
    tasks = fields.Nested(TaskSchema, many=True)
    edges = fields.Nested(EdgeSchema, many=True)

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
        edges = set(data.pop("edges", []))
        flow = super().create_object(data)
        flow.edges = edges
        flow._id = data.get("id", None)
        return flow
