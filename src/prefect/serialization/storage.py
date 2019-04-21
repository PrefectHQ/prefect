import marshmallow
from marshmallow import fields, post_load

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
    flows = fields.Dict(key=fields.Str(), values=fields.Str())

    @post_load
    def create_object(self, data: dict) -> Docker:
        flows = data.pop("flows", dict())
        base_obj = super().create_object(data)
        base_obj.flows = flows
        return base_obj


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
