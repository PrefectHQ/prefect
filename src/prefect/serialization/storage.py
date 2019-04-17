import marshmallow
from marshmallow import fields

import prefect
from prefect.utilities.serialization import ObjectSchema, OneOfSchema


class StorageSchema(ObjectSchema):
    class Meta:
        object_class = prefect.environments.storage.Storage


class DockerSchema(ObjectSchema):
    class Meta:
        object_class = prefect.environments.storage.Docker

    registry_url = fields.String(allow_none=True)
    image_name = fields.String(allow_none=True)
    image_tag = fields.String(allow_none=True)
    flow_file_path = fields.String(allow_none=True)


class BytesSchema(ObjectSchema):
    class Meta:
        object_class = prefect.environments.storage.Bytes


class StorageSchema(OneOfSchema):
    """
    Field that chooses between several nested schemas
    """

    # map class name to schema
    type_schemas = {
        "Docker": DockerSchema,
        "Bytes": BytesSchema,
        "Storage": StorageSchema,
    }
