import prefect
from prefect.environments import CloudEnvironment, Environment
from prefect.utilities.serialization import ObjectSchema, OneOfSchema


class BaseEnvironmentSchema(ObjectSchema):
    class Meta:
        object_class = Environment


class CloudEnvironmentSchema(ObjectSchema):
    class Meta:
        object_class = CloudEnvironment


class EnvironmentSchema(OneOfSchema):
    """
    Field that chooses between several nested schemas
    """

    # map class name to schema
    type_schemas = {
        "CloudEnvironment": CloudEnvironmentSchema,
        "Environment": BaseEnvironmentSchema,
    }
