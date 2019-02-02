import json
from typing import Any, Dict

from marshmallow import fields, post_load, ValidationError

from prefect.engine import state
from prefect.engine import result
from prefect.serialization.result import StateResultSchema
from prefect.utilities.collections import DotDict
from prefect.utilities.serialization import (
    JSONCompatible,
    OneOfSchema,
    ObjectSchema,
    to_qualified_name,
)


class BaseStateSchema(ObjectSchema):
    class Meta:
        object_class = state.State

    message = fields.String(allow_none=True)
    _result = fields.Nested(StateResultSchema, allow_none=False)

    @post_load
    def create_object(self, data):
        result_obj = data.pop("_result", result.NoResult)
        base_obj = super().create_object(data)
        base_obj._result = result_obj
        return base_obj


class PendingSchema(BaseStateSchema):
    class Meta:
        object_class = state.Pending

    cached_inputs = fields.Dict(
        key=fields.Str(), values=fields.Nested(StateResultSchema), allow_none=True
    )


class SubmittedSchema(BaseStateSchema):
    class Meta:
        object_class = state.Submitted

    state = fields.Nested("StateSchema", allow_none=True)


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


class CachedSchema(SuccessSchema):
    class Meta:
        object_class = state.Cached

    cached_inputs = fields.Dict(
        key=fields.Str(), values=fields.Nested(StateResultSchema), allow_none=True
    )
    cached_parameters = JSONCompatible(allow_none=True)
    cached_result_expiration = fields.DateTime(allow_none=True)


class MappedSchema(SuccessSchema):
    class Meta:
        exclude = ["_result", "map_states"]
        object_class = state.Mapped

    # though this field is excluded from serialization, it must be present in the schema
    map_states = fields.Nested("StateSchema", many=True)
    n_map_states = fields.Integer()

    @post_load
    def create_object(self, data):
        n_map_states = data.pop("n_map_states", 0)
        data["map_states"] = [None for _ in range(n_map_states)]
        return super().create_object(data)


class FailedSchema(FinishedSchema):
    class Meta:
        object_class = state.Failed


class TimedOutSchema(FinishedSchema):
    class Meta:
        object_class = state.TimedOut

    cached_inputs = fields.Dict(
        key=fields.Str(), values=fields.Nested(StateResultSchema), allow_none=True
    )


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
        "Cached": CachedSchema,
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
