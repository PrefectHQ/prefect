import uuid
from collections import OrderedDict

import marshmallow
from marshmallow import (
    ValidationError,
    fields,
    post_dump,
    post_load,
    pre_dump,
    pre_load,
)

import prefect
from prefect.utilities.serialization import (
    UUID,
    FunctionReference,
    JSONCompatible,
    VersionedSchema,
    from_qualified_name,
    to_qualified_name,
    version,
)


class TaskMethodsMixin:
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
        task_id = data.get("id", str(uuid.uuid4()))

        # if the id is not in the task cache, create a task object and add it
        if task_id not in self.context.setdefault("task_id_cache", {}):
            task = super().create_object(data)
            task.id = task_id
            self.context["task_id_cache"][task_id] = task

        # return the task object from the cache
        return self.context["task_id_cache"][task_id]


@version("0.3.3")
class TaskSchema(TaskMethodsMixin, VersionedSchema):
    class Meta:
        object_class = lambda: prefect.core.Task
        object_class_exclude = ["id", "type"]

    id = UUID()
    type = fields.Function(lambda task: to_qualified_name(type(task)), lambda x: x)
    name = fields.String(allow_none=True)
    slug = fields.String(allow_none=True)
    description = fields.String(allow_none=True)
    tags = fields.List(fields.String())
    max_retries = fields.Integer(allow_none=True)
    retry_delay = fields.TimeDelta(allow_none=True)
    timeout = fields.TimeDelta(allow_none=True)
    trigger = FunctionReference(
        valid_functions=[
            prefect.triggers.all_finished,
            prefect.triggers.manual_only,
            prefect.triggers.always_run,
            prefect.triggers.all_successful,
            prefect.triggers.all_failed,
            prefect.triggers.any_successful,
            prefect.triggers.any_failed,
        ],
        # don't reject custom functions, just leave them as strings
        reject_invalid=False,
        allow_none=True,
    )
    skip_on_upstream_skip = fields.Boolean(allow_none=True)
    cache_for = fields.TimeDelta(allow_none=True)
    cache_validator = FunctionReference(
        valid_functions=[
            prefect.engine.cache_validators.never_use,
            prefect.engine.cache_validators.duration_only,
            prefect.engine.cache_validators.all_inputs,
            prefect.engine.cache_validators.all_parameters,
            prefect.engine.cache_validators.partial_inputs_only,
            prefect.engine.cache_validators.partial_parameters_only,
        ],
        # don't reject custom functions, just leave them as strings
        reject_invalid=False,
        allow_none=True,
    )


@version("0.3.3")
class ParameterSchema(TaskMethodsMixin, VersionedSchema):
    class Meta:
        object_class = lambda: prefect.core.task.Parameter
        object_class_exclude = ["id", "type"]

    id = UUID()
    type = fields.Function(lambda task: to_qualified_name(type(task)), lambda x: x)
    name = fields.String(required=True)
    default = JSONCompatible(allow_none=True)
    required = fields.Boolean(allow_none=True)
    description = fields.String(allow_none=True)
    tags = fields.List(fields.String())
