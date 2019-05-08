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


def test_add_flow_to_docker():
    storage = Docker()
    f = Flow("test")
    assert f not in storage
    assert storage.add_flow(f) == "/root/.prefect/test.prefect"
    assert f.name in storage
    assert storage.flows[f.name] == "/root/.prefect/test.prefect"


def test_empty_docker_storage():
    storage = Docker()

    assert not storage.registry_url
    assert not storage.base_image
    assert not storage.image_name
    assert not storage.image_tag
    assert not storage.python_dependencies
    assert not storage.env_vars
    assert not storage.files
    assert storage.prefect_version == "0.5.3"
    assert storage.base_url == "unix://var/run/docker.sock"


def test_empty_docker_storage():
    storage = Docker(
        registry_url="test1",
        base_image="test3",
        python_dependencies=["test"],
        image_name="test4",
        image_tag="test5",
        env_vars={"test": "1"},
        base_url="test_url",
        prefect_version="master",
    )

    assert storage.registry_url == "test1"
    assert storage.base_image == "test3"
    assert storage.image_name == "test4"
    assert storage.image_tag == "test5"
    assert storage.python_dependencies == ["test"]
    assert storage.env_vars == {"test": "1"}
    assert storage.base_url == "test_url"
    assert storage.prefect_version == "master"


def test_files_not_absolute_path():
    with pytest.raises(ValueError):
        storage = Docker(files={"test": "test"})


def test_build_base_image(monkeypatch):
    storage = Docker(registry_url="reg", base_image="test")

    build_image = MagicMock(return_value=("1", "2"))
    monkeypatch.setattr("prefect.environments.storage.Docker.build_image", build_image)

    output = storage.build()
    assert output.registry_url == storage.registry_url
    assert output.image_name == "1"
    assert output.image_tag == "2"


def test_build_no_default(monkeypatch):
    storage = Docker(registry_url="reg")

    build_image = MagicMock(return_value=("1", "2"))
    monkeypatch.setattr("prefect.environments.storage.Docker.build_image", build_image)

    output = storage.build()
    assert output.registry_url == storage.registry_url
    assert output.image_name == "1"
    assert output.image_tag == "2"


def test_build_image_fails_deserialization(monkeypatch):
    flow = Flow("test")
    storage = Docker(registry_url="reg", base_image="python:3.6")

    client = MagicMock()
    monkeypatch.setattr("docker.APIClient", client)

    with pytest.raises(SerializationError):
        image_name, image_tag = storage.build_image(flow)


def test_build_image_fails_deserialization_no_registry(monkeypatch):
    storage = Docker(base_image="python:3.6")

    client = MagicMock()
    monkeypatch.setattr("docker.APIClient", client)

    with pytest.raises(SerializationError):
        image_name, image_tag = storage.build_image(push=False)


@pytest.mark.skip(reason="Needs to be mocked so it can work on CircleCI")
def test_build_image_passes(monkeypatch):
    flow = Flow("test")
    storage = Docker(registry_url="reg", base_image="python:3.6")

    pull_image = MagicMock()
    monkeypatch.setattr("prefect.environments.storage.Docker.pull_image", pull_image)

    build = MagicMock()
    monkeypatch.setattr("docker.APIClient.build", build)

    images = MagicMock(return_value=["test"])
    monkeypatch.setattr("docker.APIClient.images", images)

    image_name, image_tag = storage.build_image(flow, push=False)

    assert image_name
    assert image_tag


@pytest.mark.skip(reason="Needs to be mocked so it can work on CircleCI")
def test_build_image_passes_and_pushes(monkeypatch):
    flow = Flow("test")
    storage = Docker(registry_url="reg", base_image="python:3.6")

    pull_image = MagicMock()
    monkeypatch.setattr("prefect.environments.storage.Docker.pull_image", pull_image)

    push_image = MagicMock()
    monkeypatch.setattr("prefect.environments.storage.Docker.push_image", push_image)

    build = MagicMock()
    monkeypatch.setattr("docker.APIClient.build", build)

    images = MagicMock(return_value=["test"])
    monkeypatch.setattr("docker.APIClient.images", images)

    remove = MagicMock()
    monkeypatch.setattr("docker.APIClient.remove_image", remove)

    image_name, image_tag = storage.build_image(flow)

    assert image_name
    assert image_tag

    assert "reg" in push_image.call_args[0][0]
    assert "reg" in remove.call_args[1]["image"]


def test_build_image_fails_no_registry(monkeypatch):
    storage = Docker(base_image="python:3.6")

    client = MagicMock()
    monkeypatch.setattr("docker.APIClient", client)

    with pytest.raises(ValueError):
        image_name, image_tag = storage.build_image()


def test_create_dockerfile_from_base_image():
    storage = Docker(base_image="python:3.6")

    with tempfile.TemporaryDirectory() as tempdir:
        storage.create_dockerfile_object(directory=tempdir)

        with open(os.path.join(tempdir, "Dockerfile"), "r") as dockerfile:
            output = dockerfile.read()

        assert "FROM python:3.6" in output


def test_create_dockerfile_from_prefect_version():
    storage = Docker(prefect_version="master")

    with tempfile.TemporaryDirectory() as tempdir:
        storage.create_dockerfile_object(directory=tempdir)

        with open(os.path.join(tempdir, "Dockerfile"), "r") as dockerfile:
            output = dockerfile.read()

        assert "prefect.git@master" in output


def test_create_dockerfile_with_weird_flow_name():
    with tempfile.TemporaryDirectory() as tempdir_outside:

        with open(os.path.join(tempdir_outside, "test"), "w+") as t:
            t.write("asdf")

        with tempfile.TemporaryDirectory() as tempdir:

            storage = Docker(registry_url="test1", base_image="test3")
            f = Flow("WHAT IS THIS !!! ~~~~")
            storage.add_flow(f)
            storage.create_dockerfile_object(directory=tempdir)

            with open(os.path.join(tempdir, "Dockerfile"), "r") as dockerfile:
                output = dockerfile.read()

            assert (
                "COPY what-is-this.flow /root/.prefect/what-is-this.prefect" in output
            )


def test_create_dockerfile_from_everything():

    with tempfile.TemporaryDirectory() as tempdir_outside:

        with open(os.path.join(tempdir_outside, "test"), "w+") as t:
            t.write("asdf")

        with tempfile.TemporaryDirectory() as tempdir:

            storage = Docker(
                registry_url="test1",
                base_image="test3",
                python_dependencies=["test"],
                image_name="test4",
                image_tag="test5",
                env_vars={"test": "1"},
                files={os.path.join(tempdir_outside, "test"): "./test2"},
                base_url="test_url",
            )
            f = Flow("test")
            g = Flow("other")
            storage.add_flow(f)
            storage.add_flow(g)
            storage.create_dockerfile_object(directory=tempdir)

            with open(os.path.join(tempdir, "Dockerfile"), "r") as dockerfile:
                output = dockerfile.read()

            assert "FROM test3" in output
            assert "COPY test ./test2" in output
            assert "ENV test=1" in output
            assert "COPY healthcheck.py /root/.prefect/healthcheck.py" in output
            assert "COPY test.flow /root/.prefect/test.prefect" in output
            assert "COPY other.flow /root/.prefect/other.prefect" in output


def test_pull_image(monkeypatch):
    storage = Docker(base_image="python:3.6")

    pull = MagicMock(return_value=[{"progress": "test"}])
    monkeypatch.setattr(
        "docker.APIClient", MagicMock(pull=MagicMock(return_value=pull))
    )

    storage.pull_image()
    assert storage


def test_push_image(monkeypatch):
    storage = Docker(base_image="python:3.6")

    push = MagicMock(return_value=[{"progress": "test"}])
    monkeypatch.setattr(
        "docker.APIClient", MagicMock(push=MagicMock(return_value=push))
    )

    storage.push_image(image_name="test", image_tag="test")

    assert storage


def test_parse_output():
    storage = Docker(base_image="python:3.6")

    with pytest.raises(AttributeError):
        storage._parse_generator_output([b'"{}"\n'])

    assert storage


def test_docker_storage_name():
    storage = Docker(base_image="python:3.6")
    with pytest.raises(ValueError):
        storage.name

    storage.registry_url = "test1"
    storage.image_name = "test2"
    storage.image_tag = "test3"
    assert storage.name == "test1/test2:test3"


def test_docker_storage_doesnt_have_get_flow_method():
    storage = Docker(base_image="python:3.6")
    with pytest.raises(NotImplementedError):
        storage.get_flow("")


def test_add_similar_flows_fails():
    storage = Docker()
    flow = prefect.Flow("test")
    storage.add_flow(flow)
    with pytest.raises(ValueError):
        storage.add_flow(flow)


def test_add_flow_with_weird_name_is_cleaned():
    storage = Docker()
    flow = prefect.Flow("WELL what do you know?!~? looks like a test!!!!")
    loc = storage.add_flow(flow)
    assert "?" not in loc
    assert "!" not in loc
    assert " " not in loc
    assert "~" not in loc
