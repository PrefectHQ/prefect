from typing import Any
import marshmallow
import prefect
from marshmallow import fields, post_load
from prefect.utilities.collections import DotDict
from prefect.utilities.serialization import (
    Bytes,
    JSONCompatible,
    VersionedSchema,
    version,
    to_qualified_name,
    OneOfSchema,
)


@version("0.3.3")
class LocalEnvironmentSchema(VersionedSchema):
    class Meta:
        object_class = prefect.environments.LocalEnvironment

    encryption_key = Bytes(allow_none=True)
    serialized_flow = Bytes(allow_none=True)


@version("0.3.3")
class ContainerEnvironmentSchema(VersionedSchema):
    class Meta:
        object_class = prefect.environments.ContainerEnvironment

    base_image = fields.String(required=True)
    registry_url = fields.String(required=True)
    image_name = fields.String(allow_none=True)
    image_tag = fields.String(allow_none=True)
    python_dependencies = fields.List(fields.String(), allow_none=True)


class EnvironmentSchema(OneOfSchema):
    """
    Field that chooses between several nested schemas
    """

    # map class name to schema
    type_schemas = {
        "ContainerEnvironment": ContainerEnvironmentSchema,
        "LocalEnvironment": LocalEnvironmentSchema,
    }
