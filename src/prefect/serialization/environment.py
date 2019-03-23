from typing import Any, TYPE_CHECKING

import marshmallow
from marshmallow import fields, post_load

import prefect
from prefect.utilities.collections import DotDict
from prefect.utilities.serialization import (
    Bytes,
    JSONCompatible,
    OneOfSchema,
    ObjectSchema,
    to_qualified_name,
)


if TYPE_CHECKING:
    import prefect.environments.kubernetes


class LocalEnvironmentSchema(ObjectSchema):
    class Meta:
        object_class = prefect.environments.LocalEnvironment

    encryption_key = Bytes(allow_none=True)
    serialized_flow = Bytes(allow_none=True)


class DockerEnvironmentSchema(ObjectSchema):
    class Meta:
        object_class = prefect.environments.DockerEnvironment

    base_image = fields.String(required=True)
    registry_url = fields.String(required=True)
    image_name = fields.String(allow_none=True)
    image_tag = fields.String(allow_none=True)


# Kubernetes Environments


class DockerOnKubernetesEnvironmentSchema(DockerEnvironmentSchema):
    class Meta:
        object_class = prefect.environments.kubernetes.DockerOnKubernetesEnvironment


class DaskOnKubernetesEnvironmentSchema(DockerEnvironmentSchema):
    class Meta:
        object_class = prefect.environments.kubernetes.DaskOnKubernetesEnvironment

    max_workers = fields.Integer(allow_none=True)


class EnvironmentSchema(OneOfSchema):
    """
    Field that chooses between several nested schemas
    """

    # map class name to schema
    type_schemas = {
        "DockerEnvironment": DockerEnvironmentSchema,
        "LocalEnvironment": LocalEnvironmentSchema,
        "DockerOnKubernetesEnvironment": DockerOnKubernetesEnvironmentSchema,
        "DaskOnKubernetesEnvironment": DaskOnKubernetesEnvironmentSchema,
    }
