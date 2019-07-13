import json
from typing import Any, Dict, Optional

from marshmallow import ValidationError, fields, post_load

from prefect.engine.result_handlers import (
    JSONResultHandler,
    LocalResultHandler,
    ResultHandler,
)


from prefect.utilities.serialization import (
    JSONCompatible,
    ObjectSchema,
    OneOfSchema,
    to_qualified_name,
)


from prefect.utilities.imports import lazy_import

lazy_gcs_result_handler = lazy_import(
    "prefect.engine.result_handlers.gcs_result_handler",
    globals(),
    "lazy_gcs_result_handler",
)
lazy_s3_result_handler = lazy_import(
    "prefect.engine.result_handlers.s3_result_handler",
    globals(),
    "lazy_s3_result_handler",
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
    def create_object(self, data: dict, **kwargs: Any) -> None:
        """Because we cannot deserialize a custom class, just return `None`"""
        return None


class GCSResultHandlerSchema(BaseResultHandlerSchema):
    class Meta:
        object_class = lambda: lazy_gcs_result_handler.GCSResultHandler

    bucket = fields.String(allow_none=False)
    credentials_secret = fields.String(allow_none=True)


class JSONResultHandlerSchema(BaseResultHandlerSchema):
    class Meta:
        object_class = JSONResultHandler


class LocalResultHandlerSchema(BaseResultHandlerSchema):
    class Meta:
        object_class = LocalResultHandler

    dir = fields.String(allow_none=True)


class S3ResultHandlerSchema(BaseResultHandlerSchema):
    class Meta:
        object_class = lambda: lazy_s3_result_handler.S3ResultHandler

    bucket = fields.String(allow_none=False)
    aws_credentials_secret = fields.String(allow_none=True)


class ResultHandlerSchema(OneOfSchema):
    """
    Field that chooses between several nested schemas
    """

    # map class name to schema
    type_schemas = {
        "ResultHandler": BaseResultHandlerSchema,
        "GCSResultHandler": GCSResultHandlerSchema,
        "S3ResultHandler": S3ResultHandlerSchema,
        "JSONResultHandler": JSONResultHandlerSchema,
        "LocalResultHandler": LocalResultHandlerSchema,
    }

    def get_obj_type(self, obj: Any) -> str:
        name = obj.__class__.__name__
        self.type_schemas.setdefault(name, CustomResultHandlerSchema)
        return name
