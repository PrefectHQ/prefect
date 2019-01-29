import json
from typing import Any, Dict

from marshmallow import fields, post_load, ValidationError

from prefect.engine import state
from prefect.utilities.collections import DotDict
from prefect.utilities.serialization import (
    JSONCompatible,
    OneOfSchema,
    ObjectSchema,
    to_qualified_name,
)


class ResultHandlerField(fields.Field):
    def _serialize(self, value, attr, obj, **kwargs):
        if hasattr(obj, "_metadata"):
            is_raw = obj._metadata[attr]["raw"]
            # "raw" results are never serialized
            if is_raw:
                value = None
            else:
                try:
                    json.dumps(value)
                except TypeError:
                    raise TypeError(
                        "The serialized result of a ResultHandler must be JSON-compatible."
                    )
        return super()._serialize(value, attr, obj, **kwargs)


class BaseStateSchema(ObjectSchema):
    class Meta:
        object_class = state.State

    message = fields.String(allow_none=True)
    _metadata = fields.Dict(keys=fields.Str())
    result = ResultHandlerField(allow_none=True)

    @post_load
    def create_object(self, data):
        _metadata = data.pop("_metadata", {})
        base_obj = super().create_object(data)
        base_obj._metadata = DotDict(_metadata)
        return base_obj


class PendingSchema(BaseStateSchema):
    class Meta:
        object_class = state.Pending

    cached_inputs = ResultHandlerField(allow_none=True)


class SubmittedSchema(BaseStateSchema):
    class Meta:
        object_class = state.Submitted

    state = fields.Nested("StateSchema", allow_none=True)


class CachedStateSchema(PendingSchema):
    class Meta:
        object_class = state.CachedState

    cached_result = ResultHandlerField(allow_none=True)
    cached_parameters = JSONCompatible(allow_none=True)
    cached_result_expiration = fields.DateTime(allow_none=True)


class ScheduledSchema(PendingSchema):
    class Meta:
        object_class = state.Scheduled

    start_time = fields.DateTime(allow_none=True)


class ResumeSchema(ScheduledSchema):
    class Meta:
        object_class = state.Resume


class RetryingSchema(ScheduledSchema):
    class Meta:
        object_class = state.Retrying

    run_count = fields.Int(allow_none=True)


class RunningSchema(BaseStateSchema):
    class Meta:
        object_class = state.Running


class FinishedSchema(BaseStateSchema):
    class Meta:
        object_class = state.Finished


class SuccessSchema(FinishedSchema):
    class Meta:
        object_class = state.Success

    cached = fields.Nested(CachedStateSchema, allow_none=True)


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


class FailedSchema(FinishedSchema):
    class Meta:
        object_class = state.Failed


class TimedOutSchema(FinishedSchema):
    class Meta:
        object_class = state.TimedOut

    cached_inputs = ResultHandlerField(allow_none=True)


class TriggerFailedSchema(FailedSchema):
    class Meta:
        object_class = state.TriggerFailed


class SkippedSchema(SuccessSchema):
    class Meta:
        object_class = state.Skipped
        exclude_fields = ["cached"]


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
