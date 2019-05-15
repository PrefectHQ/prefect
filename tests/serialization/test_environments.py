import prefect
from prefect import environments
from prefect.serialization.environment import (
    BaseEnvironmentSchema,
    CloudEnvironmentSchema,
)


def test_serialize_base_environment():
    env = environments.Environment()

    serialized = BaseEnvironmentSchema().dump(env)
    assert serialized
    assert serialized["__version__"] == prefect.__version__


def test_serialize_cloud_environment():
    env = environments.CloudEnvironment()

    serialized = CloudEnvironmentSchema().dump(env)
    assert serialized
    assert serialized["__version__"] == prefect.__version__


def test_serialize_cloud_environment_with_private():
    env = environments.CloudEnvironment(private=True)

    schema = CloudEnvironmentSchema()
    serialized = schema.dump(env)
    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["private"] is True

    new = schema.load(serialized)
    assert new.private is True
