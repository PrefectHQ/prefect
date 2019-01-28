import json
from typing import Any, Dict

from marshmallow import fields, post_load, ValidationError

from prefect.engine import state
from prefect.utilities.serialization import (
    JSONCompatible,
    OneOfSchema,
    VersionedSchema,
    to_qualified_name,
    version,
)


class ResultHandlerField(fields.Field):
    def _serialize(self, value, attr, obj, **kwargs):
        if hasattr(obj, "metadata"):
            is_raw = obj.metadata.get(attr, {}).get("raw", True)
            if is_raw:
                value = None
        return super()._serialize(value, attr, obj, **kwargs)

    def _deserialize(self, value, attr, data, **kwargs):
        value = super()._deserialize(value, attr, data, **kwargs)
        return value


@version("0.3.3")
class BaseStateSchema(VersionedSchema):
    class Meta:
        object_class = state.State

    message = fields.String(allow_none=True)
    metadata = fields.Dict(keys=fields.Str())
    result = ResultHandlerField(allow_none=True)

    @post_load
    def create_object(self, data):
        metadata = data.pop("metadata", {})
        base_obj = super().create_object(data)
        base_obj.metadata = metadata
        return base_obj


@version("0.3.3")
class PendingSchema(BaseStateSchema):
    class Meta:
        object_class = state.Pending

    cached_inputs = ResultHandlerField(allow_none=True)


@version("0.3.3")
class SubmittedSchema(BaseStateSchema):
    class Meta:
        object_class = state.Submitted

    state = fields.Nested("StateSchema", allow_none=True)


@version("0.3.3")
class CachedStateSchema(PendingSchema):
    class Meta:
        object_class = state.CachedState

    cached_result = ResultHandlerField(allow_none=True)
    cached_parameters = JSONCompatible(allow_none=True)
    cached_result_expiration = fields.DateTime(allow_none=True)


@version("0.3.3")
class ScheduledSchema(PendingSchema):
    class Meta:
        object_class = state.Scheduled

    start_time = fields.DateTime(allow_none=True)


@version("0.3.3")
class ResumeSchema(ScheduledSchema):
    class Meta:
        object_class = state.Resume


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
        exclude = ["result", "map_states"]
        object_class = state.Mapped

    # though this field is excluded from serialization, it must be present in the schema
    map_states = fields.Nested("StateSchema", many=True)
    n_map_states = fields.Integer()

    @post_load
    def create_object(self, data):
        n_map_states = data.pop("n_map_states", 0)
        data["map_states"] = [
            state.Pending("Generated map state") for _ in range(n_map_states)
        ]
        return super().create_object(data)


@version("0.3.3")
class FailedSchema(FinishedSchema):
    class Meta:
        object_class = state.Failed


@version("0.3.3")
class TimedOutSchema(FinishedSchema):
    class Meta:
        object_class = state.TimedOut

    cached_inputs = ResultHandlerField(allow_none=True)


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
        "CachedState": CachedStateSchema,
        "Failed": FailedSchema,
        "Finished": FinishedSchema,
        "Mapped": MappedSchema,
        "Paused": PausedSchema,
        "Pending": PendingSchema,
        "Resume": ResumeSchema,
        "Retrying": RetryingSchema,
        "Running": RunningSchema,
        "Scheduled": ScheduledSchema,
        "Skipped": SkippedSchema,
        "Submitted": SubmittedSchema,
        "Success": SuccessSchema,
        "TimedOut": TimedOutSchema,
        "TriggerFailed": TriggerFailedSchema,
    }
