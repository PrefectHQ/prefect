import os
import sys
import json
import tempfile
import textwrap
from unittest.mock import MagicMock, ANY, patch
from collections import OrderedDict

import cloudpickle
import pendulum
import pytest

import prefect
from prefect import Flow
from prefect.storage import Docker


@pytest.fixture
def no_docker_host_var(monkeypatch):
    """
    This fixture is for tests that assert an unset DOCKER_HOST variable
    to avoid muddying test results from running Docker in Docker (e.g. in CI)
    """
    monkeypatch.delenv("DOCKER_HOST", raising=False)


def test_create_docker_storage():
    storage = Docker(secrets=["cloud_creds"])
    assert storage
    assert storage.logger
    assert len(storage.secrets) == 1
    assert storage.secrets == ["cloud_creds"]


def test_cant_create_docker_with_both_base_image_and_dockerfile():
    with pytest.raises(ValueError):
        Docker(dockerfile="path/to/file", base_image="python:3.7")


def test_serialize_docker_storage():
    storage = Docker()
    serialized_storage = storage.serialize()

    assert serialized_storage["type"] == "Docker"


def test_add_flow_to_docker():
    storage = Docker()
    f = Flow("test")
    assert f not in storage
    assert storage.add_flow(f) == "/opt/prefect/flows/test.prefect"
    assert f.name in storage
    assert storage.flows[f.name] == "/opt/prefect/flows/test.prefect"


def test_add_flow_to_docker_custom_prefect_dir():
    storage = Docker(prefect_directory="/usr/prefect-is-gr8")
    f = Flow("test")
    assert f not in storage
    assert storage.add_flow(f) == "/usr/prefect-is-gr8/flows/test.prefect"
    assert f.name in storage
    assert storage.flows[f.name] == "/usr/prefect-is-gr8/flows/test.prefect"
    assert storage.env_vars == {
        "PREFECT__USER_CONFIG_PATH": "/usr/prefect-is-gr8/config.toml"
    }


@pytest.mark.parametrize(
    "platform,url",
    [
        ("win32", "npipe:////./pipe/docker_engine"),
        ("darwn", "unix://var/run/docker.sock"),
    ],
)
def test_empty_docker_storage(monkeypatch, platform, url, no_docker_host_var):
    monkeypatch.setattr("prefect.storage.docker.sys.platform", platform)
    monkeypatch.setattr(sys, "version_info", MagicMock(major=3, minor=7))
    monkeypatch.setattr(prefect, "__version__", "0.9.2+c2394823")

    storage = Docker()

    assert not storage.registry_url
    assert storage.base_image == "python:3.7-slim"
    assert not storage.image_name
    assert not storage.image_tag
    assert storage.python_dependencies == ["wheel"]
    assert storage.env_vars == {"PREFECT__USER_CONFIG_PATH": "/opt/prefect/config.toml"}
    assert not storage.files
    assert storage.prefect_version
    assert storage.base_url == url
    assert storage.tls_config is False
    assert storage.build_kwargs == {}
    assert not storage.local_image
    assert not storage.ignore_healthchecks


@pytest.mark.parametrize(
    "platform,url",
    [
        ("win32", "npipe:////./pipe/docker_engine"),
        ("darwn", "unix://var/run/docker.sock"),
    ],
)
def test_empty_docker_storage_on_tagged_commit(
    monkeypatch, platform, url, no_docker_host_var
):
    monkeypatch.setattr("prefect.storage.docker.sys.platform", platform)
    monkeypatch.setattr(sys, "version_info", MagicMock(major=3, minor=7))
    monkeypatch.setattr(prefect, "__version__", "0.9.2")

    storage = Docker()

    assert not storage.registry_url
    assert storage.base_image == "prefecthq/prefect:0.9.2-python3.7"
    assert not storage.image_name
    assert not storage.image_tag
    assert storage.python_dependencies == ["wheel"]
    assert storage.env_vars == {"PREFECT__USER_CONFIG_PATH": "/opt/prefect/config.toml"}
    assert not storage.files
    assert storage.prefect_version
    assert storage.base_url == url
    assert not storage.local_image


@pytest.mark.parametrize("dev_version", ["1.0rc0", "1.0rc0+c2394823"])
def test_base_image_release_candidate_dev_image(monkeypatch, dev_version):
    monkeypatch.setattr(sys, "version_info", MagicMock(major=3, minor=7))
    monkeypatch.setattr(prefect, "__version__", dev_version)

    storage = Docker()
    assert storage.base_image == "prefecthq/prefect:1.0rc0"


def test_base_image_release_candidate(monkeypatch):
    monkeypatch.setattr(sys, "version_info", MagicMock(major=3, minor=7))
    monkeypatch.setattr(prefect, "__version__", "1.0rc1")

    storage = Docker()
    assert storage.base_image == "prefecthq/prefect:1.0rc1-python3.7"


@pytest.mark.parametrize("version_info", [(3, 5), (3, 6), (3, 7)])
def test_docker_init_responds_to_python_version(monkeypatch, version_info):
    version_mock = MagicMock(major=version_info[0], minor=version_info[1])
    monkeypatch.setattr(sys, "version_info", version_mock)
    monkeypatch.setattr(prefect, "__version__", "0.9.2+c2394823")
    storage = Docker()
    assert storage.base_image == "python:{}.{}-slim".format(*version_info)


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


def test_initialized_docker_storage(no_docker_host_var):
    storage = Docker(
        registry_url="test1",
        base_image="test3",
        python_dependencies=["test"],
        image_name="test4",
        image_tag="test5",
        env_vars={"test": "1"},
        base_url="test_url",
        tls_config={"tls": "here"},
        prefect_version="my-branch",
        local_image=True,
        build_kwargs={"nocache": True},
    )

    assert storage.registry_url == "test1"
    assert storage.base_image == "test3"
    assert storage.image_name == "test4"
    assert storage.image_tag == "test5"
    assert storage.python_dependencies == ["test", "wheel"]
    assert storage.env_vars == {
        "test": "1",
        "PREFECT__USER_CONFIG_PATH": "/opt/prefect/config.toml",
    }
    assert storage.base_url == "test_url"
    assert storage.tls_config == {"tls": "here"}
    assert storage.build_kwargs == {"nocache": True}
    assert storage.prefect_version == "my-branch"
    assert storage.local_image


def test_initialized_docker_storage_client(monkeypatch, no_docker_host_var):
    client = MagicMock()
    monkeypatch.setattr("docker.APIClient", client)

    storage = Docker(
        registry_url="test1", base_url="test_url", tls_config={"tls": "here"}
    )

    storage._get_client()

    assert client.call_args[1]["base_url"] == "test_url"
    assert client.call_args[1]["tls"] == {"tls": "here"}
    assert client.call_args[1]["version"] == "auto"


def test_env_var_precedence_docker_storage(monkeypatch, no_docker_host_var):
    monkeypatch.setenv("DOCKER_HOST", "bar")
    storage = Docker()
    assert storage.base_url
    assert storage.base_url == "bar"
    storage = Docker(base_url="foo")
    assert storage.base_url == "foo"
    storage = Docker(base_url="foo")


def test_docker_storage_allows_for_user_provided_config_locations():
    storage = Docker(env_vars={"PREFECT__USER_CONFIG_PATH": "1"})

    assert storage.env_vars == {"PREFECT__USER_CONFIG_PATH": "1"}


def test_files_not_absolute_path():
    with pytest.raises(ValueError):
        Docker(files={"test": "test"})


def test_build_base_image(monkeypatch):
    storage = Docker(registry_url="reg", base_image="test")

    monkeypatch.setattr("prefect.storage.Docker._build_image", MagicMock())

    output = storage.build()
    assert output.registry_url == storage.registry_url
    assert output.image_name
    assert output.image_tag.startswith(str(pendulum.now("utc").year))


def test_build_no_default(monkeypatch):
    storage = Docker(registry_url="reg")

    monkeypatch.setattr("prefect.storage.Docker._build_image", MagicMock())

    output = storage.build()
    assert output.registry_url == storage.registry_url
    assert output.image_name
    assert output.image_tag.startswith(str(pendulum.now("utc").year))


def test_build_sets_informative_image_name(monkeypatch):
    storage = Docker(registry_url="reg")
    storage.add_flow(Flow("test"))

    monkeypatch.setattr("prefect.storage.Docker._build_image", MagicMock())

    output = storage.build()
    assert output.registry_url == storage.registry_url
    assert output.image_name == "test"
    assert output.image_tag.startswith(str(pendulum.now("utc").year))


def test_build_sets_image_name_for_multiple_flows(monkeypatch):
    storage = Docker(registry_url="reg")
    storage.add_flow(Flow("test"))
    storage.add_flow(Flow("test2"))

    monkeypatch.setattr("prefect.storage.Docker._build_image", MagicMock())

    output = storage.build()
    assert output.registry_url == storage.registry_url
    assert isinstance(output.image_name, str)
    assert output.image_tag.startswith(str(pendulum.now("utc").year))


def test_build_respects_user_provided_image_name_and_tag(monkeypatch):
    storage = Docker(registry_url="reg", image_name="CUSTOM", image_tag="TAG")
    storage.add_flow(Flow("test"))

    monkeypatch.setattr("prefect.storage.Docker._build_image", MagicMock())

    output = storage.build()
    assert output.registry_url == storage.registry_url
    assert output.image_name == "CUSTOM"
    assert output.image_tag == "TAG"


def test_build_respects_user_provided_image_name_and_tag_for_multiple_flows(
    monkeypatch,
):
    storage = Docker(registry_url="reg", image_name="CUSTOM", image_tag="TAG")
    storage.add_flow(Flow("test"))
    storage.add_flow(Flow("test2"))

    monkeypatch.setattr("prefect.storage.Docker._build_image", MagicMock())

    output = storage.build()
    assert output.registry_url == storage.registry_url
    assert output.image_name == "CUSTOM"
    assert output.image_tag == "TAG"


def test_build_sets_informative_image_name_for_weird_name_flows(monkeypatch):
    storage = Docker(registry_url="reg")
    storage.add_flow(Flow("!&& ~~ cool flow :shades:"))

    monkeypatch.setattr("prefect.storage.Docker._build_image", MagicMock())

    output = storage.build()
    assert output.registry_url == storage.registry_url
    assert output.image_name == "cool-flow-shades"
    assert output.image_tag.startswith(str(pendulum.now("utc").year))


def test_build_image_fails_with_value_error(monkeypatch):
    flow = Flow("test")
    storage = Docker(
        registry_url="reg",
        base_image="python:3.7",
        image_name="test",
        image_tag="latest",
    )

    client = MagicMock()
    monkeypatch.setattr("docker.APIClient", client)

    with pytest.raises(ValueError, match="failed to build"):
        image_name, image_tag = storage._build_image(flow)


def test_build_image_fails_no_registry(monkeypatch):
    storage = Docker(base_image="python:3.7", image_name="test", image_tag="latest")

    client = MagicMock()
    monkeypatch.setattr("docker.APIClient", client)

    with pytest.raises(ValueError, match="failed to build"):
        image_name, image_tag = storage._build_image(push=False)


@pytest.mark.skip(reason="Needs to be mocked so it can work on CircleCI")
def test_build_image_passes(monkeypatch):
    flow = Flow("test")
    storage = Docker(
        registry_url="reg",
        base_image="python:3.7",
        image_name="test",
        image_tag="latest",
    )

    pull_image = MagicMock()
    monkeypatch.setattr("prefect.storage.Docker.pull_image", pull_image)

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
    storage = Docker(registry_url="reg", base_image="python:3.7")

    pull_image = MagicMock()
    monkeypatch.setattr("prefect.storage.Docker.pull_image", pull_image)

    push_image = MagicMock()
    monkeypatch.setattr("prefect.storage.Docker.push_image", push_image)

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


def test_build_with_default_rm_true(monkeypatch):
    storage = Docker(
        registry_url="reg",
        base_image="python:3.7",
        image_name="test",
        image_tag="latest",
    )

    pull_image = MagicMock()
    monkeypatch.setattr("prefect.storage.Docker.pull_image", pull_image)

    mock_docker_client = MagicMock()
    mock_docker_client.images.return_value = ["test"]
    with patch.object(storage, "_get_client") as mock_docker_client_fn:
        mock_docker_client_fn.return_value = mock_docker_client

        output = storage.build(push=False)
        mock_docker_client.build.assert_called_once_with(
            dockerfile=ANY, path=ANY, tag="reg/test:latest", rm=True
        )


def test_build_with_rm_override(monkeypatch):
    storage = Docker(
        registry_url="reg",
        base_image="python:3.7",
        image_name="test",
        image_tag="latest",
        build_kwargs={"rm": False},
    )

    mock_docker_client = MagicMock()
    mock_docker_client.images.return_value = ["test"]
    with patch.object(storage, "_get_client") as mock_docker_client_fn:
        mock_docker_client_fn.return_value = mock_docker_client

        output = storage.build(push=False)
        mock_docker_client.build.assert_called_once_with(
            dockerfile=ANY, path=ANY, tag="reg/test:latest", rm=False
        )


def test_create_dockerfile_from_base_image():
    storage = Docker(base_image="python:3.7")

    with tempfile.TemporaryDirectory() as tempdir:
        dpath = storage.create_dockerfile_object(directory=tempdir)

        with open(dpath, "r") as dockerfile:
            output = dockerfile.read()

        assert "FROM python:3.7" in output


def test_create_dockerfile_from_dockerfile():
    myfile = "FROM my-own-image:latest\n\nRUN echo 'hi'"
    with tempfile.TemporaryDirectory() as directory:

        with open(os.path.join(directory, "myfile"), "w") as tmp:
            tmp.write(myfile)

        storage = Docker(dockerfile=os.path.join(directory, "myfile"))
        dpath = storage.create_dockerfile_object(directory=directory)

        with open(dpath, "r") as dockerfile:
            output = dockerfile.read()

    assert output.startswith("\n" + myfile)

    # test proper indentation
    assert all(
        line == line.lstrip() for line in output.split("\n") if line not in ["\n", " "]
    )


def test_copy_files():
    with tempfile.TemporaryDirectory() as sample_top_directory:

        sample_sub_directory = os.path.join(sample_top_directory, "subdir")
        os.mkdir(sample_sub_directory)

        sample_file = os.path.join(sample_sub_directory, "test.txt")
        with open(sample_file, "w+") as t:
            t.write("asdf")

        with tempfile.TemporaryDirectory() as directory:

            storage = Docker(
                files={
                    sample_sub_directory: "/test_dir",
                    sample_file: "/path/test_file.txt",
                },
            )
            storage.add_flow(Flow("foo"))
            dpath = storage.create_dockerfile_object(directory=directory)

            with open(dpath, "r") as dockerfile:
                output = dockerfile.read()

            contents = os.listdir(directory)
            assert "subdir" in contents, contents
            assert "test.txt" in contents, contents

            assert "COPY {} /test_dir".format(
                os.path.join(directory, "subdir").replace("\\", "/") in output
            ), output

            assert "COPY {} /path/test_file.txt".format(
                os.path.join(directory, "test.txt").replace("\\", "/") in output
            ), output


def test_copy_files_with_dockerignore():
    with tempfile.TemporaryDirectory() as sample_top_directory:

        sample_sub_directory = os.path.join(sample_top_directory, "subdir")
        os.mkdir(sample_sub_directory)

        sample_file = os.path.join(sample_sub_directory, "test.txt")
        with open(sample_file, "w+") as t:
            t.write("asdf")

        dockerignore = os.path.join(sample_sub_directory, ".dockerignore")
        with open(dockerignore, "w+") as t:
            t.write("test.txt")

        with tempfile.TemporaryDirectory() as directory:

            storage = Docker(
                files={
                    sample_sub_directory: "/test_dir",
                    sample_file: "/path/test_file.txt",
                },
                dockerignore=dockerignore,
            )
            storage.add_flow(Flow("foo"))
            storage.create_dockerfile_object(directory=directory)

            contents = os.listdir(directory)
            assert ".dockerignore" in contents, contents


def test_extra_dockerfile_commands():
    with tempfile.TemporaryDirectory() as directory:

        storage = Docker(
            extra_dockerfile_commands=[
                'RUN echo "I\'m a little tea pot"',
            ],
        )
        storage.add_flow(Flow("foo"))
        dpath = storage.create_dockerfile_object(directory=directory)

        with open(dpath, "r") as dockerfile:
            output = dockerfile.read()

        assert "COPY {} /path/test_file.txt".format(
            'RUN echo "I\'m a little tea pot"\n' in output
        ), output


def test_dockerfile_env_vars(tmpdir):
    env_vars = OrderedDict(
        [
            ("NUM", 1),
            ("STR_WITH_SPACES", "Hello world!"),
            ("STR_WITH_QUOTES", 'Hello "friend"'),
            ("STR_WITH_SINGLE_QUOTES", "'foo'"),
        ]
    )
    storage = Docker(
        env_vars=env_vars,
    )
    storage.add_flow(Flow("foo"))
    dpath = storage.create_dockerfile_object(directory=str(tmpdir))

    with open(dpath, "r") as dockerfile:
        output = dockerfile.read()

    expected = textwrap.dedent(
        """
        ENV NUM=1 \\
            STR_WITH_SPACES='Hello world!' \\
            STR_WITH_QUOTES='Hello "friend"' \\
            STR_WITH_SINGLE_QUOTES="'foo'" \\
        """
    )

    assert expected in output


def test_create_dockerfile_from_dockerfile_uses_tempdir_path():
    myfile = "FROM my-own-image:latest\n\nRUN echo 'hi'"
    with tempfile.TemporaryDirectory() as tempdir_outside:

        with open(os.path.join(tempdir_outside, "test"), "w+") as t:
            t.write("asdf")

        with tempfile.TemporaryDirectory() as directory:

            with open(os.path.join(directory, "myfile"), "w") as tmp:
                tmp.write(myfile)

            storage = Docker(
                dockerfile=os.path.join(directory, "myfile"),
                files={os.path.join(tempdir_outside, "test"): "./test2"},
            )
            storage.add_flow(Flow("foo"))
            dpath = storage.create_dockerfile_object(directory=directory)

            with open(dpath, "r") as dockerfile:
                output = dockerfile.read()

            assert (
                "COPY {} /opt/prefect/flows/foo.prefect".format(
                    os.path.join(directory, "foo.flow").replace("\\", "/")
                )
                in output
            ), output
            assert (
                "COPY {} ./test2".format(
                    os.path.join(directory, "test").replace("\\", "/")
                )
                in output
            ), output
            assert (
                "COPY {} /opt/prefect/healthcheck.py".format(
                    os.path.join(directory, "healthcheck.py").replace("\\", "/")
                )
                in output
            )

    assert output.startswith("\n" + myfile)

    # test proper indentation
    assert all(
        line == line.lstrip() for line in output.split("\n") if line not in ["\n", " "]
    )


@pytest.mark.parametrize(
    "prefect_version",
    [
        ("0.5.3", ("FROM prefecthq/prefect:0.5.3-python3.7",)),
        (
            "master",
            (
                "FROM python:3.7-slim",
                "pip show prefect || pip install git+https://github.com/PrefectHQ/prefect.git@master",
            ),
        ),
        (
            "424be6b5ed8d3be85064de4b95b5c3d7cb665510",
            (
                "FROM python:3.7-slim",
                "apt update && apt install -y gcc git make && rm -rf /var/lib/apt/lists/*",
                "pip show prefect || pip install git+https://github.com/PrefectHQ/prefect.git@424be6b5ed8d3be85064de4b95b5c3d7cb665510#egg=prefect[all_orchestration_extras]",
            ),
        ),
    ],
)
def test_create_dockerfile_from_prefect_version(monkeypatch, prefect_version):
    monkeypatch.setattr(sys, "version_info", MagicMock(major=3, minor=7))

    storage = Docker(prefect_version=prefect_version[0])

    with tempfile.TemporaryDirectory() as tempdir:
        dpath = storage.create_dockerfile_object(directory=tempdir)

        with open(dpath, "r") as dockerfile:
            output = dockerfile.read()

        for content in prefect_version[1]:
            assert content in output


def test_create_dockerfile_with_weird_flow_name():
    with tempfile.TemporaryDirectory() as tempdir_outside:

        with open(os.path.join(tempdir_outside, "test"), "w+") as t:
            t.write("asdf")

        with tempfile.TemporaryDirectory() as tempdir:

            storage = Docker(registry_url="test1", base_image="test3")
            f = Flow("WHAT IS THIS !!! ~~~~")
            storage.add_flow(f)
            dpath = storage.create_dockerfile_object(directory=tempdir)

            with open(dpath, "r") as dockerfile:
                output = dockerfile.read()

            assert (
                "COPY what-is-this.flow /opt/prefect/flows/what-is-this.prefect"
                in output
            )


def test_create_dockerfile_with_complex_python_dependencies():
    with tempfile.TemporaryDirectory() as tempdir_outside:

        with open(os.path.join(tempdir_outside, "test"), "w+") as t:
            t.write("asdf")

        with tempfile.TemporaryDirectory() as tempdir:

            storage = Docker(
                registry_url="test1",
                base_image="test3",
                python_dependencies=["lib[flavor]<2.0.0,>=1.1.1", "other-lib"],
            )
            dpath = storage.create_dockerfile_object(directory=tempdir)

            with open(dpath, "r") as dockerfile:
                output = dockerfile.read()

            assert (
                "RUN pip install 'lib[flavor]<2.0.0,>=1.1.1' 'other-lib' 'wheel'"
                in output
            )


def test_create_dockerfile_with_weird_flow_name_custom_prefect_dir(tmpdir):

    with open(os.path.join(tmpdir, "test"), "w+") as t:
        t.write("asdf")

    storage = Docker(
        registry_url="test1",
        base_image="test3",
        prefect_directory="/tmp/prefect-is-c00l",
    )
    f = Flow("WHAT IS THIS !!! ~~~~")
    storage.add_flow(f)
    dpath = storage.create_dockerfile_object(directory=tmpdir)

    with open(dpath, "r") as dockerfile:
        output = dockerfile.read()

    assert (
        "COPY what-is-this.flow /tmp/prefect-is-c00l/flows/what-is-this.prefect"
        in output
    )


def test_create_dockerfile_from_everything(no_docker_host_var):

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
                files={os.path.join(tempdir_outside, "test"): "./test2"},
                base_url="test_url",
            )
            f = Flow("test")
            g = Flow("other")
            storage.add_flow(f)
            storage.add_flow(g)
            dpath = storage.create_dockerfile_object(directory=tempdir)

            with open(dpath, "r") as dockerfile:
                output = dockerfile.read()

            assert "FROM test3" in output
            assert "COPY test ./test2" in output
            assert "COPY healthcheck.py /opt/prefect/healthcheck.py" in output
            assert "COPY test.flow /opt/prefect/flows/test.prefect" in output
            assert "COPY other.flow /opt/prefect/flows/other.prefect" in output


def test_create_dockerfile_with_flow_file(no_docker_host_var, tmpdir):

    contents = """from prefect import Flow\nf=Flow('test-flow')"""

    full_path = os.path.join(tmpdir, "flow.py")

    with open(full_path, "w") as f:
        f.write(contents)

    with open(os.path.join(tmpdir, "test"), "w+") as t:
        t.write("asdf")

    with tempfile.TemporaryDirectory() as tempdir_inside:

        storage = Docker(
            files={full_path: "flow.py"}, stored_as_script=True, path="flow.py"
        )
        f = Flow("test-flow")
        storage.add_flow(f)
        dpath = storage.create_dockerfile_object(directory=tempdir_inside)

        with open(dpath, "r") as dockerfile:
            output = dockerfile.read()

        assert "COPY flow.py flow.py" in output

        storage = Docker(files={full_path: "flow.py"}, stored_as_script=True)
        f = Flow("test-flow")
        storage.add_flow(f)

        with pytest.raises(ValueError):
            storage.create_dockerfile_object(directory=tempdir_inside)


@pytest.mark.parametrize("ignore_healthchecks", [True, False])
def test_run_healthchecks_arg(ignore_healthchecks):

    with tempfile.TemporaryDirectory() as tempdir_outside:

        with open(os.path.join(tempdir_outside, "test"), "w+") as t:
            t.write("asdf")

        with tempfile.TemporaryDirectory() as tempdir:
            storage = Docker(ignore_healthchecks=ignore_healthchecks)

            f = Flow("test")
            storage.add_flow(f)
            dpath = storage.create_dockerfile_object(directory=tempdir)

            with open(dpath, "r") as dockerfile:
                output = dockerfile.read()

            if ignore_healthchecks:
                assert "RUN python /opt/prefect/healthcheck.py" not in output
            else:
                assert "RUN python /opt/prefect/healthcheck.py" in output


@pytest.mark.parametrize("ignore_healthchecks", [True, False])
def test_run_healthchecks_arg_custom_prefect_dir(ignore_healthchecks, tmpdir):

    with open(os.path.join(tmpdir, "test"), "w+") as t:
        t.write("asdf")

    storage = Docker(
        ignore_healthchecks=ignore_healthchecks, prefect_directory="/usr/local/prefect"
    )

    f = Flow("test")
    storage.add_flow(f)
    dpath = storage.create_dockerfile_object(directory=tmpdir)

    with open(dpath, "r") as dockerfile:
        output = dockerfile.read()

    if ignore_healthchecks:
        assert "RUN python /usr/local/prefect/healthcheck.py" not in output
    else:
        assert "RUN python /usr/local/prefect/healthcheck.py" in output


def test_pull_image(capsys, monkeypatch):
    storage = Docker(base_image="python:3.7")

    client = MagicMock()
    client.pull.return_value = [{"progress": "test", "status": "100"}]
    monkeypatch.setattr("docker.APIClient", MagicMock(return_value=client))

    storage.pull_image()
    captured = capsys.readouterr()
    printed_lines = [line for line in captured.out.split("\n") if line != ""]

    assert any("100 test\r" in line for line in printed_lines)


def test_pull_image_raises_if_error_encountered(monkeypatch):
    storage = Docker(base_image="python:3.7")

    client = MagicMock()
    client.pull.return_value = [
        {"progress": "test"},
        {"error": "you know nothing jon snow"},
    ]
    monkeypatch.setattr("docker.APIClient", MagicMock(return_value=client))

    with pytest.raises(InterruptedError, match="you know nothing jon snow"):
        storage.pull_image()


def test_push_image(capsys, monkeypatch):
    storage = Docker(base_image="python:3.7")

    client = MagicMock()
    client.push.return_value = [{"progress": "test", "status": "100"}]
    monkeypatch.setattr("docker.APIClient", MagicMock(return_value=client))

    storage.push_image(image_name="test", image_tag="test")

    captured = capsys.readouterr()
    printed_lines = [line for line in captured.out.split("\n") if line != ""]

    assert any("100 test\r" in line for line in printed_lines)


def test_push_image_raises_if_error_encountered(monkeypatch):
    storage = Docker(base_image="python:3.7")

    client = MagicMock()
    client.push.return_value = [
        {"progress": "test"},
        {"error": "you know nothing jon snow"},
    ]
    monkeypatch.setattr("docker.APIClient", MagicMock(return_value=client))

    with pytest.raises(InterruptedError, match="you know nothing jon snow"):
        storage.push_image(image_name="test", image_tag="test")


def test_docker_storage_name():
    storage = Docker(base_image="python:3.7")
    with pytest.raises(ValueError):
        storage.name

    storage.registry_url = "test1"
    storage.image_name = "test2"
    storage.image_tag = "test3"
    assert storage.name == "test1/test2:test3"


@pytest.mark.parametrize(
    "contents,expected",
    [
        pytest.param({"stream": "hello"}, "hello\n", id="stream key"),
        pytest.param({"message": "hello"}, "hello\n", id="message key"),
        pytest.param(
            {"errorDetail": {"message": "hello"}}, "hello\n", id="errorDetail key"
        ),
        pytest.param(
            {"errorDetail": {"unknown": "hello"}},
            "",
            id="errorDetail unknown key",
        ),
        pytest.param({"unknown": "hello"}, "", id="unknown key"),
        pytest.param([], "", id="empty generator"),
        pytest.param([{}, {}], "", id="empty dicts"),
        pytest.param(["", ""], "", id="empty strings"),
        pytest.param(
            [
                {"stream": "hello"},
                {"stream": "world"},
            ],
            "hello\nworld\n",
            id="multiple items",
        ),
    ],
)
def test_docker_storage_output_stream(contents, expected, capsys):
    if not isinstance(contents, list):
        contents = [contents]
    contents = [json.dumps(item).encode() for item in contents]
    Docker._parse_generator_output(contents)
    assert capsys.readouterr().out == expected


def test_docker_storage_name_registry_url_none():
    storage = Docker(base_image="python:3.7")
    with pytest.raises(ValueError):
        storage.name

    storage.image_name = "test2"
    storage.image_tag = "test3"
    assert storage.name == "test2:test3"


def test_docker_storage_get_flow_method(tmpdir):
    flow_dir = str(tmpdir.mkdir("flows"))

    flow = Flow("test")
    flow_path = os.path.join(flow_dir, "test.prefect")
    with open(flow_path, "wb") as f:
        cloudpickle.dump(flow, f)

    storage = Docker(base_image="python:3.7", prefect_directory=str(tmpdir))
    storage.add_flow(flow)

    f = storage.get_flow(flow.name)
    assert isinstance(f, Flow)
    assert f.name == "test"


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
