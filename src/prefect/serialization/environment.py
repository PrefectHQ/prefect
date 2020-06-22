from typing import Any

from marshmallow import fields, post_load

from prefect.environments import (
    DaskKubernetesEnvironment,
    Environment,
    FargateTaskEnvironment,
    KubernetesJobEnvironment,
    LocalEnvironment,
    RemoteEnvironment,
    RemoteDaskEnvironment,
)
from prefect.utilities.serialization import (
    ObjectSchema,
    OneOfSchema,
    to_qualified_name,
    JSONCompatible,
)


class BaseEnvironmentSchema(ObjectSchema):
    class Meta:
        object_class = Environment

    labels = fields.List(fields.String())
    metadata = JSONCompatible(allow_none=True)


class LocalEnvironmentSchema(ObjectSchema):
    class Meta:
        object_class = LocalEnvironment

    labels = fields.List(fields.String())
    metadata = JSONCompatible(allow_none=True)


class DaskKubernetesEnvironmentSchema(ObjectSchema):
    class Meta:
        object_class = DaskKubernetesEnvironment

    docker_secret = fields.String(allow_none=True)
    labels = fields.List(fields.String())
    metadata = JSONCompatible(allow_none=True)
    private_registry = fields.Boolean(allow_none=False)
    min_workers = fields.Int()
    max_workers = fields.Int()


class FargateTaskEnvironmentSchema(ObjectSchema):
    class Meta:
        object_class = FargateTaskEnvironment

    labels = fields.List(fields.String())
    metadata = JSONCompatible(allow_none=True)


class KubernetesJobEnvironmentSchema(ObjectSchema):
    class Meta:
        object_class = KubernetesJobEnvironment

    labels = fields.List(fields.String())
    metadata = JSONCompatible(allow_none=True)


class RemoteEnvironmentSchema(ObjectSchema):
    class Meta:
        object_class = RemoteEnvironment

    executor = fields.String(allow_none=True)
    executor_kwargs = fields.Dict(allow_none=True)
    labels = fields.List(fields.String())
    metadata = JSONCompatible(allow_none=True)


class RemoteDaskEnvironmentSchema(ObjectSchema):
    class Meta:
        object_class = RemoteDaskEnvironment

    address = fields.String()
    labels = fields.List(fields.String())
    metadata = JSONCompatible(allow_none=True)


class CustomEnvironmentSchema(ObjectSchema):
    class Meta:
        object_class = lambda: Environment
        exclude_fields = ["type"]

    labels = fields.List(fields.String())
    metadata = JSONCompatible(allow_none=True)

    type = fields.Function(
        lambda environment: to_qualified_name(type(environment)), lambda x: x
    )

    @post_load
    def create_object(self, data: dict, **kwargs: Any) -> Environment:
        """
        Because we cannot deserialize a custom class, we return an empty
        Base Environment with the appropriate labels.
        """
        return Environment(labels=data.get("labels"), metadata=data.get("metadata"))


class EnvironmentSchema(OneOfSchema):
    """
    Field that chooses between several nested schemas
    """

    # map class name to schema
    type_schemas = {
        "DaskKubernetesEnvironment": DaskKubernetesEnvironmentSchema,
        "Environment": BaseEnvironmentSchema,
        "FargateTaskEnvironment": FargateTaskEnvironmentSchema,
        "LocalEnvironment": LocalEnvironmentSchema,
        "KubernetesJobEnvironment": KubernetesJobEnvironmentSchema,
        "RemoteEnvironment": RemoteEnvironmentSchema,
        "RemoteDaskEnvironment": RemoteDaskEnvironmentSchema,
        "CustomEnvironment": CustomEnvironmentSchema,
    }

    def get_obj_type(self, obj: Any) -> str:
        name = obj.__class__.__name__
        if name in self.type_schemas:
            return name
        else:
            return "CustomEnvironment"
