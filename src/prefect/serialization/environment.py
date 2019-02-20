from typing import Any

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


class LocalOnKubernetesEnvironment(DockerEnvironmentSchema):
    class Meta:
        object_class = prefect.environments.kubernetes.LocalOnKubernetesEnvironment


class DockerOnKubernetesEnvironment(DockerEnvironmentSchema):
    class Meta:
        object_class = prefect.environments.kubernetes.DockerOnKubernetesEnvironment


class EnvironmentSchema(OneOfSchema):
    """
    Field that chooses between several nested schemas
    """

    # map class name to schema
    type_schemas = {
        "DockerEnvironment": DockerEnvironmentSchema,
        "LocalEnvironment": LocalEnvironmentSchema,
        "LocalOnKubernetesEnvironment": LocalOnKubernetesEnvironment,
        "DockerOnKubernetesEnvironment": DockerOnKubernetesEnvironment,
    }
