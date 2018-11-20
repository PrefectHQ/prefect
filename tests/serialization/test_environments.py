import datetime
import json

import pytest

import marshmallow
import prefect
from prefect import environments
from prefect.serialization.environment import (
    EnvironmentSchema,
    ContainerEnvironmentSchema,
    LocalEnvironmentSchema,
)


def test_serialize_local_environment():
    env = environments.LocalEnvironment(encryption_key="test")
    serialized = LocalEnvironmentSchema().dump(env)
    assert serialized["encryption_key"] == "test"
    assert serialized["__version__"] == prefect.__version__


def test_deserialize_local_environment():
    env = environments.LocalEnvironment(encryption_key="test")
    serialized = LocalEnvironmentSchema().dump(env)
    deserialized = LocalEnvironmentSchema().load(serialized)
    assert isinstance(deserialized, environments.LocalEnvironment)
    assert deserialized.encryption_key == "test"


def test_serialize_container_environment():
    env = environments.ContainerEnvironment(
        image="a", name="b", tag="c", python_dependencies=["d", "e"], secrets=["f", "g"]
    )
    serialized = ContainerEnvironmentSchema().dump(env)
    assert serialized["image"] == "a"
    assert serialized["name"] == "b"
    assert serialized["tag"] == "c"
    assert serialized["python_dependencies"] == ["d", "e"]
    assert serialized["secrets"] == ["f", "g"]
    assert serialized["__version__"] == prefect.__version__


def test_deserialize_container_environment():
    env = environments.ContainerEnvironment(
        image="a", name="b", tag="c", python_dependencies=["d", "e"], secrets=["f", "g"]
    )
    serialized = ContainerEnvironmentSchema().dump(env)
    deserialized = ContainerEnvironmentSchema().load(serialized)

    assert deserialized.image == env.image
    assert deserialized.name == env.name
    assert deserialized.tag == env.tag
    assert deserialized.python_dependencies == env.python_dependencies
    assert deserialized.secrets == env.secrets


def test_environment_schema_with_local_environment():
    env = environments.LocalEnvironment(encryption_key="test")
    serialized = EnvironmentSchema().dump(env)
    deserialized = EnvironmentSchema().load(serialized)
    assert isinstance(deserialized, environments.LocalEnvironment)
    assert deserialized.encryption_key == "test"


def test_environment_schema_with_local_environment():
    env = environments.ContainerEnvironment(
        image="a", name="b", tag="c", python_dependencies=["d", "e"], secrets=["f", "g"]
    )
    serialized = EnvironmentSchema().dump(env)
    deserialized = EnvironmentSchema().load(serialized)
    assert isinstance(deserialized, environments.ContainerEnvironment)
    assert deserialized.image == env.image
    assert deserialized.name == env.name
    assert deserialized.tag == env.tag
    assert deserialized.python_dependencies == env.python_dependencies
    assert deserialized.secrets == env.secrets
