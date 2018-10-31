from typing import Any, Dict
import json
from marshmallow_oneofschema import OneOfSchema
from marshmallow import fields, post_load
from prefect.serialization.versioned_schema import (
    VersionedSchema,
    version,
    to_qualified_name,
)
from prefect.engine import state
from prefect.utilities.serialization import JSONField


@version("0.3.2")
class BaseStateSchema(VersionedSchema):
    class Meta:
        object_class = state.State

    message = fields.String(allow_none=True)
    result = JSONField(max_size=16000, allow_none=True)
    timestamp = fields.DateTime(allow_none=True)


@version("0.3.2")
class PendingSchema(BaseStateSchema):
    class Meta:
        object_class = state.Pending

    cached_inputs = JSONField(max_size=16000, allow_none=True)


@version("0.3.2")
class CachedStateSchema(PendingSchema):
    class Meta:
        object_class = state.CachedState

    cached_result = JSONField(max_size=16000, allow_none=True)
    cached_parameters = JSONField(max_size=16000, allow_none=True)
    cached_result_expiration = fields.DateTime(allow_none=True)


@version("0.3.2")
class ScheduledSchema(PendingSchema):
    class Meta:
        object_class = state.Scheduled

    start_time = fields.DateTime(allow_none=True)


@version("0.3.2")
class RetryingSchema(ScheduledSchema):
    class Meta:
        object_class = state.Retrying

    run_count = fields.Int(allow_none=True)


@version("0.3.2")
class RunningSchema(BaseStateSchema):
    class Meta:
        object_class = state.Running


@version("0.3.2")
class FinishedSchema(BaseStateSchema):
    class Meta:
        object_class = state.Finished


@version("0.3.2")
class SuccessSchema(FinishedSchema):
    class Meta:
        object_class = state.Success

    cached = fields.Nested(CachedStateSchema, allow_none=True)


@version("0.3.2")
class MappedSchema(SuccessSchema):
    class Meta:
        object_class = state.Mapped


@version("0.3.2")
class FailedSchema(FinishedSchema):
    class Meta:
        object_class = state.Failed


@version("0.3.2")
class TriggerFailedSchema(FailedSchema):
    class Meta:
        object_class = state.TriggerFailed


@version("0.3.2")
class SkippedSchema(SuccessSchema):
    class Meta:
        object_class = state.Skipped
        object_class_exclude = ["cached"]


@version("0.3.2")
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
        "TriggerFailed": TriggerFailedSchema,
        "Skipped": SkippedSchema,
        "Paused": PausedSchema,
    }
