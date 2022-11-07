import uuid
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import anyio.abc
import docker
import pytest

from prefect.docker import get_prefect_image_name
from prefect.infrastructure.docker import (
    CONTAINER_LABELS,
    DockerContainer,
    DockerRegistry,
    ImagePullPolicy,
)
from prefect.testing.utilities import assert_does_not_warn

if TYPE_CHECKING:
    from docker import DockerClient
    from docker.models.containers import Container


@pytest.fixture(autouse=True)
def skip_if_docker_is_not_installed():
    pytest.importorskip("docker")


@pytest.fixture
def mock_docker_client(monkeypatch):
    docker = pytest.importorskip("docker")
    docker.models.containers = pytest.importorskip("docker.models.containers")

    mock = MagicMock(name="DockerClient", spec=docker.DockerClient)
    mock.version.return_value = {"Version": "20.10"}

    # Build a fake container object to return
    fake_container = docker.models.containers.Container()
    fake_container.client = MagicMock(name="Container.client")
    fake_container.collection = MagicMock(name="Container.collection")
    attrs = {
        "Id": "fake-id",
        "Name": "fake-name",
        "State": {
            "Status": "exited",
            "Running": False,
            "Paused": False,
            "Restarting": False,
            "OOMKilled": False,
            "Dead": True,
            "Pid": 0,
            "ExitCode": 0,
            "Error": "",
            "StartedAt": "2022-08-31T18:01:32.645851548Z",
            "FinishedAt": "2022-08-31T18:01:32.657076632Z",
        },
    }
    fake_container.collection.get().attrs = attrs
    fake_container.attrs = attrs

    # Return the fake container on lookups and creation
    mock.containers.get.return_value = fake_container
    mock.containers.create.return_value = fake_container

    monkeypatch.setattr("docker.from_env", MagicMock(return_value=mock))
    return mock


@pytest.mark.parametrize(
    "requested_name,container_name",
    [
        ("_flow_run", "flow_run"),
        ("...flow_run", "flow_run"),
        ("._-flow_run", "flow_run"),
        ("9flow-run", "9flow-run"),
        ("-flow.run", "flow.run"),
        ("flow*run", "flow-run"),
        ("flow9.-foo_bar^x", "flow9.-foo_bar-x"),
    ],
)
def test_name_cast_to_valid_container_name(
    mock_docker_client, requested_name, container_name
):

    DockerContainer(command=["echo", "hello"], name=requested_name).run()
    mock_docker_client.containers.create.assert_called_once()
    call_name = mock_docker_client.containers.create.call_args[1].get("name")
    assert call_name == container_name


def test_container_name_falls_back_to_null(mock_docker_client):
    DockerContainer(command=["echo", "hello"], name="--__....").run()
    mock_docker_client.containers.create.assert_called_once()
    call_name = mock_docker_client.containers.create.call_args[1].get("name")
    assert call_name is None


@pytest.mark.parametrize("collision_count", (0, 1, 5))
def test_container_name_includes_index_on_conflict(mock_docker_client, collision_count):
    import docker.errors

    if collision_count:
        # Add the basic name first
        existing_names = [f"test-name"]
        for i in range(1, collision_count):
            existing_names.append(f"test-name-{i}")
    else:
        existing_names = []

    def fail_if_name_exists(*args, **kwargs):
        if kwargs.get("name") in existing_names:
            raise docker.errors.APIError(
                "Conflict. The container name 'foobar' is already in use"
            )
        return MagicMock()  # A container

    mock_docker_client.containers.create.side_effect = fail_if_name_exists

    DockerContainer(command=["echo", "hello"], name="test-name").run()

    assert mock_docker_client.containers.create.call_count == collision_count + 1
    call_name = mock_docker_client.containers.create.call_args[1].get("name")
    expected_name = (
        "test-name" if not collision_count else f"test-name-{collision_count}"
    )
    assert call_name == expected_name


def test_container_creation_failure_reraises_if_not_name_conflict(
    mock_docker_client,
):
    import docker.errors

    mock_docker_client.containers.create.side_effect = docker.errors.APIError(
        "test error"
    )

    with pytest.raises(docker.errors.APIError, match="test error"):
        DockerContainer(
            command=["echo", "hello"],
        ).run()


def test_uses_image_setting(mock_docker_client):
    DockerContainer(command=["echo", "hello"], image="foo").run()
    mock_docker_client.containers.create.assert_called_once()
    call_image = mock_docker_client.containers.create.call_args[1].get("image")
    assert call_image == "foo"


def test_uses_volumes_setting(mock_docker_client):
    DockerContainer(command=["echo", "hello"], volumes=["a:b", "c:d"]).run()
    mock_docker_client.containers.create.assert_called_once()
    call_volumes = mock_docker_client.containers.create.call_args[1].get("volumes")
    assert "a:b" in call_volumes
    assert "c:d" in call_volumes


@pytest.mark.parametrize("networks", [[], ["a"], ["a", "b"]])
def test_uses_network_setting(mock_docker_client, networks):
    DockerContainer(command=["echo", "hello"], networks=networks).run()
    mock_docker_client.containers.create.assert_called_once()
    call_network = mock_docker_client.containers.create.call_args[1].get("network")

    if not networks:
        assert not call_network
    else:
        assert call_network == networks[0]

    # Additional networks must be added after
    if len(networks) <= 1:
        mock_docker_client.networks.get.assert_not_called()
    else:
        for network_name in networks[1:]:
            mock_docker_client.networks.get.assert_called_with(network_name)

        # network.connect called with the created container
        mock_docker_client.networks.get().connect.assert_called_with(
            mock_docker_client.containers.create()
        )


def test_uses_label_setting(
    mock_docker_client,
):

    DockerContainer(
        command=["echo", "hello"], labels={"foo": "FOO", "bar": "BAR"}
    ).run()
    mock_docker_client.containers.create.assert_called_once()
    call_labels = mock_docker_client.containers.create.call_args[1].get("labels")
    assert call_labels == {**CONTAINER_LABELS, "foo": "FOO", "bar": "BAR"}


def test_uses_network_mode_setting(
    mock_docker_client,
):

    DockerContainer(command=["echo", "hello"], network_mode="bridge").run()
    mock_docker_client.containers.create.assert_called_once()
    network_mode = mock_docker_client.containers.create.call_args[1].get("network_mode")
    assert network_mode == "bridge"


def test_uses_env_setting(
    mock_docker_client,
):

    DockerContainer(command=["echo", "hello"], env={"foo": "FOO", "bar": "BAR"}).run()
    mock_docker_client.containers.create.assert_called_once()
    call_env = mock_docker_client.containers.create.call_args[1].get("environment")
    assert call_env == {
        **DockerContainer._base_environment(),
        "foo": "FOO",
        "bar": "BAR",
    }


def test_allows_unsetting_environment_variables(
    mock_docker_client,
):
    DockerContainer(command=["echo", "hello"], env={"PREFECT_TEST_MODE": None}).run()
    mock_docker_client.containers.create.assert_called_once()
    call_env = mock_docker_client.containers.create.call_args[1].get("environment")
    assert "PREFECT_TEST_MODE" not in call_env


def test_uses_image_registry_setting(mock_docker_client):
    DockerContainer(
        command=["echo", "hello"],
        image_registry=DockerRegistry(
            username="foo", password="bar", registry_url="example.test"
        ),
        image_pull_policy="ALWAYS",
    ).run()

    # ensure that login occurs when DockerContainer is provided an
    # image registry
    mock_docker_client.login.assert_called_once_with(
        username="foo", password="bar", registry="example.test", reauth=True
    )


def test_uses_image_registry_client(mock_docker_client, monkeypatch):
    container = DockerContainer(
        command=["echo", "hello"],
        image_registry=DockerRegistry(
            username="foo", password="bar", registry_url="example.test"
        ),
        image_pull_policy="ALWAYS",
    )

    # ensure that DockerContainer is asking for an authenticated
    # DockerClient from DockerRegistry.
    mock_get_client = MagicMock()
    mock_get_client.return_value = mock_docker_client
    monkeypatch.setattr(container.image_registry, "get_docker_client", mock_get_client)
    container.run()
    mock_get_client.assert_called_once()
    mock_docker_client.images.pull.assert_called_once()


async def test_uses_image_registry_setting_after_save(
    mock_docker_client,
):
    # This test overlaps a bit with blocks test coverage, checking that the loaded
    # object resolves the nested reference correctly.

    await DockerRegistry(
        username="foo", password="bar", registry_url="example.test"
    ).save("test-docker-registry")

    await DockerContainer(
        command=["echo", "hello"],
        image_registry=await DockerRegistry.load("test-docker-registry"),
        image_pull_policy="ALWAYS",
    ).save("test-docker-container")

    container = await DockerContainer.load("test-docker-container")
    await container.run()

    mock_docker_client.login.assert_called_once_with(
        username="foo", password="bar", registry="example.test", reauth=True
    )


async def test_uses_image_registry_client_after_save(mock_docker_client, monkeypatch):
    await DockerRegistry(
        username="foo", password="bar", registry_url="example.test"
    ).save("test-docker-registry")

    await DockerContainer(
        command=["echo", "hello"],
        image_registry=await DockerRegistry.load("test-docker-registry"),
        image_pull_policy="ALWAYS",
    ).save("test-docker-container")

    container = await DockerContainer.load("test-docker-container")

    # ensure that the saved and reloaded DockerContainer is asking for an authenticated
    # DockerClient from DockerRegistry.
    mock_get_client = MagicMock()
    mock_get_client.return_value = mock_docker_client
    monkeypatch.setattr(container.image_registry, "get_docker_client", mock_get_client)
    await container.run()
    mock_get_client.assert_called_once()
    mock_docker_client.images.pull.assert_called_once()


@pytest.mark.parametrize("localhost", ["localhost", "127.0.0.1"])
def test_network_mode_defaults_to_host_if_using_localhost_api_on_linux(
    mock_docker_client, localhost, monkeypatch
):
    monkeypatch.setattr("sys.platform", "linux")

    DockerContainer(
        command=["echo", "hello"], env=dict(PREFECT_API_URL=f"http://{localhost}/test")
    ).run()
    mock_docker_client.containers.create.assert_called_once()
    network_mode = mock_docker_client.containers.create.call_args[1].get("network_mode")
    assert network_mode == "host"


def test_network_mode_defaults_to_none_if_using_networks(mock_docker_client):
    # Despite using localhost for the API, we will set the network mode to `None`
    # because `networks` and `network_mode` cannot both be set.
    DockerContainer(
        command=["echo", "hello"],
        env=dict(PREFECT_API_URL="http://localhost/test"),
        networks=["test"],
    ).run()
    mock_docker_client.containers.create.assert_called_once()
    network_mode = mock_docker_client.containers.create.call_args[1].get("network_mode")
    assert network_mode is None


def test_network_mode_defaults_to_none_if_using_nonlocal_api(mock_docker_client):

    DockerContainer(
        command=["echo", "hello"], env=dict(PREFECT_API_URL="http://foo/test")
    ).run()
    mock_docker_client.containers.create.assert_called_once()
    network_mode = mock_docker_client.containers.create.call_args[1].get("network_mode")
    assert network_mode is None


def test_network_mode_defaults_to_none_if_not_on_linux(mock_docker_client, monkeypatch):
    monkeypatch.setattr("sys.platform", "darwin")

    DockerContainer(
        command=["echo", "hello"], env=dict(PREFECT_API_URL="http://localhost/test")
    ).run()

    mock_docker_client.containers.create.assert_called_once()
    network_mode = mock_docker_client.containers.create.call_args[1].get("network_mode")
    assert network_mode is None


def test_network_mode_defaults_to_none_if_api_url_cannot_be_parsed(
    mock_docker_client, monkeypatch
):
    monkeypatch.setattr("sys.platform", "darwin")

    # It is hard to actually get urlparse to fail, so we'll just raise an error
    # manually
    monkeypatch.setattr(
        "urllib.parse.urlparse", MagicMock(side_effect=ValueError("test"))
    )

    with pytest.warns(UserWarning, match="Failed to parse host"):
        DockerContainer(
            command=["echo", "hello"], env=dict(PREFECT_API_URL="foo")
        ).run()

    mock_docker_client.containers.create.assert_called_once()
    network_mode = mock_docker_client.containers.create.call_args[1].get("network_mode")
    assert network_mode is None


@pytest.mark.usefixtures("use_hosted_orion")
def test_replaces_localhost_api_with_dockerhost_when_not_using_host_network(
    mock_docker_client, hosted_orion_api
):

    DockerContainer(
        command=["echo", "hello"],
        network_mode="bridge",
    ).run()
    mock_docker_client.containers.create.assert_called_once()
    call_env = mock_docker_client.containers.create.call_args[1].get("environment")
    assert "PREFECT_API_URL" in call_env
    assert call_env["PREFECT_API_URL"] == hosted_orion_api.replace(
        "localhost", "host.docker.internal"
    )


@pytest.mark.usefixtures("use_hosted_orion")
def test_does_not_replace_localhost_api_when_using_host_network(
    mock_docker_client,
    hosted_orion_api,
    monkeypatch,
):
    # We will warn if setting 'host' network mode on non-linux platforms
    monkeypatch.setattr("sys.platform", "linux")

    DockerContainer(
        command=["echo", "hello"],
        network_mode="host",
    ).run()
    mock_docker_client.containers.create.assert_called_once()
    call_env = mock_docker_client.containers.create.call_args[1].get("environment")
    assert "PREFECT_API_URL" in call_env
    assert call_env["PREFECT_API_URL"] == hosted_orion_api


@pytest.mark.usefixtures("use_hosted_orion")
def test_warns_at_runtime_when_using_host_network_mode_on_non_linux_platform(
    mock_docker_client,
    monkeypatch,
):
    monkeypatch.setattr("sys.platform", "darwin")

    with assert_does_not_warn():
        runner = DockerContainer(
            command=["echo", "hello"],
            network_mode="host",
        )

    with pytest.warns(
        UserWarning,
        match="'host' network mode is not supported on platform 'darwin'",
    ):
        runner.run()

    mock_docker_client.containers.create.assert_called_once()
    network_mode = mock_docker_client.containers.create.call_args[1].get("network_mode")
    assert network_mode == "host", "The setting is passed to dockerpy still"


def test_does_not_override_user_provided_api_host(
    mock_docker_client,
):
    DockerContainer(
        command=["echo", "hello"], env={"PREFECT_API_URL": "http://localhost/api"}
    ).run()
    mock_docker_client.containers.create.assert_called_once()
    call_env = mock_docker_client.containers.create.call_args[1].get("environment")
    assert call_env.get("PREFECT_API_URL") == "http://localhost/api"


def test_adds_docker_host_gateway_on_linux(mock_docker_client, monkeypatch):
    monkeypatch.setattr("sys.platform", "linux")

    DockerContainer(
        command=["echo", "hello"],
    ).run()

    mock_docker_client.containers.create.assert_called_once()
    call_extra_hosts = mock_docker_client.containers.create.call_args[1].get(
        "extra_hosts"
    )
    assert call_extra_hosts == {"host.docker.internal": "host-gateway"}


def test_default_image_pull_policy_pulls_image_with_latest_tag(
    mock_docker_client,
):
    DockerContainer(command=["echo", "hello"], image="prefect:latest").run()
    mock_docker_client.images.pull.assert_called_once()
    mock_docker_client.images.pull.assert_called_with("prefect", "latest")


def test_default_image_pull_policy_pulls_image_with_no_tag(
    mock_docker_client,
):
    DockerContainer(command=["echo", "hello"], image="prefect").run()
    mock_docker_client.images.pull.assert_called_once()
    mock_docker_client.images.pull.assert_called_with("prefect", None)


def test_default_image_pull_policy_pulls_image_with_tag_other_than_latest_if_not_present(
    mock_docker_client,
):
    from docker.errors import ImageNotFound

    mock_docker_client.images.get.side_effect = ImageNotFound("No way, bub")

    DockerContainer(command=["echo", "hello"], image="prefect:omega").run()
    mock_docker_client.images.pull.assert_called_once()
    mock_docker_client.images.pull.assert_called_with("prefect", "omega")


def test_default_image_pull_policy_does_not_pull_image_with_tag_other_than_latest_if_present(
    mock_docker_client,
):
    from docker.models.images import Image

    mock_docker_client.images.get.return_value = Image()

    DockerContainer(command=["echo", "hello"], image="prefect:omega").run()
    mock_docker_client.images.pull.assert_not_called()


def test_image_pull_policy_always_pulls(
    mock_docker_client,
):
    DockerContainer(
        command=["echo", "hello"],
        image="prefect",
        image_pull_policy=ImagePullPolicy.ALWAYS,
    ).run()
    mock_docker_client.images.get.assert_not_called()
    mock_docker_client.images.pull.assert_called_once()
    mock_docker_client.images.pull.assert_called_with("prefect", None)


def test_image_pull_policy_never_does_not_pull(
    mock_docker_client,
):
    DockerContainer(
        command=["echo", "hello"],
        image="prefect",
        image_pull_policy=ImagePullPolicy.NEVER,
    ).run()
    mock_docker_client.images.pull.assert_not_called()


def test_image_pull_policy_if_not_present_pulls_image_if_not_present(
    mock_docker_client,
):
    from docker.errors import ImageNotFound

    mock_docker_client.images.get.side_effect = ImageNotFound("No way, bub")

    DockerContainer(
        command=["echo", "hello"],
        image="prefect",
        image_pull_policy=ImagePullPolicy.IF_NOT_PRESENT,
    ).run()
    mock_docker_client.images.pull.assert_called_once()
    mock_docker_client.images.pull.assert_called_with("prefect", None)


def test_image_pull_policy_if_not_present_does_not_pull_image_if_present(
    mock_docker_client,
):
    from docker.models.images import Image

    mock_docker_client.images.get.return_value = Image()

    DockerContainer(
        command=["echo", "hello"],
        image="prefect",
        image_pull_policy=ImagePullPolicy.IF_NOT_PRESENT,
    ).run()
    mock_docker_client.images.pull.assert_not_called()


@pytest.mark.parametrize("platform", ["win32", "darwin"])
def test_does_not_add_docker_host_gateway_on_other_platforms(
    mock_docker_client, monkeypatch, platform
):
    monkeypatch.setattr("sys.platform", platform)

    DockerContainer(
        command=["echo", "hello"],
    ).run()

    mock_docker_client.containers.create.assert_called_once()
    call_extra_hosts = mock_docker_client.containers.create.call_args[1].get(
        "extra_hosts"
    )
    assert not call_extra_hosts


@pytest.mark.parametrize(
    "explicit_api_url",
    [
        None,
        "http://localhost/api",
        "http://127.0.0.1:2222/api",
        "http://host.docker.internal:10/foo/api",
    ],
)
@pytest.mark.usefixtures("use_hosted_orion")
def test_warns_if_docker_version_does_not_support_host_gateway_on_linux(
    mock_docker_client,
    explicit_api_url,
    monkeypatch,
):
    monkeypatch.setattr("sys.platform", "linux")

    mock_docker_client.version.return_value = {"Version": "19.1.1"}

    with pytest.warns(
        UserWarning,
        match=(
            "`host.docker.internal` could not be automatically resolved.*"
            f"feature is not supported on Docker Engine v19.1.1"
        ),
    ):
        DockerContainer(
            command=["echo", "hello"],
            env={"PREFECT_API_URL": explicit_api_url} if explicit_api_url else {},
        ).run()

    mock_docker_client.containers.create.assert_called_once()
    call_extra_hosts = mock_docker_client.containers.create.call_args[1].get(
        "extra_hosts"
    )
    assert not call_extra_hosts


def test_does_not_warn_about_gateway_if_user_has_provided_nonlocal_api_url(
    mock_docker_client,
    monkeypatch,
):
    monkeypatch.setattr("sys.platform", "linux")
    mock_docker_client.version.return_value = {"Version": "19.1.1"}

    with assert_does_not_warn():
        DockerContainer(
            command=["echo", "hello"],
            env={"PREFECT_API_URL": "http://my-domain.test/api"},
        ).run()

    mock_docker_client.containers.create.assert_called_once()
    call_extra_hosts = mock_docker_client.containers.create.call_args[1].get(
        "extra_hosts"
    )
    assert not call_extra_hosts


def test_task_status_receives_container_id(mock_docker_client):
    fake_status = MagicMock(spec=anyio.abc.TaskStatus)
    result = DockerContainer(command=["echo", "hello"], stream_output=False).run(
        task_status=fake_status
    )
    fake_status.started.assert_called_once_with(result.identifier)


@pytest.mark.usefixtures("use_hosted_orion")
@pytest.mark.parametrize("platform", ["win32", "darwin"])
def test_does_not_warn_about_gateway_if_not_using_linux(
    mock_docker_client,
    platform,
    monkeypatch,
):
    monkeypatch.setattr("sys.platform", platform)
    mock_docker_client.version.return_value = {"Version": "19.1.1"}

    with assert_does_not_warn():
        DockerContainer(
            command=["echo", "hello"],
        ).run()

    mock_docker_client.containers.create.assert_called_once()
    call_extra_hosts = mock_docker_client.containers.create.call_args[1].get(
        "extra_hosts"
    )
    assert not call_extra_hosts


@pytest.mark.service("docker")
def test_container_result(docker: "DockerClient"):
    result = DockerContainer(command=["echo", "hello"]).run()
    assert bool(result)
    assert result.status_code == 0
    assert result.identifier
    container = docker.containers.get(result.identifier)
    assert container is not None


@pytest.mark.service("docker")
def test_container_auto_remove(docker: "DockerClient"):
    from docker.errors import NotFound

    result = DockerContainer(command=["echo", "hello"], auto_remove=True).run()
    assert bool(result)
    assert result.status_code == 0
    assert result.identifier
    with pytest.raises(NotFound):
        docker.containers.get(result.identifier)


@pytest.mark.service("docker")
def test_container_metadata(docker: "DockerClient"):
    result = DockerContainer(
        command=["echo", "hello"],
        name="test-name",
        labels={"test.foo": "a", "test.bar": "b"},
    ).run()
    container: "Container" = docker.containers.get(result.identifier)
    assert container.name == "test-name"
    assert container.labels["test.foo"] == "a"
    assert container.labels["test.bar"] == "b"
    assert container.image.tags[0] == get_prefect_image_name()

    for key, value in CONTAINER_LABELS.items():
        assert container.labels[key] == value


@pytest.mark.service("docker")
def test_container_name_collision(docker: "DockerClient"):
    # Generate a unique base name to avoid collissions with existing images
    base_name = uuid.uuid4().hex

    container = DockerContainer(
        command=["echo", "hello"], name=base_name, auto_remove=False
    )
    result = container.run()
    created_container: "Container" = docker.containers.get(result.identifier)
    assert created_container.name == base_name

    result = container.run()
    created_container: "Container" = docker.containers.get(result.identifier)
    assert created_container.name == base_name + "-1"


@pytest.mark.service("docker")
async def test_container_result_async(docker: "DockerClient"):
    result = await DockerContainer(command=["echo", "hello"]).run()
    assert bool(result)
    assert result.status_code == 0
    assert result.identifier
    container = docker.containers.get(result.identifier)
    assert container is not None


def test_run_requires_command():
    container = DockerContainer(command=[])
    with pytest.raises(ValueError, match="cannot be run with empty command"):
        container.run()


def test_stream_container_logs(capsys, mock_docker_client):
    mock_container = mock_docker_client.containers.get.return_value
    mock_container.logs = MagicMock(return_value=[b"hello", b"world"])

    DockerContainer(command=["doesnt", "matter"]).run()

    captured = capsys.readouterr()
    assert "hello\nworld\n" in captured.out


def test_logs_warning_when_container_marked_for_removal(caplog, mock_docker_client):
    warning = (
        "Docker container fake-name was marked for removal before logs "
        "could be retrieved. Output will not be streamed"
    )
    mock_container = mock_docker_client.containers.get.return_value
    mock_container.logs = MagicMock(side_effect=docker.errors.APIError(warning))

    DockerContainer(
        command=["doesnt", "matter"],
    ).run()

    assert "Docker container fake-name was marked for removal" in caplog.text


def test_logs_when_unexpected_docker_error(caplog, mock_docker_client):
    mock_container = mock_docker_client.containers.get.return_value
    mock_container.logs = MagicMock(side_effect=docker.errors.APIError("..."))

    DockerContainer(
        command=["doesnt", "matter"],
    ).run()

    assert (
        "An unexpected Docker API error occured while streaming output from container fake-name."
        in caplog.text
    )


@pytest.mark.service("docker")
def test_stream_container_logs_on_real_container(capsys):
    DockerContainer(
        command=["echo", "hello"],
        stream_output=True,
    ).run()

    captured = capsys.readouterr()
    assert "hello" in captured.out
