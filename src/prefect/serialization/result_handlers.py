from typing import Any

from marshmallow import fields, post_load

from prefect.engine.result_handlers import (
    AzureResultHandler,
    GCSResultHandler,
    JSONResultHandler,
    LocalResultHandler,
    ResultHandler,
    S3ResultHandler,
)
from prefect.utilities.serialization import (
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
    def create_object(self, data: dict, **kwargs: Any) -> ResultHandler:
        """Because we cannot deserialize a custom class, just return `None`"""
        return ResultHandler()


class SecretResultHandlerSchema(ObjectSchema):
    class Meta:
        object_class = lambda: ResultHandler

    name = fields.Function(lambda handler: handler.secret_task.name, lambda x: x)

    @post_load
    def create_object(self, data: dict, **kwargs: Any) -> ResultHandler:
        """Because we cannot deserialize a custom class, just return `None`"""
        return ResultHandler()


class GCSResultHandlerSchema(BaseResultHandlerSchema):
    class Meta:
        object_class = GCSResultHandler

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
        object_class = S3ResultHandler

    bucket = fields.String(allow_none=False)
    aws_credentials_secret = fields.String(allow_none=True)


class AzureResultHandlerSchema(BaseResultHandlerSchema):
    class Meta:
        object_class = AzureResultHandler

    container = fields.String(allow_none=False)
    azure_credentials_secret = fields.String(allow_none=True)


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
        "AzureResultHandler": AzureResultHandlerSchema,
        "SecretResultHandler": SecretResultHandlerSchema,
        "CustomResultHandler": CustomResultHandlerSchema,
    }

    def get_obj_type(self, obj: Any) -> str:
        name = obj.__class__.__name__
        if name in self.type_schemas:
            return name
        else:
            return "CustomResultHandler"
