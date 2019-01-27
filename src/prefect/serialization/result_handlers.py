import json
from typing import Any, Dict

from marshmallow import fields, post_load, ValidationError

from prefect.engine.result_handlers import ResultHandler, LocalResultHandler
from prefect.utilities.serialization import (
    JSONCompatible,
    OneOfSchema,
    VersionedSchema,
    to_qualified_name,
    version,
)


@version("0.3.3")
class BaseResultHandlerSchema(VersionedSchema):
    class Meta:
        object_class = ResultHandler


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
        "LocalResultHandler": LocalResultHandlerSchema,
    }
