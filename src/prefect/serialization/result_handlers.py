import json
from typing import Any, Dict

from marshmallow import fields, post_load, ValidationError

from prefect.engine.cloud.result_handler import CloudResultHandler
from prefect.engine.result_handlers import (
    ResultHandler,
    JSONResultHandler,
    LocalResultHandler,
)
from prefect.utilities.serialization import (
    JSONCompatible,
    OneOfSchema,
    ObjectSchema,
    to_qualified_name,
)


class BaseResultHandlerSchema(ObjectSchema):
    class Meta:
        object_class = ResultHandler


class CloudResultHandlerSchema(BaseResultHandlerSchema):
    class Meta:
        object_class = CloudResultHandler

    result_handler_service = fields.String(allow_none=True)


class JSONResultHandlerSchema(BaseResultHandlerSchema):
    class Meta:
        object_class = JSONResultHandler


class LocalResultHandlerSchema(BaseResultHandlerSchema):
    class Meta:
        object_class = LocalResultHandler

    dir = fields.String(allow_none=True)


class ResultHandlerSchema(OneOfSchema):
    """
    Field that chooses between several nested schemas
    """

    # map class name to schema
    type_schemas = {
        "ResultHandler": BaseResultHandlerSchema,
        "CloudResultHandler": CloudResultHandlerSchema,
        "JSONResultHandler": JSONResultHandlerSchema,
        "LocalResultHandler": LocalResultHandlerSchema,
    }
