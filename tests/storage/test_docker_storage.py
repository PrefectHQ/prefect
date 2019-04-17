import os
import tempfile
from unittest.mock import MagicMock

import pytest

import prefect
from prefect import Flow
from prefect.environments.storage import Docker
from prefect.utilities.exceptions import SerializationError


def test_create_docker_storage():
    storage = Docker()
    assert storage


def test_serialize_docker_storage():
    storage = Docker()
    serialized_storage = storage.serialize()

    assert serialized_storage["type"] == "Docker"


def test_empty_docker_storage():
    storage = Docker()

    assert not storage.registry_url
    assert not storage.dockerfile
    assert not storage.base_image
    assert not storage.image_name
    assert not storage.image_tag
    assert not storage.python_dependencies
    assert not storage.env_vars
    assert not storage.files
    assert storage.flow_file_path == "/root/.prefect/flow_env.prefect"
    assert storage.base_url == "unix://var/run/docker.sock"


def test_empty_docker_storage():
    storage = Docker(
        registry_url="test1",
        dockerfile="test2",
        base_image="test3",
        python_dependencies=["test"],
        image_name="test4",
        image_tag="test5",
        env_vars={"test": "1"},
        flow_file_path="test_path",
        base_url="test_url",
    )

    assert storage.registry_url == "test1"
    assert storage.dockerfile == "test2"
    assert storage.base_image == "test3"
    assert storage.image_name == "test4"
    assert storage.image_tag == "test5"
    assert storage.python_dependencies == ["test"]
    assert storage.env_vars == {"test": "1"}
    assert storage.flow_file_path == "test_path"
    assert storage.base_url == "test_url"


def test_xor_image_dockerfile_fails():
    flow = Flow("test")
    storage = Docker(base_image="test", dockerfile="test")
    with pytest.raises(ValueError):
        storage.build(flow=flow)


def test_build(monkeypatch):
    flow = Flow("test")
    storage = Docker(registry_url="reg", base_image="test")

    build_image = MagicMock(return_value=("1", "2"))
    monkeypatch.setattr("prefect.environments.storage.Docker.build_image", build_image)

    output = storage.build(flow=flow)
    assert output.registry_url == storage.registry_url
    assert output.image_name == "1"
    assert output.image_tag == "2"
    assert output.flow_file_path == storage.flow_file_path


def test_build_no_default(monkeypatch):
    flow = Flow("test")
    storage = Docker(registry_url="reg")

    build_image = MagicMock(return_value=("1", "2"))
    monkeypatch.setattr("prefect.environments.storage.Docker.build_image", build_image)

    output = storage.build(flow=flow)
    assert output.registry_url == storage.registry_url
    assert output.image_name == "1"
    assert output.image_tag == "2"
    assert output.flow_file_path == storage.flow_file_path


def test_build_image_fails_deserialization(monkeypatch):
    flow = Flow("test")
    storage = Docker(registry_url="reg", base_image="python:3.6")

    client = MagicMock()
    monkeypatch.setattr("docker.APIClient", client)

    with pytest.raises(SerializationError):
        image_name, image_tag = storage.build_image(flow)


def test_build_image_fails_no_registry(monkeypatch):
    flow = Flow("test")
    storage = Docker(base_image="python:3.6")

    client = MagicMock()
    monkeypatch.setattr("docker.APIClient", client)

    with pytest.raises(ValueError):
        image_name, image_tag = storage.build_image(flow)


def test_create_dockerfile_from_base_image():
    flow = Flow("test")
    storage = Docker(base_image="python:3.6")

    with tempfile.TemporaryDirectory() as tempdir:
        storage.create_dockerfile_object_from_base_image(flow=flow, directory=tempdir)

        with open(os.path.join(tempdir, "Dockerfile"), "r") as dockerfile:
            output = dockerfile.read()

        assert "FROM python:3.6" in output


def test_create_dockerfile_from_base_image_separate_flow_path():
    flow = Flow("test")
    storage = Docker(base_image="python:3.6", flow_file_path="asdf.prefect")

    with tempfile.TemporaryDirectory() as tempdir:
        storage.create_dockerfile_object_from_base_image(flow=flow, directory=tempdir)

        with open(os.path.join(tempdir, "Dockerfile"), "r") as dockerfile:
            output = dockerfile.read()

        assert "COPY flow_env.prefect asdf.prefect" in output
        assert 'ENV PREFECT_ENVIRONMENT_FILE="asdf.prefect"' in output


def test_create_dockerfile_from_dockerfile():
    flow = Flow("test")

    dockerfile_str = """
    FROM prefect:0.5.0

    do something
    """
    storage = Docker(dockerfile=dockerfile_str)

    with tempfile.TemporaryDirectory() as tempdir:
        storage.create_dockerfile_object_from_dockerfile(flow=flow, directory=tempdir)

        with open(os.path.join(tempdir, "Dockerfile"), "r") as dockerfile:
            output = dockerfile.read()

        assert "FROM prefect:0.5.0" in output
        assert "do something" in output


# Docker Utilities


def test_pull_image(monkeypatch):
    storage = Docker(base_image="python:3.6")

    client = MagicMock()
    monkeypatch.setattr("docker.APIClient", client)

    storage.pull_image()

    assert storage


def test_push_image(monkeypatch):
    storage = Docker(base_image="python:3.6")

    client = MagicMock()
    monkeypatch.setattr("docker.APIClient", client)

    storage.push_image(image_name="test", image_tag="test")

    assert storage


def test_parse_output():
    storage = Docker(base_image="python:3.6")
    storage._parse_generator_output([])

    assert storage
