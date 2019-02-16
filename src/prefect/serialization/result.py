from marshmallow import fields

from prefect.engine import result
from prefect.serialization.result_handlers import ResultHandlerSchema
from prefect.utilities.serialization import JSONCompatible, ObjectSchema, OneOfSchema


class SafeResultSchema(ObjectSchema):
    class Meta:
        object_class = result.SafeResult

    value = JSONCompatible(allow_none=True)
    result_handler = fields.Nested(ResultHandlerSchema, allow_none=False)


class NoResultSchema(ObjectSchema):
    class Meta:
        object_class = result.NoResultType


class StateResultSchema(OneOfSchema):
    """
    Field that chooses between several nested schemas
    """

    # map class name to schema
    type_schemas = {"SafeResult": SafeResultSchema, "NoResultType": NoResultSchema}
