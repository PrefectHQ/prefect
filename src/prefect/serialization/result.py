from marshmallow import fields

from prefect.engine import result, results
from prefect.serialization.result_handlers import ResultHandlerSchema
from prefect.utilities.serialization import JSONCompatible, ObjectSchema, OneOfSchema


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


class AzureResultSchema(ObjectSchema):
    class Meta:
        object_class = results.AzureResult

    location = fields.Str(allow_none=True)


class ConstantResultSchema(ObjectSchema):
    class Meta:
        object_class = results.ConstantResult

    location = fields.Str(allow_none=True)


class GCSResultSchema(ObjectSchema):
    class Meta:
        object_class = results.GCSResult

    location = fields.Str(allow_none=True)


class LocalResultSchema(ObjectSchema):
    class Meta:
        object_class = results.LocalResult

    location = fields.Str(allow_none=True)


class PrefectResultSchema(ObjectSchema):
    class Meta:
        object_class = results.PrefectResult

    location = fields.Str(allow_none=True)


class S3ResultSchema(ObjectSchema):
    class Meta:
        object_class = results.S3Result

    location = fields.Str(allow_none=True)


class SecretResultSchema(ObjectSchema):
    class Meta:
        object_class = results.SecretResult

    location = fields.Str(allow_none=True)


class ResultHandlerResultSchema(ObjectSchema):
    class Meta:
        object_class = results.ResultHandlerResult

    location = fields.Str(allow_none=True)


class StateResultSchema(OneOfSchema):
    """
    Field that chooses between several nested schemas
    """

    # map class name to schema
    type_schemas = {
        "SafeResult": SafeResultSchema,
        "NoResultType": NoResultSchema,
        "Result": ResultSchema,
        "AzureResult": AzureResultSchema,
        "ConstantResult": ConstantResultSchema,
        "GCSResult": GCSResultSchema,
        "LocalResult": LocalResultSchema,
        "PrefectResult": PrefectResultSchema,
        "S3Result": S3ResultSchema,
        "SecretResult": SecretResultSchema,
        "ResultHandlerResult": ResultHandlerResultSchema,
    }
