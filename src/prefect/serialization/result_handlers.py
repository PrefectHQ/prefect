import json
from typing import Any, Dict, Optional

from marshmallow import ValidationError, fields, post_load

from prefect.engine.cloud.result_handler import CloudResultHandler
from prefect.engine.result_handlers import (
    GCSResultHandler,
    JSONResultHandler,
    LocalResultHandler,
    ResultHandler,
    S3ResultHandler,
)
from prefect.utilities.serialization import (
    JSONCompatible,
    ObjectSchema,
    OneOfSchema,
    to_qualified_name,
)


class BaseResultHandlerSchema(ObjectSchema):
    class Meta:
        object_class = ResultHandler


class CustomResultHandlerSchema(ObjectSchema):
    class Meta:
        object_class = lambda: ResultHandler
        exclude_fields = ["type"]

    type = fields.Function(
        lambda handler: to_qualified_name(type(handler)), lambda x: x
    )

    @post_load
    def create_object(self, data: dict) -> None:
        """Because we cannot deserialize a custom class, just return `None`"""
        return None


class CloudResultHandlerSchema(BaseResultHandlerSchema):
    class Meta:
        object_class = CloudResultHandler

    result_handler_service = fields.String(allow_none=True)


class GCSResultHandlerSchema(BaseResultHandlerSchema):
    class Meta:
        object_class = GCSResultHandler

    bucket = fields.String(allow_none=False)


class JSONResultHandlerSchema(BaseResultHandlerSchema):
    class Meta:
        object_class = JSONResultHandler


class LocalResultHandlerSchema(BaseResultHandlerSchema):
    class Meta:
        object_class = LocalResultHandler

    dir = fields.String(allow_none=True)


class S3ResultHandlerSchema(BaseResultHandlerSchema):
    class Meta:
        object_class = S3ResultHandler

    bucket = fields.String(allow_none=False)


class ResultHandlerSchema(OneOfSchema):
    """
    Field that chooses between several nested schemas
    """

    # map class name to schema
    type_schemas = {
        "ResultHandler": BaseResultHandlerSchema,
        "GCSResultHandler": GCSResultHandlerSchema,
        "S3ResultHandler": S3ResultHandlerSchema,
        "CloudResultHandler": CloudResultHandlerSchema,
        "JSONResultHandler": JSONResultHandlerSchema,
        "LocalResultHandler": LocalResultHandlerSchema,
    }

    def get_obj_type(self, obj: Any) -> str:
        name = obj.__class__.__name__
        self.type_schemas.setdefault(name, CustomResultHandlerSchema)
        return name
