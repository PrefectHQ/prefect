from marshmallow import fields

from prefect.engine import result
from prefect.serialization.result_handlers import ResultHandlerSchema
from prefect.utilities.serialization import JSONCompatible, ObjectSchema, OneOfSchema

class ResultSchema(ObjectSchema):
    class Meta:
        object_class = result.Result

    value = JSONCompatible(allow_none=True)
    handled = fields.Boolean()
    result_handler = fields.Nested(ResultHandlerSchema)


class NoResultSchema(ObjectSchema):
    class Meta:
        object_class = result.NoResultType


class StateResultSchema(OneOfSchema):
    """
    Field that chooses between several nested schemas
    """

    # map class name to schema
    type_schemas = {
        "Result": ResultSchema,
        "NoResultType": NoResultSchema,
    }

