import datetime
import json

import marshmallow
import pytest

import prefect
from prefect import environments
from prefect.serialization.environment import (
    DaskOnKubernetesEnvironmentSchema,
    DockerEnvironmentSchema,
    DockerOnKubernetesEnvironmentSchema,
    EnvironmentSchema,
    LocalEnvironmentSchema,
)

FERNET_KEY = b"1crderTHVJ7vvVJj79Zns81_1opaTID0HRZoOzqIpOA="

#################################
##### Environment Tests
#################################

#################################
##### Local Tests
#################################


def test_serialize_local_environment():
    env = environments.LocalEnvironment(encryption_key=FERNET_KEY)
    serialized = LocalEnvironmentSchema().dump(env)
    assert (
        serialized["encryption_key"]
        == "MWNyZGVyVEhWSjd2dlZKajc5Wm5zODFfMW9wYVRJRDBIUlpvT3pxSXBPQT0="
    )
    assert serialized["__version__"] == prefect.__version__


def test_deserialize_local_environment():
    env = environments.LocalEnvironment(encryption_key=FERNET_KEY)
    serialized = LocalEnvironmentSchema().dump(env)
    deserialized = LocalEnvironmentSchema().load(serialized)
    assert isinstance(deserialized, environments.LocalEnvironment)
    assert deserialized.encryption_key == FERNET_KEY


def test_environment_schema_with_local_environment():
    env = environments.LocalEnvironment(encryption_key=FERNET_KEY)
    serialized = EnvironmentSchema().dump(env)
    deserialized = EnvironmentSchema().load(serialized)
    assert isinstance(deserialized, environments.LocalEnvironment)
    assert deserialized.encryption_key == FERNET_KEY


#################################
##### Docker Tests
#################################


def test_serialize_docker_environment():
    env = environments.DockerEnvironment(
        base_image="a",
        python_dependencies=["b", "c"],
        registry_url="f",
        image_name="g",
        image_tag="h",
    )
    serialized = DockerEnvironmentSchema().dump(env)
    assert serialized["base_image"] == "a"
    assert serialized["registry_url"] == "f"
    assert serialized["image_name"] == "g"
    assert serialized["image_tag"] == "h"
    assert serialized["__version__"] == prefect.__version__


def test_deserialize_empty_docker_environment():
    schema = DockerEnvironmentSchema()
    with pytest.raises(marshmallow.ValidationError):
        schema.load(schema.dump({}))


def test_deserialize_minimal_docker_environment():
    schema = DockerEnvironmentSchema()
    assert schema.load(schema.dump({"base_image": "a", "registry_url": "b"}))


def test_deserialize_docker_environment():
    env = environments.DockerEnvironment(
        base_image="a", python_dependencies=["b", "c"], registry_url="f"
    )
    serialized = DockerEnvironmentSchema().dump(env)
    deserialized = DockerEnvironmentSchema().load(serialized)

    assert deserialized.base_image == env.base_image
    assert deserialized.registry_url == env.registry_url


def test_environment_schema_with_docker_environment():
    env = environments.DockerEnvironment(
        base_image="a", python_dependencies=["b", "c"], registry_url="f"
    )
    serialized = EnvironmentSchema().dump(env)
    deserialized = EnvironmentSchema().load(serialized)
    assert isinstance(deserialized, environments.DockerEnvironment)
    assert deserialized.registry_url == env.registry_url
    assert deserialized.base_image == env.base_image


#################################
##### DockerOnKubernetes Tests
#################################


def test_serialize_docker_on_kubernetes_environment():
    env = environments.kubernetes.DockerOnKubernetesEnvironment(
        base_image="a",
        python_dependencies=["b", "c"],
        registry_url="f",
        image_name="g",
        image_tag="h",
    )
    serialized = DockerOnKubernetesEnvironmentSchema().dump(env)
    assert serialized["base_image"] == "a"
    assert serialized["registry_url"] == "f"
    assert serialized["image_name"] == "g"
    assert serialized["image_tag"] == "h"
    assert serialized["__version__"] == prefect.__version__


def test_serialize_docker_on_kubernetes_environment_no_base_image():
    env = environments.kubernetes.DockerOnKubernetesEnvironment(
        python_dependencies=["b", "c"], registry_url="f", image_name="g", image_tag="h"
    )
    serialized = DockerOnKubernetesEnvironmentSchema().dump(env)
    assert serialized["base_image"] == "python:3.6"
    assert serialized["registry_url"] == "f"
    assert serialized["image_name"] == "g"
    assert serialized["image_tag"] == "h"
    assert serialized["__version__"] == prefect.__version__


def test_deserialize_empty_docker_on_kubernetes_environment():
    schema = DockerOnKubernetesEnvironmentSchema()
    with pytest.raises(marshmallow.ValidationError):
        schema.load(schema.dump({}))


def test_deserialize_minimal_docker_on_kubernetes_environment():
    schema = DockerOnKubernetesEnvironmentSchema()
    assert schema.load(schema.dump({"base_image": "a", "registry_url": "b"}))


def test_deserialize_docker_on_kubernetes_environment():
    env = environments.kubernetes.DockerOnKubernetesEnvironment(
        base_image="a", python_dependencies=["b", "c"], registry_url="f"
    )
    serialized = DockerOnKubernetesEnvironmentSchema().dump(env)
    deserialized = DockerOnKubernetesEnvironmentSchema().load(serialized)

    assert deserialized.base_image == env.base_image
    assert deserialized.registry_url == env.registry_url


def test_environment_schema_with_docker_on_kubernetes_environment():
    env = environments.kubernetes.DockerOnKubernetesEnvironment(
        base_image="a", python_dependencies=["b", "c"], registry_url="f"
    )
    serialized = DockerOnKubernetesEnvironmentSchema().dump(env)
    deserialized = DockerOnKubernetesEnvironmentSchema().load(serialized)
    assert isinstance(
        deserialized, environments.kubernetes.DockerOnKubernetesEnvironment
    )
    assert deserialized.registry_url == env.registry_url
    assert deserialized.base_image == env.base_image


#################################
##### DaskOnKubernetes Tests
#################################


def test_serialize_dask_on_kubernetes_environment():
    env = environments.kubernetes.DaskOnKubernetesEnvironment(
        base_image="a",
        python_dependencies=["b", "c"],
        registry_url="f",
        image_name="g",
        image_tag="h",
        max_workers=5,
    )
    serialized = DaskOnKubernetesEnvironmentSchema().dump(env)
    assert serialized["base_image"] == "a"
    assert serialized["registry_url"] == "f"
    assert serialized["image_name"] == "g"
    assert serialized["image_tag"] == "h"
    assert serialized["__version__"] == prefect.__version__
    assert serialized["max_workers"] == 5


def test_serialize_dask_on_kubernetes_environment_no_base_image():
    env = environments.kubernetes.DaskOnKubernetesEnvironment(
        python_dependencies=["b", "c"],
        registry_url="f",
        image_name="g",
        image_tag="h",
        max_workers=5,
    )
    serialized = DaskOnKubernetesEnvironmentSchema().dump(env)
    assert serialized["base_image"] == "python:3.6"
    assert serialized["registry_url"] == "f"
    assert serialized["image_name"] == "g"
    assert serialized["image_tag"] == "h"
    assert serialized["__version__"] == prefect.__version__
    assert serialized["max_workers"] == 5


def test_serialize_dask_on_kubernetes_environment_defaults():
    env = environments.kubernetes.DaskOnKubernetesEnvironment()
    serialized = DaskOnKubernetesEnvironmentSchema().dump(env)
    assert serialized["base_image"] == "python:3.6"
    assert serialized["registry_url"] == None
    assert serialized["image_name"] == None
    assert serialized["image_tag"] == None
    assert serialized["__version__"] == prefect.__version__
    assert serialized["max_workers"] == 1


def test_deserialize_empty_dask_on_kubernetes_environment():
    schema = DaskOnKubernetesEnvironmentSchema()
    with pytest.raises(marshmallow.ValidationError):
        schema.load(schema.dump({}))


def test_deserialize_minimal_dask_on_kubernetes_environment():
    schema = DaskOnKubernetesEnvironmentSchema()
    assert schema.load(schema.dump({"base_image": "a", "registry_url": "b"}))


def test_deserialize_dask_on_kubernetes_environment():
    env = environments.kubernetes.DaskOnKubernetesEnvironment(
        base_image="a", python_dependencies=["b", "c"], registry_url="f"
    )
    serialized = DaskOnKubernetesEnvironmentSchema().dump(env)
    deserialized = DaskOnKubernetesEnvironmentSchema().load(serialized)

    assert deserialized.base_image == env.base_image
    assert deserialized.registry_url == env.registry_url


def test_environment_schema_with_dask_on_kubernetes_environment():
    env = environments.kubernetes.DaskOnKubernetesEnvironment(
        base_image="a", python_dependencies=["b", "c"], registry_url="f"
    )
    serialized = DaskOnKubernetesEnvironmentSchema().dump(env)
    deserialized = DaskOnKubernetesEnvironmentSchema().load(serialized)
    assert isinstance(deserialized, environments.kubernetes.DaskOnKubernetesEnvironment)
    assert deserialized.registry_url == env.registry_url
    assert deserialized.base_image == env.base_image
