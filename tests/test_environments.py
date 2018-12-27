import base64
import json
import os
import tempfile

import pytest
from cryptography.fernet import Fernet, InvalidToken

import prefect
from prefect import Flow, Parameter, Task
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
            base_image="python:3.6", image_tag="tag", registry_url=""
        )
        image = container.build(Flow())
        assert image

    def test_basic_create_dockerfile(self):
        container = ContainerEnvironment(base_image="python:3.6", registry_url="")
        with tempfile.TemporaryDirectory(prefix="prefect-tests") as tmp:
            container.create_dockerfile(Flow(), directory=tmp)
            with open(os.path.join(tmp, "Dockerfile"), "r") as f:
                dockerfile = f.read()

        assert "FROM python:3.6" in dockerfile
        assert "RUN pip install ./prefect" in dockerfile
        assert "RUN mkdir /root/.prefect/" in dockerfile
        assert "COPY config.toml /root/.prefect/config.toml" in dockerfile

    def test_create_dockerfile_with_environment_variables(self):
        container = ContainerEnvironment(
            base_image="python:3.6",
            registry_url="",
            env_vars=dict(
                X=2, Y='"/a/quoted/string/path"', Z="/an/unquoted/string/path"
            ),
        )
        with tempfile.TemporaryDirectory(prefix="prefect-tests") as tmp:
            container.create_dockerfile(Flow(), directory=tmp)
            with open(os.path.join(tmp, "Dockerfile"), "r") as f:
                dockerfile = f.read()

        assert "ENV X=2" in dockerfile
        assert 'ENV Y="/a/quoted/string/path"' in dockerfile
        assert "ENV Z=/an/unquoted/string/path" in dockerfile

    def test_create_dockerfile_with_copy_files(self):
        container = ContainerEnvironment(
            base_image="python:3.6",
            registry_url="",
            files={
                "/my/config": "/root/dockerconfig",
                ".secret_file": "./.secret_file",
            },
        )
        with tempfile.TemporaryDirectory(prefix="prefect-tests") as tmp:
            container.create_dockerfile(Flow(), directory=tmp)
            with open(os.path.join(tmp, "Dockerfile"), "r") as f:
                dockerfile = f.read()

        assert "COPY /my/config /root/dockerconfig" in dockerfile
        assert "COPY .secret_file ./.secret_file" in dockerfile
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
