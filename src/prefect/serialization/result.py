from marshmallow import fields, post_load
from typing import Any

from prefect.engine import result, results
from prefect.tasks.secrets import SecretBase
from prefect.utilities.serialization import (
    ObjectSchema,
    OneOfSchema,
    to_qualified_name,
)


class ResultSchema(ObjectSchema):
    class Meta:
        object_class = result.Result

    location = fields.Str(allow_none=True)


class NoResultSchema(ObjectSchema):
    class Meta:
        object_class = result.NoResultType


class CustomResultSchema(ObjectSchema):
    class Meta:
        object_class = lambda: result.Result
        exclude_fields = ["type"]

    location = fields.Str(allow_none=True)

    type = fields.Function(lambda result: to_qualified_name(type(result)), lambda x: x)

    @post_load
    def create_object(self, data: dict, **kwargs: Any) -> result.Result:
        """Because we cannot deserialize a custom class, return a base `Result`"""
        return result.Result(location=data.get("location"))


class AzureResultSchema(ObjectSchema):
    class Meta:
        object_class = results.AzureResult

    container = fields.Str(allow_none=False)
    location = fields.Str(allow_none=True)


class ConstantResultSchema(ObjectSchema):
    class Meta:
        object_class = results.ConstantResult

    location = fields.Str(allow_none=True)


class GCSResultSchema(ObjectSchema):
    class Meta:
        object_class = results.GCSResult

    bucket = fields.Str(allow_none=False)
    location = fields.Str(allow_none=True)


class LocalResultSchema(ObjectSchema):
    class Meta:
        object_class = results.LocalResult

    dir = fields.Str(allow_none=False)
    location = fields.Str(allow_none=True)

    @post_load
    def create_object(self, data: dict, **kwargs: Any) -> results.LocalResult:
        data["validate_dir"] = False
        base_obj = super().create_object(data)
        return base_obj


class PrefectResultSchema(ObjectSchema):
    class Meta:
        object_class = results.PrefectResult

    location = fields.Str(allow_none=True)


class S3ResultSchema(ObjectSchema):
    class Meta:
        object_class = results.S3Result

    bucket = fields.Str(allow_none=False)
    location = fields.Str(allow_none=True)


class SecretResultSchema(ObjectSchema):
    class Meta:
        object_class = results.SecretResult
        exclude_fields = ["secret_type"]

    location = fields.Str(allow_none=True)
    secret_type = fields.Function(
        lambda res: type(res.secret_task).__name__, lambda x: x
    )

    @post_load
    def create_object(self, data: dict, **kwargs: Any) -> results.SecretResult:
        data["secret_task"] = SecretBase()
        base_obj = super().create_object(data)
        return base_obj


class StateResultSchema(OneOfSchema):
    """
    Field that chooses between several nested schemas
    """

    type_schemas = {
        "Result": ResultSchema,
        "CustomResult": CustomResultSchema,
        "AzureResult": AzureResultSchema,
        "ConstantResult": ConstantResultSchema,
        "GCSResult": GCSResultSchema,
        "LocalResult": LocalResultSchema,
        "PrefectResult": PrefectResultSchema,
        "S3Result": S3ResultSchema,
        "SecretResult": SecretResultSchema,
        "NoResultType": NoResultSchema,
    }

    def _load(self, data, *args, **kwargs):
        if data.get("type") not in self.type_schemas:
            data["type"] = "CustomResult"
        return super()._load(data, *args, **kwargs)

    def get_obj_type(self, obj: Any) -> str:
        name = obj.__class__.__name__
        if name in self.type_schemas:
            return name
        else:
            return "CustomResult"
