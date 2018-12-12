import base64
import json
import os

import pytest

import tempfile
from cryptography.fernet import Fernet, InvalidToken
import prefect
from prefect import Flow, Task, Parameter
from prefect.environments import (
    ContainerEnvironment,
    Environment,
    LocalEnvironment,
    from_file,
)


def error_flow():
    @prefect.task
    def error_task():
        1 / 0

    with Flow("error flow") as flow:
        error_task()

    return flow


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
        container = ContainerEnvironment(base_image=None, registry_url=None)
        assert container

    @pytest.mark.skip("Circle will need to handle container building")
    def test_build_image_process(self):

        container = ContainerEnvironment(
            base_image="python:3.6", tag="tag", registry_url=""
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

    def test_local_environment_generates_encryption_key(self):
        env = LocalEnvironment()
        assert env.encryption_key is not None

    def test_local_environment_stores_encryption_key(self):
        key = Fernet.generate_key()
        env = LocalEnvironment(encryption_key=key)
        assert env.encryption_key == key

    def test_local_environment_validates_encryption_key(self):
        with pytest.raises(ValueError) as exc:
            LocalEnvironment(encryption_key="hi")
        assert "Invalid encryption key" in str(exc)

    def test_serialize_flow(self):
        assert isinstance(LocalEnvironment().serialize_flow_to_bytes(Flow()), bytes)

    def test_deserialize_flow(self):
        f = Flow()
        f.add_task(Task())
        f.add_task(Parameter("x"))

        env = LocalEnvironment()
        serialized = env.serialize_flow_to_bytes(f)
        deserialized = env.deserialize_flow_from_bytes(serialized)

        assert isinstance(deserialized, Flow)
        assert len(deserialized.tasks) == 2
        assert {p.name for p in deserialized.parameters()} == {"x"}

    def test_deserialize_flow_fails_if_not_same_environment(self):
        serialized = LocalEnvironment().serialize_flow_to_bytes(Flow())
        with pytest.raises(InvalidToken):
            LocalEnvironment().deserialize_flow_from_bytes(serialized)

    def test_deserialize_flow_succeeds_with_same_key(self):
        key = Fernet.generate_key()
        serialized = LocalEnvironment(encryption_key=key).serialize_flow_to_bytes(
            Flow()
        )
        deserialized = LocalEnvironment(encryption_key=key).deserialize_flow_from_bytes(
            serialized
        )
        assert len(deserialized.tasks) == 0

    def test_build_local_environment(self):
        env = LocalEnvironment()
        new_env = env.build(Flow())
        assert isinstance(new_env, LocalEnvironment)
        assert env.serialized_flow is None
        assert new_env.serialized_flow is not None

    def test_run(self):
        env = LocalEnvironment()
        state = env.build(error_flow()).run()
        assert state.is_failed()

    def test_run_without_build(self):
        env = LocalEnvironment()

        with pytest.raises(ValueError) as exc:
            env.run()
        assert "No serialized flow found!" in str(exc)

    def test_to_and_from_file(self):
        env = LocalEnvironment().build(error_flow())
        with tempfile.NamedTemporaryFile() as tmp:
            env.to_file(tmp.name)
            new_env = from_file(tmp.name)

        assert isinstance(new_env, LocalEnvironment)
        assert new_env.encryption_key == env.encryption_key
        assert new_env.serialized_flow == env.serialized_flow

    def test_serialize(self):
        env = LocalEnvironment().build(error_flow())
        s = env.serialize()
        assert isinstance(s, dict)
