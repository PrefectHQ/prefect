import prefect
from prefect.utilities.serialization import ObjectSchema, OneOfSchema


class BaseEnvironmentSchema(ObjectSchema):
    class Meta:
        object_class = prefect.environments.Environment


class CloudEnvironmentSchema(ObjectSchema):
    class Meta:
        object_class = prefect.environments.CloudEnvironment


class EnvironmentSchema(OneOfSchema):
    """
    Field that chooses between several nested schemas
    """

    # map class name to schema
    type_schemas = {
        "CloudEnvironment": CloudEnvironmentSchema,
        "Environment": BaseEnvironmentSchema,
    }
