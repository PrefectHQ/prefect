from marshmallow import fields

from prefect.engine import result
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


class NORESULTSchema(ObjectSchema):
    class Meta:
        object_class = result._NORESULT


class StateResultSchema(OneOfSchema):
    """
    Field that chooses between several nested schemas
    """

    # map class name to schema
    type_schemas = {
        "SafeResult": SafeResultSchema,
        "NoResultType": NoResultSchema,
        "Result": ResultSchema,
        "_NORESULT": NORESULTSchema,
    }
