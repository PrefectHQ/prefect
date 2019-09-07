from marshmallow import fields

from prefect.environments import (
    DaskKubernetesEnvironment,
    Environment,
    LocalEnvironment,
    RemoteEnvironment,
)
from prefect.utilities.serialization import ObjectSchema, OneOfSchema


class BaseEnvironmentSchema(ObjectSchema):
    class Meta:
        object_class = Environment

    labels = fields.List(fields.String())


class LocalEnvironmentSchema(ObjectSchema):
    class Meta:
        object_class = LocalEnvironment

    labels = fields.List(fields.String())


class DaskKubernetesEnvironmentSchema(ObjectSchema):
    class Meta:
        object_class = DaskKubernetesEnvironment

    docker_secret = fields.String(allow_none=True)
    labels = fields.List(fields.String())
    private_registry = fields.Boolean(allow_none=False)
    min_workers = fields.Int()
    max_workers = fields.Int()


class RemoteEnvironmentSchema(ObjectSchema):
    class Meta:
        object_class = RemoteEnvironment

    executor = fields.String(allow_none=True)
    executor_kwargs = fields.Dict(allow_none=True)
    labels = fields.List(fields.String())


class EnvironmentSchema(OneOfSchema):
    """
    Field that chooses between several nested schemas
    """

    # map class name to schema
    type_schemas = {
        "DaskKubernetesEnvironment": DaskKubernetesEnvironmentSchema,
        "Environment": BaseEnvironmentSchema,
        "LocalEnvironment": LocalEnvironmentSchema,
        "RemoteEnvironment": RemoteEnvironmentSchema,
    }
