import json
from typing import Any, Dict

from marshmallow import fields, post_load, ValidationError

from prefect.engine.cloud.result_serializer import CloudResultSerializer
from prefect.engine.result_serializers import (
    ResultSerializer,
    JSONResultSerializer,
    LocalResultSerializer,
)
from prefect.utilities.serialization import (
    JSONCompatible,
    OneOfSchema,
    ObjectSchema,
    to_qualified_name,
)


class BaseResultSerializerSchema(ObjectSchema):
    class Meta:
        object_class = ResultSerializer


class CloudResultSerializerSchema(BaseResultSerializerSchema):
    class Meta:
        object_class = CloudResultSerializer

    result_serializer_service = fields.String(allow_none=True)


class JSONResultSerializerSchema(BaseResultSerializerSchema):
    class Meta:
        object_class = JSONResultSerializer


class LocalResultSerializerSchema(BaseResultSerializerSchema):
    class Meta:
        object_class = LocalResultSerializer

    dir = fields.String(allow_none=True)


class ResultSerializerSchema(OneOfSchema):
    """
    Field that chooses between several nested schemas
    """

    # map class name to schema
    type_schemas = {
        "ResultSerializer": BaseResultSerializerSchema,
        "CloudResultSerializer": CloudResultSerializerSchema,
        "JSONResultSerializer": JSONResultSerializerSchema,
        "LocalResultSerializer": LocalResultSerializerSchema,
    }
