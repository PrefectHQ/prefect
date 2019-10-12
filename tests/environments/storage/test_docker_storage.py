import os
import sys
import tempfile
from unittest.mock import MagicMock

import cloudpickle
import pendulum
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


@pytest.mark.parametrize(
    "platform,url",
    [
        ("win32", "npipe:////./pipe/docker_engine"),
        ("darwn", "unix://var/run/docker.sock"),
    ],
)
def test_empty_docker_storage(monkeypatch, platform, url):
    monkeypatch.setattr("prefect.environments.storage.docker.sys.platform", platform)

    storage = Docker()

    assert not storage.registry_url
    assert storage.base_image.startswith("python:")
    assert not storage.image_name
    assert not storage.image_tag
    assert not storage.python_dependencies
    assert not storage.env_vars
    assert not storage.files
    assert storage.prefect_version
    assert storage.base_url == url
    assert not storage.local_image


@pytest.mark.parametrize("version_info", [(3, 5), (3, 6), (3, 7)])
def test_docker_init_responds_to_python_version(monkeypatch, version_info):
    version_mock = MagicMock(major=version_info[0], minor=version_info[1])
    monkeypatch.setattr(sys, "version_info", version_mock)
    storage = Docker()
    assert storage.base_image == "python:{}.{}".format(*version_info)


@pytest.mark.parametrize(
    "version",
    [
        ("0.5.3", "0.5.3"),
        ("0.5.3+114.g35bc7ba4", "master"),
        ("0.5.2+999.gr34343.dirty", "master"),
    ],
)
def test_docker_init_responds_to_prefect_version(monkeypatch, version):
    monkeypatch.setattr(prefect, "__version__", version[0])
    storage = Docker()
    assert storage.prefect_version == version[1]


def test_initialized_docker_storage():
    storage = Docker(
        registry_url="test1",
        base_image="test3",
        python_dependencies=["test"],
        image_name="test4",
        image_tag="test5",
        env_vars={"test": "1"},
        base_url="test_url",
        prefect_version="my-branch",
        local_image=True,
    )

    assert storage.registry_url == "test1"
    assert storage.base_image == "test3"
    assert storage.image_name == "test4"
    assert storage.image_tag == "test5"
    assert storage.python_dependencies == ["test"]
    assert storage.env_vars == {"test": "1"}
    assert storage.base_url == "test_url"
    assert storage.prefect_version == "my-branch"
    assert storage.local_image


def test_files_not_absolute_path():
    with pytest.raises(ValueError):
        storage = Docker(files={"test": "test"})


def test_build_base_image(monkeypatch):
    storage = Docker(registry_url="reg", base_image="test")

    monkeypatch.setattr("prefect.environments.storage.Docker._build_image", MagicMock())

    output = storage.build()
    assert output.registry_url == storage.registry_url
    assert output.image_name
    assert output.image_tag.startswith(str(pendulum.now("utc").year))


def test_build_no_default(monkeypatch):
    storage = Docker(registry_url="reg")

    monkeypatch.setattr("prefect.environments.storage.Docker._build_image", MagicMock())

    output = storage.build()
    assert output.registry_url == storage.registry_url
    assert output.image_name
    assert output.image_tag.startswith(str(pendulum.now("utc").year))


def test_build_sets_informative_image_name(monkeypatch):
    storage = Docker(registry_url="reg")
    storage.add_flow(Flow("test"))

    monkeypatch.setattr("prefect.environments.storage.Docker._build_image", MagicMock())

    output = storage.build()
    assert output.registry_url == storage.registry_url
    assert output.image_name == "test"
    assert output.image_tag.startswith(str(pendulum.now("utc").year))


def test_build_sets_image_name_for_multiple_flows(monkeypatch):
    storage = Docker(registry_url="reg")
    storage.add_flow(Flow("test"))
    storage.add_flow(Flow("test2"))

    monkeypatch.setattr("prefect.environments.storage.Docker._build_image", MagicMock())

    output = storage.build()
    assert output.registry_url == storage.registry_url
    assert isinstance(output.image_name, str)
    assert output.image_tag.startswith(str(pendulum.now("utc").year))


def test_build_respects_user_provided_image_name_and_tag(monkeypatch):
    storage = Docker(registry_url="reg", image_name="CUSTOM", image_tag="TAG")
    storage.add_flow(Flow("test"))

    monkeypatch.setattr("prefect.environments.storage.Docker._build_image", MagicMock())

    output = storage.build()
    assert output.registry_url == storage.registry_url
    assert output.image_name == "CUSTOM"
    assert output.image_tag == "TAG"


def test_build_respects_user_provided_image_name_and_tag_for_multiple_flows(
    monkeypatch
):
    storage = Docker(registry_url="reg", image_name="CUSTOM", image_tag="TAG")
    storage.add_flow(Flow("test"))
    storage.add_flow(Flow("test2"))

    monkeypatch.setattr("prefect.environments.storage.Docker._build_image", MagicMock())

    output = storage.build()
    assert output.registry_url == storage.registry_url
    assert output.image_name == "CUSTOM"
    assert output.image_tag == "TAG"


def test_build_sets_informative_image_name_for_weird_name_flows(monkeypatch):
    storage = Docker(registry_url="reg")
    storage.add_flow(Flow("!&& ~~ cool flow :shades:"))

    monkeypatch.setattr("prefect.environments.storage.Docker._build_image", MagicMock())

    output = storage.build()
    assert output.registry_url == storage.registry_url
    assert output.image_name == "cool-flow-shades"
    assert output.image_tag.startswith(str(pendulum.now("utc").year))


def test_build_image_fails_deserialization(monkeypatch):
    flow = Flow("test")
    storage = Docker(
        registry_url="reg",
        base_image="python:3.6",
        image_name="test",
        image_tag="latest",
    )

    client = MagicMock()
    monkeypatch.setattr("docker.APIClient", client)

    with pytest.raises(SerializationError):
        image_name, image_tag = storage._build_image(flow)


def test_build_image_fails_deserialization_no_registry(monkeypatch):
    storage = Docker(base_image="python:3.6", image_name="test", image_tag="latest")

    client = MagicMock()
    monkeypatch.setattr("docker.APIClient", client)

    with pytest.raises(SerializationError):
        image_name, image_tag = storage._build_image(push=False)


@pytest.mark.skip(reason="Needs to be mocked so it can work on CircleCI")
def test_build_image_passes(monkeypatch):
    flow = Flow("test")
    storage = Docker(
        registry_url="reg",
        base_image="python:3.6",
        image_name="test",
        image_tag="latest",
    )

    pull_image = MagicMock()
    monkeypatch.setattr("prefect.environments.storage.Docker.pull_image", pull_image)

    build = MagicMock()
    monkeypatch.setattr("docker.APIClient.build", build)

    images = MagicMock(return_value=["test"])
    monkeypatch.setattr("docker.APIClient.images", images)

    image_name, image_tag = storage._build_image(flow, push=False)

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

    image_name, image_tag = storage._build_image(flow)

    assert image_name
    assert image_tag

    assert "reg" in push_image.call_args[0][0]
    assert "reg" in remove.call_args[1]["image"]


@pytest.mark.filterwarnings("error")
def test_build_image_passes_but_raises_warning(monkeypatch):
    storage = Docker(base_image="python:3.6", image_name="test", image_tag="latest")

    client = MagicMock()
    client.images.return_value = ["name"]
    monkeypatch.setattr("docker.APIClient", MagicMock(return_value=client))

    with pytest.raises(UserWarning):
        image_name, image_tag = storage._build_image()
        assert image_name == "test"
        assert image_tag == "latest"


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


def test_pull_image(capsys, monkeypatch):
    storage = Docker(base_image="python:3.6")

    client = MagicMock()
    client.pull.return_value = [{"progress": "test", "status": "100"}]
    monkeypatch.setattr("docker.APIClient", MagicMock(return_value=client))

    storage.pull_image()
    captured = capsys.readouterr()
    printed_lines = [line for line in captured.out.split("\n") if line != ""]

    assert any(["100 test\r" in line for line in printed_lines])


def test_pull_image_raises_if_error_encountered(monkeypatch):
    storage = Docker(base_image="python:3.6")

    client = MagicMock()
    client.pull.return_value = [
        {"progress": "test"},
        {"error": "you know nothing jon snow"},
    ]
    monkeypatch.setattr("docker.APIClient", MagicMock(return_value=client))

    with pytest.raises(InterruptedError, match="you know nothing jon snow"):
        storage.pull_image()


def test_push_image(capsys, monkeypatch):
    storage = Docker(base_image="python:3.6")

    client = MagicMock()
    client.push.return_value = [{"progress": "test", "status": "100"}]
    monkeypatch.setattr("docker.APIClient", MagicMock(return_value=client))

    storage.push_image(image_name="test", image_tag="test")

    captured = capsys.readouterr()
    printed_lines = [line for line in captured.out.split("\n") if line != ""]

    assert any(["100 test\r" in line for line in printed_lines])


def test_push_image_raises_if_error_encountered(monkeypatch):
    storage = Docker(base_image="python:3.6")

    client = MagicMock()
    client.push.return_value = [
        {"progress": "test"},
        {"error": "you know nothing jon snow"},
    ]
    monkeypatch.setattr("docker.APIClient", MagicMock(return_value=client))

    with pytest.raises(InterruptedError, match="you know nothing jon snow"):
        storage.push_image(image_name="test", image_tag="test")


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


def test_docker_storage_name_registry_url_none():
    storage = Docker(base_image="python:3.6")
    with pytest.raises(ValueError):
        storage.name

    storage.image_name = "test2"
    storage.image_tag = "test3"
    assert storage.name == "test2:test3"


def test_docker_storage_get_flow_method():
    storage = Docker(base_image="python:3.6")
    with tempfile.TemporaryDirectory() as directory:

        @prefect.task
        def add_to_dict():
            with open(os.path.join(directory, "output"), "w") as tmp:
                tmp.write("success")

        with open(os.path.join(directory, "flow_env.prefect"), "w+") as env:
            flow = Flow("test", tasks=[add_to_dict])
            flow_path = os.path.join(directory, "flow_env.prefect")
            with open(flow_path, "wb") as f:
                cloudpickle.dump(flow, f)

        f = storage.get_flow(flow_path)
        assert isinstance(f, Flow)
        assert f.name == "test"
        assert len(f.tasks) == 1


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
