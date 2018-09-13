import json
import os

import pytest

import prefect
from prefect import Flow
from prefect.environments import (
    ContainerEnvironment,
    Environment,
    LocalEnvironment,
    Secret,
)

#################################
##### Secret Tests
#################################


def test_create_secret():
    secret = Secret(name="test")
    assert secret


def test_secret_value_none():
    secret = Secret(name="test")
    assert not secret.value


def test_secret_value_set():
    secret = Secret(name="test")
    secret.value = "test_value"
    assert secret.value


#################################
##### Environment Tests
#################################


def test_create_environment():
    environment = Environment()
    assert environment


def test_environment_secrets():
    secrets = [Secret(name="test")]
    environment = Environment(secrets=secrets)
    assert environment.secrets


def test_environment_secrets_none():
    environment = Environment()
    assert not environment.secrets


def test_environment_build_error():
    environment = Environment()
    with pytest.raises(NotImplementedError):
        environment.build(1)


#################################
##### Container Tests
#################################


def test_create_container():
    container = ContainerEnvironment(image="image", tag="tag")
    assert container


def test_container_image():
    container = ContainerEnvironment(image="image", tag="tag")
    assert container.image == "image"


def test_container_tag():
    container = ContainerEnvironment(image="image", tag="tag")
    assert container.tag == "tag"


def test_container_tag_none():
    container = ContainerEnvironment(image="image", tag=None)
    assert container.tag == "image"


def test_container_python_dependencies():
    container = ContainerEnvironment(
        image="image", tag=None, python_dependencies=["dependency"]
    )
    assert len(container.python_dependencies) == 1
    assert container.python_dependencies[0] == "dependency"


def test_container_client():
    container = ContainerEnvironment(image="image", tag="tag")
    assert container.client


@pytest.mark.skip("Circle will need to handle container building")
def test_build_image_process():

    personal_access_token = Secret(name="PERSONAL_ACCESS_TOKEN")
    personal_access_token.value = os.getenv("PERSONAL_ACCESS_TOKEN", None)

    container = ContainerEnvironment(
        image="python:3.6", tag="tag", secrets=[personal_access_token]
    )
    image = container.build(Flow())
    assert image

    # Need to test running stuff in container, however circleci won't be able to build
    # a container


#################################
##### LocalEnvironment Tests
#################################


class TestLocalEnvironment:
    def test_create_local_environment(self):
        env = LocalEnvironment()
        assert env
        assert env.encryption_key

    def test_build_local_environment(self):
        key = LocalEnvironment().build(Flow())
        assert isinstance(key, bytes)

    def test_local_environment_cli(self):
        f = prefect.Flow(environment=LocalEnvironment())

        key = f.environment.build(f)
        output = f.environment.run(key, "prefect flows ids")
        assert json.loads(output.decode()) == {
            f.id: dict(project=f.project, name=f.name, version=f.version)
        }
