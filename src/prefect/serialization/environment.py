from marshmallow import fields

from prefect.environments import (
    CloudEnvironment,
    Environment,
    LocalEnvironment,
    RemoteEnvironment,
)
from prefect.utilities.serialization import ObjectSchema, OneOfSchema


class BaseEnvironmentSchema(ObjectSchema):
    class Meta:
        object_class = Environment


class LocalEnvironmentSchema(ObjectSchema):
    class Meta:
        object_class = LocalEnvironment


class CloudEnvironmentSchema(ObjectSchema):
    class Meta:
        object_class = CloudEnvironment

    docker_secret = fields.String(allow_none=True)
    private_registry = fields.Boolean(allow_none=False)


class RemoteEnvironmentSchema(ObjectSchema):
    class Meta:
        object_class = RemoteEnvironment

    executor = fields.String(allow_none=True)
    executor_kwargs = fields.Dict(allow_none=True)


class EnvironmentSchema(OneOfSchema):
    """
    Field that chooses between several nested schemas
    """

    # map class name to schema
    type_schemas = {
        "CloudEnvironment": CloudEnvironmentSchema,
        "Environment": BaseEnvironmentSchema,
        "LocalEnvironment": LocalEnvironmentSchema,
        "RemoteEnvironment": RemoteEnvironmentSchema,
    }
