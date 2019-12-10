from typing import Any

import marshmallow
from marshmallow import fields, post_load

import prefect
from prefect.environments.storage import Bytes, Docker, GCS, Local, Memory, Storage, S3
from prefect.utilities.serialization import Bytes as BytesField
from prefect.utilities.serialization import ObjectSchema, OneOfSchema


class BaseStorageSchema(ObjectSchema):
    class Meta:
        object_class = Storage


class BytesSchema(ObjectSchema):
    class Meta:
        object_class = Bytes

    flows = fields.Dict(key=fields.Str(), values=BytesField())

    @post_load
    def create_object(self, data: dict, **kwargs: Any) -> Docker:
        flows = data.pop("flows", dict())
        base_obj = super().create_object(data)
        base_obj.flows = flows
        return base_obj


class DockerSchema(ObjectSchema):
    class Meta:
        object_class = Docker

    registry_url = fields.String(allow_none=True)
    image_name = fields.String(allow_none=True)
    image_tag = fields.String(allow_none=True)
    flows = fields.Dict(key=fields.Str(), values=fields.Str())
    prefect_version = fields.String(allow_none=False)

    @post_load
    def create_object(self, data: dict, **kwargs: Any) -> Docker:
        flows = data.pop("flows", dict())
        base_obj = super().create_object(data)
        base_obj.flows = flows
        return base_obj


class GCSSchema(ObjectSchema):
    class Meta:
        object_class = GCS

    bucket = fields.Str(allow_none=False)
    key = fields.Str(allow_none=True)
    project = fields.Str(allow_none=True)
    flows = fields.Dict(key=fields.Str(), values=fields.Str())

    @post_load
    def create_object(self, data: dict, **kwargs: Any) -> GCS:
        flows = data.pop("flows", dict())
        base_obj = super().create_object(data)
        base_obj.flows = flows
        return base_obj


class LocalSchema(ObjectSchema):
    class Meta:
        object_class = Local

    directory = fields.Str(allow_none=False)
    flows = fields.Dict(key=fields.Str(), values=fields.Str())

    @post_load
    def create_object(self, data: dict, **kwargs: Any) -> Docker:
        flows = data.pop("flows", dict())
        data.update(validate=False)
        base_obj = super().create_object(data)
        base_obj.flows = flows
        return base_obj


class S3Schema(ObjectSchema):
    class Meta:
        object_class = S3

    bucket = fields.String(allow_none=False)
    key = fields.String(allow_none=True)
    flows = fields.Dict(key=fields.Str(), values=fields.Str())

    @post_load
    def create_object(self, data: dict, **kwargs: Any) -> S3:
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
        "Bytes": BytesSchema,
        "Docker": DockerSchema,
        "GCS": GCSSchema,
        "Local": LocalSchema,
        "Memory": MemorySchema,
        "Storage": BaseStorageSchema,
        "S3": S3Schema,
    }
