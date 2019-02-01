from marshmallow import fields

from prefect.engine import result
from prefect.serialization.result_handlers import ResultHandlerSchema
from prefect.utilities.serialization import JSONCompatible, ObjectSchema


class ResultSchema(ObjectSchema):
    class Meta:
        object_class = result.Result

    value = JSONCompatible(allow_none=True)
    serialized = fields.Boolean(allow_none=False)
    serializer = fields.Nested(ResultHandlerSchema)


class NoResultSchema(ObjectSchema):
    class Meta:
        object_class = result.NoResult
