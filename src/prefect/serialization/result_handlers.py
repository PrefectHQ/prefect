import json
from typing import Any, Dict

from marshmallow import fields, post_load, ValidationError

from prefect.engine.cloud.result_handler import CloudResultHandler
from prefect.engine.result_handlers import ResultHandler, LocalResultHandler
from prefect.utilities.serialization import (
    JSONCompatible,
    OneOfSchema,
    VersionedSchema,
    to_qualified_name,
    version,
)


@version("0.4.0")
class BaseResultHandlerSchema(VersionedSchema):
    class Meta:
        object_class = ResultHandler


@version("0.4.0")
class CloudResultHandlerSchema(BaseResultHandlerSchema):
    class Meta:
        object_class = CloudResultHandler

    result_handler_service = fields.String(allow_none=True)


@version("0.3.3")
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
        "LocalResultHandler": LocalResultHandlerSchema,
    }
