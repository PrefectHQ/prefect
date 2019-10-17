import json
from typing import Any, Dict, TYPE_CHECKING

from marshmallow import ValidationError, fields, post_load

from prefect.engine import result, state
from prefect.serialization.result import StateResultSchema
from prefect.utilities.serialization import (
    JSONCompatible,
    Nested,
    ObjectSchema,
    OneOfSchema,
    to_qualified_name,
)

if TYPE_CHECKING:
    import prefect


def get_safe(obj: state.State, context: dict) -> Any:
    """
    Helper function for ensuring only safe values are serialized.
    Note that it is up to the user to actively store a Result's value in a
    safe way prior to serialization (if they want the result to be avaiable post-serialization).
    """
    if context.get("attr") == "_result":
        return obj._result.safe_value  # type: ignore
    value = context.get("value", result.NoResult)
    if value is None:
        return value
    return value.safe_value


class BaseStateSchema(ObjectSchema):
    class Meta:
        object_class = state.State

    context = fields.Dict(key=fields.Str(), values=JSONCompatible(), allow_none=True)
    message = fields.String(allow_none=True)
    _result = Nested(StateResultSchema, allow_none=False, value_selection_fn=get_safe)

    @post_load
    def create_object(self, data: dict, **kwargs: Any) -> state.State:
        result_obj = data.pop("_result", result.NoResult)
        data["result"] = result_obj
        base_obj = super().create_object(data)
        return base_obj


class PendingSchema(BaseStateSchema):
    class Meta:
        object_class = state.Pending

    cached_inputs = fields.Dict(
        key=fields.Str(),
        values=Nested(StateResultSchema, value_selection_fn=get_safe),
        allow_none=True,
    )


class MetaStateSchema(BaseStateSchema):
    state = fields.Nested("StateSchema", allow_none=True)


class ClientFailedSchema(MetaStateSchema):
    class Meta:
        object_class = state.ClientFailed


class SubmittedSchema(MetaStateSchema):
    class Meta:
        object_class = state.Submitted


class QueuedSchema(MetaStateSchema):
    class Meta:
        object_class = state.Queued

    start_time = fields.DateTime(allow_none=True)


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


class LoopedSchema(BaseStateSchema):
    class Meta:
        object_class = state.Looped

    loop_count = fields.Int(allow_none=False)


class SuccessSchema(FinishedSchema):
    class Meta:
        object_class = state.Success


class CachedSchema(SuccessSchema):
    class Meta:
        object_class = state.Cached

    cached_inputs = fields.Dict(
        key=fields.Str(),
        values=Nested(
            StateResultSchema, value_selection_fn=get_safe, attr="cached_inputs"
        ),
        allow_none=True,
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
    def create_object(self, data: dict, **kwargs: Any) -> state.Mapped:
        n_map_states = data.pop("n_map_states", 0)
        data["map_states"] = [None for _ in range(n_map_states)]
        return super().create_object(data)


class FailedSchema(FinishedSchema):
    class Meta:
        object_class = state.Failed

    cached_inputs = fields.Dict(
        key=fields.Str(),
        values=Nested(StateResultSchema, value_selection_fn=get_safe),
        allow_none=True,
    )


class AbortedSchema(FailedSchema):
    class Meta:
        object_class = state.Aborted


class TimedOutSchema(FinishedSchema):
    class Meta:
        object_class = state.TimedOut

    cached_inputs = fields.Dict(
        key=fields.Str(),
        values=Nested(
            StateResultSchema, value_selection_fn=get_safe, attr="cached_inputs"
        ),
        allow_none=True,
    )


class TriggerFailedSchema(FailedSchema):
    class Meta:
        object_class = state.TriggerFailed


class SkippedSchema(SuccessSchema):
    class Meta:
        object_class = state.Skipped
        exclude_fields = ["cached"]


class PausedSchema(ScheduledSchema):
    class Meta:
        object_class = state.Paused


class StateSchema(OneOfSchema):
    """
    Field that chooses between several nested schemas
    """

    # map class name to schema
    type_schemas = {
        "Aborted": AbortedSchema,
        "Cached": CachedSchema,
        "ClientFailed": ClientFailedSchema,
        "Failed": FailedSchema,
        "Finished": FinishedSchema,
        "Looped": LoopedSchema,
        "Mapped": MappedSchema,
        "Paused": PausedSchema,
        "Pending": PendingSchema,
        "Queued": QueuedSchema,
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
