import json
import os

import pytest

import prefect
from prefect import Flow
from prefect.environments import ContainerEnvironment, Environment, LocalEnvironment

#################################
##### Environment Tests
#################################


def test_create_environment():
    environment = Environment()
    assert environment


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
    assert container.tag


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

    container = ContainerEnvironment(image="python:3.6", tag="tag")
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
        assert env.encryption_key is None

    def test_build_local_environment(self):
        key = LocalEnvironment().build(Flow())
        assert isinstance(key, LocalEnvironment)

    @pytest.mark.skip("Cloudpickle truncation error")
    def test_local_environment_cli(self):
        f = prefect.Flow(environment=LocalEnvironment())

        key = f.environment.build(f).serialized
        output = f.environment.run(key, "prefect flows ids")
        assert json.loads(output.decode()) == {
            f.id: dict(project=f.project, name=f.name, version=f.version)
        }
