import base64
import json
import os

import pytest

from cryptography.fernet import Fernet
import prefect
import prefect.core.registry
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


class TestContainerEnvironment:
    def test_create_container_environment(self):
        container = ContainerEnvironment(image=None)
        assert container

    @pytest.mark.skip("Circle will need to handle container building")
    def test_build_image_process(self):

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

    def test_local_environment_generates_encryption_key(self):
        env = LocalEnvironment()
        assert env.encryption_key is not None

    def test_build_local_environment(self):
        key = LocalEnvironment().build(Flow())
        assert isinstance(key, dict)
        assert isinstance(key["serialized registry"], str)

    def test_local_environment_key_is_base64_encoded_and_encrypted_registry(self):
        encryption_key = Fernet.generate_key()
        flow = Flow()
        key = LocalEnvironment(encryption_key=encryption_key).build(flow)
        decoded = base64.b64decode(key["serialized registry"])

        registry = {}  # type: dict
        prefect.core.registry.load_serialized_registry(
            decoded, encryption_key=encryption_key, dest_registry=registry
        )
        assert isinstance(registry[flow.id], Flow)

    def test_local_environment_cli(self):
        f = prefect.Flow(environment=LocalEnvironment())

        key = f.environment.build(f)

        output = f.environment.run(key, "prefect flows ids")
        assert json.loads(output.decode()) == [f.id]

    def test_local_environment_cli_run(self):
        f = prefect.Flow(environment=LocalEnvironment())

        key = f.environment.build(f)

        output = f.environment.run(key, "prefect flows run {}".format(f.id))
        assert output
