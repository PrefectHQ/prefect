import json
from typing import Any, Dict

from marshmallow import fields, post_load

from prefect.engine import state
from prefect.utilities.serialization import (
    JSONCompatible,
    OneOfSchema,
    VersionedSchema,
    to_qualified_name,
    version,
)


class ResultHandlerField(JSONCompatible):
    def _serialize(self, value, attr, obj, **kwargs):
        if self.context.get("result_handler") and value is not None:
            uri = self.context["result_handler"].serialize(value)
        else:
            uri = value
        return super()._serialize(uri, attr, obj, **kwargs)

    def _deserialize(self, value, attr, data, **kwargs):
        value = super()._deserialize(value, attr, data, **kwargs)
        if self.context.get("result_handler") and value not in [None, "null"]:
            true_val = self.context["result_handler"].deserialize(value)
        else:
            true_val = value
        return true_val


@version("0.3.3")
class BaseStateSchema(VersionedSchema):
    class Meta:
        object_class = state.State

    message = fields.String(allow_none=True)
    result = ResultHandlerField(allow_none=True)


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
