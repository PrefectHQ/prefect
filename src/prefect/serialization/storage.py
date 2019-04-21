import marshmallow
from marshmallow import fields

import prefect
from prefect.environments.storage import Memory, Docker, Storage
from prefect.utilities.serialization import ObjectSchema, OneOfSchema


class BaseStorageSchema(ObjectSchema):
    class Meta:
        object_class = Storage


class DockerSchema(ObjectSchema):
    class Meta:
        object_class = Docker

    registry_url = fields.String(allow_none=True)
    image_name = fields.String(allow_none=True)
    image_tag = fields.String(allow_none=True)


class MemorySchema(ObjectSchema):
    class Meta:
        object_class = Memory


class StorageSchema(OneOfSchema):
    """
    Field that chooses between several nested schemas
    """

    # map class name to schema
    type_schemas = {
        "Docker": DockerSchema,
        "Memory": MemorySchema,
        "Storage": BaseStorageSchema,
    }
