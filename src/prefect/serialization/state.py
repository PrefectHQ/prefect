import json
from typing import Any, Dict

from marshmallow import fields, post_load

from prefect.engine import state
from prefect.utilities.serialization import (
    JSONCompatible,
    OneOfSchema,
    VersionedSchema,
    to_qualified_name,
    DateTime,
    version,
)


class Private(JSONCompatible):
    def _serialize(self, value, attr, obj, **kwargs):
        if "result_handler" in self.context and value is not None:
            uri = self.context["result_handler"].serialize(value)
        else:
            uri = value
        return super()._serialize(uri, attr, obj, **kwargs)

    def _deserialize(self, value, attr, data, **kwargs):
        value = super()._deserialize(value, attr, data, **kwargs)
        if "result_handler" in self.context and value not in [None, "null"]:
            true_val = self.context["result_handler"].deserialize(value)
        else:
            true_val = value
        return true_val


@version("0.3.3")
class BaseStateSchema(VersionedSchema):
    class Meta:
        object_class = state.State

    message = fields.String(allow_none=True)
    result = Private(allow_none=True)
    timestamp = DateTime(allow_none=True)


@version("0.3.3")
class PendingSchema(BaseStateSchema):
    class Meta:
        object_class = state.Pending

    cached_inputs = Private(allow_none=True)


@version("0.3.3")
class CachedStateSchema(PendingSchema):
    class Meta:
        object_class = state.CachedState

    cached_result = Private(allow_none=True)
    cached_parameters = JSONCompatible(allow_none=True)
    cached_result_expiration = DateTime(allow_none=True)


@version("0.3.3")
class ScheduledSchema(PendingSchema):
    class Meta:
        object_class = state.Scheduled

    start_time = DateTime(allow_none=True)


@version("0.3.3")
class RetryingSchema(ScheduledSchema):
    class Meta:
        object_class = state.Retrying

    run_count = fields.Int(allow_none=True)


@version("0.3.3")
class RunningSchema(BaseStateSchema):
    class Meta:
        object_class = state.Running


@version("0.3.3")
class FinishedSchema(BaseStateSchema):
    class Meta:
        object_class = state.Finished


@version("0.3.3")
class SuccessSchema(FinishedSchema):
    class Meta:
        object_class = state.Success

    cached = fields.Nested(CachedStateSchema, allow_none=True)


@version("0.3.3")
class MappedSchema(SuccessSchema):
    class Meta:
        object_class = state.Mapped


@version("0.3.3")
class FailedSchema(FinishedSchema):
    class Meta:
        object_class = state.Failed


@version("0.3.3")
class TimedOutSchema(FinishedSchema):
    class Meta:
        object_class = state.TimedOut

    cached_inputs = Private(allow_none=True)


@version("0.3.3")
class TriggerFailedSchema(FailedSchema):
    class Meta:
        object_class = state.TriggerFailed


@version("0.3.3")
class SkippedSchema(SuccessSchema):
    class Meta:
        object_class = state.Skipped
        object_class_exclude = ["cached"]


@version("0.3.3")
class PausedSchema(PendingSchema):
    class Meta:
        object_class = state.Paused


class StateSchema(OneOfSchema):
    """
    Field that chooses between several nested schemas
    """

    # map class name to schema
    type_schemas = {
        "Pending": PendingSchema,
        "CachedState": CachedStateSchema,
        "Scheduled": ScheduledSchema,
        "Retrying": RetryingSchema,
        "Running": RunningSchema,
        "Finished": FinishedSchema,
        "Success": SuccessSchema,
        "Mapped": MappedSchema,
        "Failed": FailedSchema,
        "TimedOut": TimedOutSchema,
        "TriggerFailed": TriggerFailedSchema,
        "Skipped": SkippedSchema,
        "Paused": PausedSchema,
    }
