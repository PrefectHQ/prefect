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
    env = environments.Environment()

    serialized = CloudEnvironmentSchema().dump(env)
    assert serialized
    assert serialized["__version__"] == prefect.__version__
