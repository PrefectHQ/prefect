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


class ResultSchema(ObjectSchema):
    class Meta:
        object_class = result.Result

    @post_load
    def create_object(self, data):
        result_obj = data.pop("_result", result.NoResult)
        base_obj = super().create_object(data)
        base_obj._result = result_obj
        return base_obj


class StateResultSchema(OneOfSchema):
    """
    Field that chooses between several nested schemas
    """

    # map class name to schema
    type_schemas = {"SafeResult": SafeResultSchema, "NoResultType": NoResultSchema}
