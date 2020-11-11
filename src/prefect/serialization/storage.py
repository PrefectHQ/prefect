from typing import Any

from marshmallow import fields, post_load

from prefect.environments.storage import (
    GCS,
    S3,
    Azure,
    Docker,
    Local,
    Storage,
    GitHub,
    GitLab,
    Webhook,
)
from prefect.utilities.serialization import JSONCompatible, ObjectSchema, OneOfSchema


class AzureSchema(ObjectSchema):
    class Meta:
        object_class = Azure

    container = fields.String(allow_none=False)
    blob_name = fields.String(allow_none=True)
    stored_as_script = fields.Bool(allow_none=True)
    flows = fields.Dict(key=fields.Str(), values=fields.Str())
    secrets = fields.List(fields.Str(), allow_none=True)

    @post_load
    def create_object(self, data: dict, **kwargs: Any) -> Azure:
        flows = data.pop("flows", dict())
        base_obj = super().create_object(data)
        base_obj.flows = flows
        return base_obj


class BaseStorageSchema(ObjectSchema):
    class Meta:
        object_class = Storage


class DockerSchema(ObjectSchema):
    class Meta:
        object_class = Docker

    registry_url = fields.String(allow_none=True)
    image_name = fields.String(allow_none=True)
    image_tag = fields.String(allow_none=True)
    path = fields.Str(allow_none=True)
    stored_as_script = fields.Bool(allow_none=True)
    flows = fields.Dict(key=fields.Str(), values=fields.Str())
    prefect_version = fields.String(allow_none=False)
    secrets = fields.List(fields.Str(), allow_none=True)

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
    stored_as_script = fields.Bool(allow_none=True)
    flows = fields.Dict(key=fields.Str(), values=fields.Str())
    secrets = fields.List(fields.Str(), allow_none=True)

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
    path = fields.Str(allow_none=True)
    stored_as_script = fields.Bool(allow_none=True)
    flows = fields.Dict(key=fields.Str(), values=fields.Str())
    secrets = fields.List(fields.Str(), allow_none=True)

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
    stored_as_script = fields.Bool(allow_none=True)
    flows = fields.Dict(key=fields.Str(), values=fields.Str())
    client_options = fields.Dict(
        key=fields.Str(), values=JSONCompatible(), allow_none=True
    )
    secrets = fields.List(fields.Str(), allow_none=True)

    @post_load
    def create_object(self, data: dict, **kwargs: Any) -> S3:
        flows = data.pop("flows", dict())
        base_obj = super().create_object(data)
        base_obj.flows = flows
        return base_obj


class GitHubSchema(ObjectSchema):
    class Meta:
        object_class = GitHub

    repo = fields.String(allow_none=False)
    ref = fields.String(allow_none=False)
    path = fields.String(allow_none=True)
    flows = fields.Dict(key=fields.Str(), values=fields.Str())
    secrets = fields.List(fields.Str(), allow_none=True)

    @post_load
    def create_object(self, data: dict, **kwargs: Any) -> GitHub:
        flows = data.pop("flows", dict())
        base_obj = super().create_object(data)
        base_obj.flows = flows
        return base_obj


class GitLabSchema(ObjectSchema):
    class Meta:
        object_class = GitLab

    repo = fields.String(allow_none=False)
    path = fields.String(allow_none=True)
    host = fields.String(allow_none=True)
    ref = fields.String(allow_none=True)
    flows = fields.Dict(key=fields.Str(), values=fields.Str())
    secrets = fields.List(fields.Str(), allow_none=True)

    @post_load
    def create_object(self, data: dict, **kwargs: Any) -> GitHub:
        flows = data.pop("flows", dict())
        base_obj = super().create_object(data)
        base_obj.flows = flows
        return base_obj


class WebhookSchema(ObjectSchema):
    class Meta:
        object_class = Webhook

    build_request_kwargs = fields.Dict(key=fields.Str, allow_none=False)
    build_request_http_method = fields.String(allow_none=False)
    get_flow_request_kwargs = fields.Dict(key=fields.Str, allow_none=False)
    get_flow_request_http_method = fields.String(allow_none=False)
    stored_as_script = fields.Bool(allow_none=True)
    flows = fields.Dict(key=fields.Str(), values=fields.Str())
    secrets = fields.List(fields.Str(), allow_none=True)

    @post_load
    def create_object(self, data: dict, **kwargs: Any) -> Webhook:
        flows = data.pop("flows", dict())
        base_obj = super().create_object(data)
        base_obj.flows = flows
        return base_obj


class StorageSchema(OneOfSchema):
    """
    Field that chooses between several nested schemas
    """

    # map class name to schema
    type_schemas = {
        "Azure": AzureSchema,
        "Docker": DockerSchema,
        "GCS": GCSSchema,
        "Local": LocalSchema,
        "Storage": BaseStorageSchema,
        "S3": S3Schema,
        "GitHub": GitHubSchema,
        "GitLab": GitLabSchema,
        "Webhook": WebhookSchema,
    }
