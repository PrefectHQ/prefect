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
    env = environments.LocalEnvironment(encryption_key=b"test")
    serialized = LocalEnvironmentSchema().dump(env)
    assert serialized["encryption_key"] == "dGVzdA=="
    assert serialized["__version__"] == prefect.__version__


def test_deserialize_local_environment():
    env = environments.LocalEnvironment(encryption_key=b"test")
    serialized = LocalEnvironmentSchema().dump(env)
    deserialized = LocalEnvironmentSchema().load(serialized)
    assert isinstance(deserialized, environments.LocalEnvironment)
    assert deserialized.encryption_key == b"test"


def test_serialize_container_environment():
    env = environments.ContainerEnvironment(
        base_image="a",
        python_dependencies=["b", "c"],
        secrets=["d", "e"],
        registry_url="f",
    )
    serialized = ContainerEnvironmentSchema().dump(env)
    assert serialized["base_image"] == "a"
    assert serialized["python_dependencies"] == ["b", "c"]
    assert serialized["secrets"] == ["d", "e"]
    assert serialized["registry_url"] == "f"
    assert serialized["__version__"] == prefect.__version__


def test_deserialize_container_environment():
    env = environments.ContainerEnvironment(
        base_image="a", python_dependencies=["b", "c"], secrets=["d", "e"]
    )
    serialized = ContainerEnvironmentSchema().dump(env)
    deserialized = ContainerEnvironmentSchema().load(serialized)

    assert deserialized.python_dependencies == env.python_dependencies
    assert deserialized.secrets == env.secrets


def test_environment_schema_with_local_environment():
    env = environments.LocalEnvironment(encryption_key=b"test")
    serialized = EnvironmentSchema().dump(env)
    deserialized = EnvironmentSchema().load(serialized)
    assert isinstance(deserialized, environments.LocalEnvironment)
    assert deserialized.encryption_key == b"test"


def test_environment_schema_with_container_environment():
    env = environments.ContainerEnvironment(
        base_image="a", python_dependencies=["b", "c"], secrets=["d", "e"]
    )
    serialized = EnvironmentSchema().dump(env)
    deserialized = EnvironmentSchema().load(serialized)
    assert isinstance(deserialized, environments.ContainerEnvironment)
    assert deserialized.python_dependencies == env.python_dependencies
    assert deserialized.secrets == env.secrets
    assert deserialized.registry_url == env.registry_url
    assert deserialized.base_image == env.base_image
