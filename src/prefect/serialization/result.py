from marshmallow import fields, post_load
from typing import Any

from prefect.engine import result, results
from prefect.engine.result_handlers import ResultHandler
from prefect.serialization.result_handlers import ResultHandlerSchema
from prefect.tasks.secrets import SecretBase
from prefect.utilities.serialization import (
    JSONCompatible,
    ObjectSchema,
    OneOfSchema,
    to_qualified_name,
)


class SafeResultSchema(ObjectSchema):
    class Meta:
        object_class = result.SafeResult

    value = JSONCompatible(allow_none=True)
    result_handler = fields.Nested(ResultHandlerSchema, allow_none=False)


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


class ResultHandlerResultSchema(ObjectSchema):
    class Meta:
        object_class = results.ResultHandlerResult
        exclude_fields = ["result_handler_type"]

    location = fields.Str(allow_none=True)
    result_handler_type = fields.Function(
        lambda res: type(res.result_handler).__name__, lambda x: x
    )

    @post_load
    def create_object(self, data: dict, **kwargs: Any) -> results.ResultHandlerResult:
        data["result_handler"] = ResultHandler()
        base_obj = super().create_object(data)
        return base_obj


class StateResultSchema(OneOfSchema):
    """
    Field that chooses between several nested schemas
    """

    # map class name to schema
    type_schemas = {
        "SafeResult": SafeResultSchema,
        "NoResultType": NoResultSchema,
        "Result": ResultSchema,
        "CustomResult": CustomResultSchema,
        "AzureResult": AzureResultSchema,
        "ConstantResult": ConstantResultSchema,
        "GCSResult": GCSResultSchema,
        "LocalResult": LocalResultSchema,
        "PrefectResult": PrefectResultSchema,
        "S3Result": S3ResultSchema,
        "SecretResult": SecretResultSchema,
        "ResultHandlerResult": ResultHandlerResultSchema,
    }

    def get_obj_type(self, obj: Any) -> str:
        name = obj.__class__.__name__
        if name in self.type_schemas:
            return name
        else:
            return "CustomResult"
