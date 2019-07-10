import prefect
from prefect import environments
from prefect.serialization.environment import (
    BaseEnvironmentSchema,
    CloudEnvironmentSchema,
    RemoteEnvironmentSchema,
)


def test_serialize_base_environment():
    env = environments.Environment()

    serialized = BaseEnvironmentSchema().dump(env)
    assert serialized
    assert serialized["__version__"] == prefect.__version__


def test_serialize_cloud_environment():
    env = environments.CloudEnvironment()

    schema = CloudEnvironmentSchema()
    serialized = schema.dump(env)
    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["docker_secret"] is None

    new = schema.load(serialized)
    assert new.private_registry is False
    assert new.docker_secret is None


def test_serialize_cloud_environment_with_private_registry():
    env = environments.CloudEnvironment(private_registry=True, docker_secret="FOO")

    schema = CloudEnvironmentSchema()
    serialized = schema.dump(env)
    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["private_registry"] is True
    assert serialized["docker_secret"] == "FOO"

    new = schema.load(serialized)
    assert new.private_registry is True
    assert new.docker_secret == "FOO"


def test_serialize_remote_environment():
    env = environments.RemoteEnvironment()

    schema = RemoteEnvironmentSchema()
    serialized = schema.dump(env)
    assert serialized
    assert serialized["__version__"] == prefect.__version__
    assert serialized["executor"] == prefect.config.engine.executor.default_class
    assert serialized["executor_kwargs"] == {}

    new = schema.load(serialized)
    assert new.executor == prefect.config.engine.executor.default_class
    assert new.executor_kwargs == {}
