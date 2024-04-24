import copy
import re
import uuid
from unittest.mock import MagicMock, call, patch

import anyio.abc
import docker
import docker.errors
import docker.models.containers
import pytest
from docker import DockerClient
from docker.models.containers import Container
from packaging import version
from prefect_docker.credentials import DockerRegistryCredentials
from prefect_docker.worker import (
    CONTAINER_LABELS,
    DockerWorker,
    DockerWorkerJobConfiguration,
)

import prefect
from prefect.client.schemas import FlowRun
from prefect.events import RelatedResource
from prefect.exceptions import InfrastructureNotAvailable, InfrastructureNotFound
from prefect.settings import (
    PREFECT_EXPERIMENTAL_ENABLE_WORKERS,
    PREFECT_EXPERIMENTAL_WARN_WORKERS,
    get_current_settings,
    temporary_settings,
)
from prefect.testing.utilities import assert_does_not_warn
from prefect.utilities.dockerutils import get_prefect_image_name

FAKE_CONTAINER_ID = "fake-id"
FAKE_BASE_URL = "http+docker://my-url"


@pytest.fixture(autouse=True)
def enable_workers():
    with temporary_settings(
        {PREFECT_EXPERIMENTAL_ENABLE_WORKERS: 1, PREFECT_EXPERIMENTAL_WARN_WORKERS: 0}
    ):
        yield


@pytest.fixture(autouse=True)
def bypass_api_check(monkeypatch):
    monkeypatch.setenv("PREFECT_DOCKER_TEST_MODE", True)


@pytest.fixture
def mock_docker_client(monkeypatch):
    mock = MagicMock(name="DockerClient", spec=docker.DockerClient)
    mock.version.return_value = {"Version": "20.10"}

    # Build a fake container object to return

    fake_container = docker.models.containers.Container()
    fake_container.client = MagicMock(name="Container.client")
    fake_container.collection = MagicMock(name="Container.collection")
    attrs = {
        "Id": FAKE_CONTAINER_ID,
        "Name": "fake-name",
        "State": {
            "Status": "running",
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
    fake_container.stop = MagicMock()

    def fake_reload():
        nonlocal fake_container
        fake_container.attrs["State"]["Status"] = "exited"

    fake_container.reload = MagicMock(side_effect=fake_reload)

    created_container = copy.deepcopy(fake_container)
    created_container.attrs["State"]["Status"] = "created"

    # Return the fake container on lookups and creation
    mock.containers.get.return_value = fake_container
    mock.containers.create.return_value = created_container

    # Set attributes for infrastructure PID lookup
    fake_api = MagicMock(name="APIClient")
    fake_api.base_url = FAKE_BASE_URL
    mock.api = fake_api

    monkeypatch.setattr("docker.from_env", MagicMock(return_value=mock))
    return mock


@pytest.fixture
def default_docker_worker_job_configuration():
    return DockerWorkerJobConfiguration()


@pytest.fixture
def flow_run():
    return FlowRun(flow_id=uuid.uuid4())


@pytest.fixture
async def registry_credentials():
    block = DockerRegistryCredentials(
        username="my_username",
        password="my_password",
        registry_url="registry.hub.docker.com",
    )
    await block.save(name="test", overwrite=True)
    return block


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
async def test_name_cast_to_valid_container_name(
    mock_docker_client,
    requested_name,
    container_name,
    flow_run,
    default_docker_worker_job_configuration,
):
    default_docker_worker_job_configuration.name = requested_name
    default_docker_worker_job_configuration.prepare_for_flow_run(flow_run)
    async with DockerWorker(work_pool_name="test") as worker:
        await worker.run(
            flow_run=flow_run, configuration=default_docker_worker_job_configuration
        )
    mock_docker_client.containers.create.assert_called_once()
    call_name = mock_docker_client.containers.create.call_args[1].get("name")
    assert call_name == container_name


async def test_container_name_falls_back_to_null(
    mock_docker_client, flow_run, default_docker_worker_job_configuration
):
    default_docker_worker_job_configuration.name = "--__...."
    default_docker_worker_job_configuration.prepare_for_flow_run(flow_run)
    async with DockerWorker(work_pool_name="test") as worker:
        await worker.run(
            flow_run=flow_run, configuration=default_docker_worker_job_configuration
        )

    mock_docker_client.containers.create.assert_called_once()
    call_name = mock_docker_client.containers.create.call_args[1].get("name")
    assert call_name is None


@pytest.mark.parametrize("collision_count", (0, 1, 5))
async def test_container_name_includes_index_on_conflict(
    mock_docker_client,
    collision_count,
    flow_run,
    default_docker_worker_job_configuration,
):
    import docker.errors

    if collision_count:
        # Add the basic name first
        existing_names = ["test-name"]
        for i in range(1, collision_count):
            existing_names.append(f"test-name-{i}")
    else:
        existing_names = []

    def fail_if_name_exists(*args, **kwargs):
        if kwargs.get("name") in existing_names:
            raise docker.errors.APIError(
                "Conflict. The container name 'foobar' is already in use"
            )
        container = MagicMock()
        container.name = kwargs.get("name")
        return container

    mock_docker_client.containers.create.side_effect = fail_if_name_exists

    default_docker_worker_job_configuration.name = "test-name"
    default_docker_worker_job_configuration.prepare_for_flow_run(flow_run)
    async with DockerWorker(work_pool_name="test") as worker:
        await worker.run(
            flow_run=flow_run, configuration=default_docker_worker_job_configuration
        )

    assert mock_docker_client.containers.create.call_count == collision_count + 1
    call_name = mock_docker_client.containers.create.call_args[1].get("name")
    expected_name = (
        "test-name" if not collision_count else f"test-name-{collision_count}"
    )
    assert call_name == expected_name


async def test_container_creation_failure_reraises_if_not_name_conflict(
    mock_docker_client, flow_run, default_docker_worker_job_configuration
):
    import docker.errors

    mock_docker_client.containers.create.side_effect = docker.errors.APIError(
        "test error"
    )

    with pytest.raises(docker.errors.APIError, match="test error"):
        async with DockerWorker(work_pool_name="test") as worker:
            await worker.run(
                flow_run=flow_run, configuration=default_docker_worker_job_configuration
            )


async def test_uses_image_setting(
    mock_docker_client, flow_run, default_docker_worker_job_configuration
):
    default_docker_worker_job_configuration.image = "foo"
    async with DockerWorker(work_pool_name="test") as worker:
        await worker.run(
            flow_run=flow_run, configuration=default_docker_worker_job_configuration
        )
    mock_docker_client.containers.create.assert_called_once()
    call_image = mock_docker_client.containers.create.call_args[1].get("image")
    assert call_image == "foo"


async def test_uses_credentials(
    mock_docker_client,
    flow_run,
    default_docker_worker_job_configuration,
    registry_credentials,
):
    default_docker_worker_job_configuration.registry_credentials = registry_credentials
    async with DockerWorker(work_pool_name="test") as worker:
        await worker.run(
            flow_run=flow_run, configuration=default_docker_worker_job_configuration
        )
    mock_docker_client.login.assert_called_once_with(
        username="my_username",
        password="my_password",
        registry="registry.hub.docker.com",
        reauth=True,
    )


async def test_uses_volumes_setting(
    mock_docker_client, flow_run, default_docker_worker_job_configuration
):
    default_docker_worker_job_configuration.volumes = ["a:b", "c:d"]
    async with DockerWorker(work_pool_name="test") as worker:
        await worker.run(
            flow_run=flow_run, configuration=default_docker_worker_job_configuration
        )
    mock_docker_client.containers.create.assert_called_once()
    call_volumes = mock_docker_client.containers.create.call_args[1].get("volumes")
    assert "a:b" in call_volumes
    assert "c:d" in call_volumes


async def test_uses_privileged_setting(
    mock_docker_client, flow_run, default_docker_worker_job_configuration
):
    default_docker_worker_job_configuration.privileged = True
    async with DockerWorker(work_pool_name="test") as worker:
        await worker.run(
            flow_run=flow_run, configuration=default_docker_worker_job_configuration
        )

    mock_docker_client.containers.create.assert_called_once()
    assert mock_docker_client.containers.create.call_args[1].get("privileged") is True


async def test_uses_memswap_limit_setting(
    mock_docker_client, flow_run, default_docker_worker_job_configuration
):
    default_docker_worker_job_configuration.mem_limit = "500m"
    default_docker_worker_job_configuration.memswap_limit = "1g"
    async with DockerWorker(work_pool_name="test") as worker:
        await worker.run(
            flow_run=flow_run, configuration=default_docker_worker_job_configuration
        )

    mock_docker_client.containers.create.assert_called_once()
    assert (
        mock_docker_client.containers.create.call_args[1].get("memswap_limit") == "1g"
    )


async def test_uses_mem_limit_setting(
    mock_docker_client, flow_run, default_docker_worker_job_configuration
):
    default_docker_worker_job_configuration.mem_limit = "1g"
    async with DockerWorker(work_pool_name="test") as worker:
        await worker.run(
            flow_run=flow_run, configuration=default_docker_worker_job_configuration
        )
    mock_docker_client.containers.create.assert_called_once()
    assert mock_docker_client.containers.create.call_args[1].get("mem_limit") == "1g"


@pytest.mark.parametrize("networks", [[], ["a"], ["a", "b"]])
async def test_uses_network_setting(
    mock_docker_client, networks, flow_run, default_docker_worker_job_configuration
):
    default_docker_worker_job_configuration.networks = networks
    async with DockerWorker(work_pool_name="test") as worker:
        await worker.run(
            flow_run=flow_run, configuration=default_docker_worker_job_configuration
        )
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


async def test_uses_label_setting(
    mock_docker_client, flow_run, default_docker_worker_job_configuration
):
    default_docker_worker_job_configuration.labels = {"foo": "FOO", "bar": "BAR"}
    default_docker_worker_job_configuration.prepare_for_flow_run(flow_run=flow_run)
    async with DockerWorker(work_pool_name="test") as worker:
        await worker.run(
            flow_run=flow_run, configuration=default_docker_worker_job_configuration
        )
    mock_docker_client.containers.create.assert_called_once()
    call_labels = mock_docker_client.containers.create.call_args[1].get("labels")
    assert call_labels == {
        **CONTAINER_LABELS,
        "io.prefect.flow-run-id": str(flow_run.id),
        "io.prefect.flow-run-name": flow_run.name,
        "foo": "FOO",
        "bar": "BAR",
    }


async def test_uses_network_mode_setting(
    mock_docker_client, flow_run, default_docker_worker_job_configuration
):
    default_docker_worker_job_configuration.network_mode = "bridge"
    async with DockerWorker(work_pool_name="test") as worker:
        await worker.run(
            flow_run=flow_run, configuration=default_docker_worker_job_configuration
        )
    mock_docker_client.containers.create.assert_called_once()
    network_mode = mock_docker_client.containers.create.call_args[1].get("network_mode")
    assert network_mode == "bridge"


async def test_uses_env_setting(
    mock_docker_client, flow_run, default_docker_worker_job_configuration
):
    default_docker_worker_job_configuration.env = {"foo": "FOO", "bar": "BAR"}
    default_docker_worker_job_configuration.prepare_for_flow_run(flow_run=flow_run)
    async with DockerWorker(work_pool_name="test") as worker:
        await worker.run(
            flow_run=flow_run, configuration=default_docker_worker_job_configuration
        )
    mock_docker_client.containers.create.assert_called_once()
    call_env = mock_docker_client.containers.create.call_args[1].get("environment")

    flow_run_id = (
        str(flow_run.id)
        if version.parse(prefect.__version__) >= version.parse("2.13.5")
        else flow_run.id.hex
    )
    assert call_env == {
        **get_current_settings().to_environment_variables(exclude_unset=True),
        "PREFECT__FLOW_RUN_ID": flow_run_id,
        "foo": "FOO",
        "bar": "BAR",
    }


async def test_allows_unsetting_environment_variables(
    mock_docker_client, flow_run, default_docker_worker_job_configuration
):
    default_docker_worker_job_configuration.env = {"PREFECT_TEST_MODE": None}
    default_docker_worker_job_configuration.prepare_for_flow_run(flow_run=flow_run)
    async with DockerWorker(work_pool_name="test") as worker:
        await worker.run(
            flow_run=flow_run, configuration=default_docker_worker_job_configuration
        )

    mock_docker_client.containers.create.assert_called_once()
    call_env = mock_docker_client.containers.create.call_args[1].get("environment")
    assert "PREFECT_TEST_MODE" not in call_env


@pytest.mark.parametrize("localhost", ["localhost", "127.0.0.1"])
async def test_network_mode_defaults_to_host_if_using_localhost_api_on_linux(
    mock_docker_client,
    localhost,
    monkeypatch,
    flow_run,
    default_docker_worker_job_configuration,
):
    monkeypatch.setattr("sys.platform", "linux")

    default_docker_worker_job_configuration.env = dict(
        PREFECT_API_URL=f"http://{localhost}/test"
    )
    default_docker_worker_job_configuration.prepare_for_flow_run(flow_run=flow_run)
    async with DockerWorker(work_pool_name="test") as worker:
        await worker.run(
            flow_run=flow_run, configuration=default_docker_worker_job_configuration
        )
    mock_docker_client.containers.create.assert_called_once()
    network_mode = mock_docker_client.containers.create.call_args[1].get("network_mode")
    assert network_mode == "host"


async def test_network_mode_defaults_to_none_if_using_networks(
    mock_docker_client, flow_run, default_docker_worker_job_configuration
):
    # Despite using localhost for the API, we will set the network mode to `None`
    # because `networks` and `network_mode` cannot both be set.
    default_docker_worker_job_configuration.env = dict(
        PREFECT_API_URL="http://localhost/test"
    )
    default_docker_worker_job_configuration.networks = ["test"]
    default_docker_worker_job_configuration.prepare_for_flow_run(flow_run=flow_run)
    async with DockerWorker(work_pool_name="test") as worker:
        await worker.run(
            flow_run=flow_run, configuration=default_docker_worker_job_configuration
        )
    mock_docker_client.containers.create.assert_called_once()
    network_mode = mock_docker_client.containers.create.call_args[1].get("network_mode")
    assert network_mode is None


async def test_network_mode_defaults_to_none_if_using_nonlocal_api(
    mock_docker_client, flow_run, default_docker_worker_job_configuration
):
    default_docker_worker_job_configuration.env = dict(
        PREFECT_API_URL="http://foo/test"
    )
    default_docker_worker_job_configuration.prepare_for_flow_run(flow_run=flow_run)
    async with DockerWorker(work_pool_name="test") as worker:
        await worker.run(
            flow_run=flow_run, configuration=default_docker_worker_job_configuration
        )
    mock_docker_client.containers.create.assert_called_once()
    network_mode = mock_docker_client.containers.create.call_args[1].get("network_mode")
    assert network_mode is None


async def test_network_mode_defaults_to_none_if_not_on_linux(
    mock_docker_client, monkeypatch, flow_run, default_docker_worker_job_configuration
):
    monkeypatch.setattr("sys.platform", "darwin")

    default_docker_worker_job_configuration.env = dict(
        PREFECT_API_URL="http://localhost/test"
    )
    default_docker_worker_job_configuration.prepare_for_flow_run(flow_run=flow_run)
    async with DockerWorker(work_pool_name="test") as worker:
        await worker.run(
            flow_run=flow_run, configuration=default_docker_worker_job_configuration
        )

    mock_docker_client.containers.create.assert_called_once()
    network_mode = mock_docker_client.containers.create.call_args[1].get("network_mode")
    assert network_mode is None


async def test_network_mode_defaults_to_none_if_api_url_cannot_be_parsed(
    mock_docker_client, monkeypatch, flow_run, default_docker_worker_job_configuration
):
    monkeypatch.setattr("sys.platform", "darwin")

    # It is hard to actually get urlparse to fail, so we'll just raise an error
    # manually
    monkeypatch.setattr(
        "urllib.parse.urlparse", MagicMock(side_effect=ValueError("test"))
    )

    default_docker_worker_job_configuration.env = dict(
        PREFECT_API_URL="http://localhost/test"
    )
    default_docker_worker_job_configuration.prepare_for_flow_run(flow_run=flow_run)
    with pytest.warns(UserWarning, match="Failed to parse host"):
        async with DockerWorker(work_pool_name="test") as worker:
            await worker.run(
                flow_run=flow_run, configuration=default_docker_worker_job_configuration
            )

    mock_docker_client.containers.create.assert_called_once()
    network_mode = mock_docker_client.containers.create.call_args[1].get("network_mode")
    assert network_mode is None


@pytest.mark.usefixtures("use_hosted_api_server")
async def test_replaces_localhost_api_with_dockerhost_when_not_using_host_network(
    mock_docker_client,
    hosted_api_server,
    flow_run,
    default_docker_worker_job_configuration,
):
    default_docker_worker_job_configuration.network_mode = "bridge"
    default_docker_worker_job_configuration.prepare_for_flow_run(flow_run=flow_run)
    async with DockerWorker(work_pool_name="test") as worker:
        await worker.run(
            flow_run=flow_run, configuration=default_docker_worker_job_configuration
        )
    mock_docker_client.containers.create.assert_called_once()
    call_env = mock_docker_client.containers.create.call_args[1].get("environment")
    assert "PREFECT_API_URL" in call_env
    assert call_env["PREFECT_API_URL"] == hosted_api_server.replace(
        "localhost", "host.docker.internal"
    )


@pytest.mark.usefixtures("use_hosted_api_server")
async def test_does_not_replace_localhost_api_when_using_host_network(
    mock_docker_client,
    hosted_api_server,
    monkeypatch,
    flow_run,
    default_docker_worker_job_configuration,
):
    # We will warn if setting 'host' network mode on non-linux platforms
    monkeypatch.setattr("sys.platform", "linux")

    default_docker_worker_job_configuration.network_mode = "host"
    default_docker_worker_job_configuration.prepare_for_flow_run(flow_run=flow_run)
    async with DockerWorker(work_pool_name="test") as worker:
        await worker.run(
            flow_run=flow_run, configuration=default_docker_worker_job_configuration
        )
    mock_docker_client.containers.create.assert_called_once()
    call_env = mock_docker_client.containers.create.call_args[1].get("environment")
    assert "PREFECT_API_URL" in call_env
    assert call_env["PREFECT_API_URL"] == hosted_api_server


@pytest.mark.usefixtures("use_hosted_api_server")
async def test_warns_at_runtime_when_using_host_network_mode_on_non_linux_platform(
    mock_docker_client, monkeypatch, flow_run, default_docker_worker_job_configuration
):
    monkeypatch.setattr("sys.platform", "darwin")

    default_docker_worker_job_configuration.network_mode = "host"
    default_docker_worker_job_configuration.prepare_for_flow_run(flow_run=flow_run)

    with pytest.warns(
        UserWarning,
        match="'host' network mode is not supported on platform 'darwin'",
    ):
        async with DockerWorker(work_pool_name="test") as worker:
            await worker.run(
                flow_run=flow_run, configuration=default_docker_worker_job_configuration
            )

    mock_docker_client.containers.create.assert_called_once()
    network_mode = mock_docker_client.containers.create.call_args[1].get("network_mode")
    assert network_mode == "host", "The setting is passed to dockerpy still"


async def test_does_not_override_user_provided_api_host(
    mock_docker_client, flow_run, default_docker_worker_job_configuration
):
    default_docker_worker_job_configuration.env = dict(
        PREFECT_API_URL="http://localhost/api"
    )
    default_docker_worker_job_configuration.prepare_for_flow_run(flow_run=flow_run)
    async with DockerWorker(work_pool_name="test") as worker:
        await worker.run(
            flow_run=flow_run, configuration=default_docker_worker_job_configuration
        )
    mock_docker_client.containers.create.assert_called_once()
    call_env = mock_docker_client.containers.create.call_args[1].get("environment")
    assert call_env.get("PREFECT_API_URL") == "http://localhost/api"


async def test_adds_docker_host_gateway_on_linux(
    mock_docker_client, monkeypatch, flow_run, default_docker_worker_job_configuration
):
    monkeypatch.setattr("sys.platform", "linux")

    default_docker_worker_job_configuration.prepare_for_flow_run(flow_run=flow_run)
    async with DockerWorker(work_pool_name="test") as worker:
        await worker.run(
            flow_run=flow_run, configuration=default_docker_worker_job_configuration
        )

    mock_docker_client.containers.create.assert_called_once()
    call_extra_hosts = mock_docker_client.containers.create.call_args[1].get(
        "extra_hosts"
    )
    assert call_extra_hosts == {"host.docker.internal": "host-gateway"}


async def test_default_image_pull_policy_pulls_image_with_latest_tag(
    mock_docker_client, flow_run, default_docker_worker_job_configuration
):
    default_docker_worker_job_configuration.image = "prefect:latest"
    default_docker_worker_job_configuration.prepare_for_flow_run(flow_run=flow_run)
    async with DockerWorker(work_pool_name="test") as worker:
        await worker.run(
            flow_run=flow_run, configuration=default_docker_worker_job_configuration
        )
    mock_docker_client.images.pull.assert_called_once()
    mock_docker_client.images.pull.assert_called_with("prefect", "latest")


async def test_default_image_pull_policy_pulls_image_with_no_tag(
    mock_docker_client, flow_run, default_docker_worker_job_configuration
):
    default_docker_worker_job_configuration.image = "prefect"
    default_docker_worker_job_configuration.prepare_for_flow_run(flow_run=flow_run)
    async with DockerWorker(work_pool_name="test") as worker:
        await worker.run(
            flow_run=flow_run, configuration=default_docker_worker_job_configuration
        )
    mock_docker_client.images.pull.assert_called_once()
    mock_docker_client.images.pull.assert_called_with("prefect", None)


async def test_default_image_pull_policy_pulls_image_with_tag_other_than_latest_if_not_present(  # noqa
    mock_docker_client, flow_run, default_docker_worker_job_configuration
):
    from docker.errors import ImageNotFound

    mock_docker_client.images.get.side_effect = ImageNotFound("No way, bub")

    default_docker_worker_job_configuration.image = "prefect:omega"
    default_docker_worker_job_configuration.prepare_for_flow_run(flow_run=flow_run)
    async with DockerWorker(work_pool_name="test") as worker:
        await worker.run(
            flow_run=flow_run, configuration=default_docker_worker_job_configuration
        )
    mock_docker_client.images.pull.assert_called_once()
    mock_docker_client.images.pull.assert_called_with("prefect", "omega")


async def test_default_image_pull_policy_does_not_pull_image_with_tag_other_than_latest_if_present(  # noqa
    mock_docker_client, flow_run, default_docker_worker_job_configuration
):
    from docker.models.images import Image

    mock_docker_client.images.get.return_value = Image()

    default_docker_worker_job_configuration.image = "prefect:omega"
    default_docker_worker_job_configuration.prepare_for_flow_run(flow_run=flow_run)
    async with DockerWorker(work_pool_name="test") as worker:
        await worker.run(
            flow_run=flow_run, configuration=default_docker_worker_job_configuration
        )
    mock_docker_client.images.pull.assert_not_called()


async def test_image_pull_policy_always_pulls(
    mock_docker_client,
    flow_run,
    default_docker_worker_job_configuration: DockerWorkerJobConfiguration,
):
    default_docker_worker_job_configuration.image_pull_policy = "Always"
    default_docker_worker_job_configuration.image = "prefect"
    default_docker_worker_job_configuration.prepare_for_flow_run(flow_run=flow_run)
    async with DockerWorker(work_pool_name="test") as worker:
        await worker.run(
            flow_run=flow_run, configuration=default_docker_worker_job_configuration
        )
    mock_docker_client.images.get.assert_not_called()
    mock_docker_client.images.pull.assert_called_once()
    mock_docker_client.images.pull.assert_called_with("prefect", None)


async def test_image_pull_policy_never_does_not_pull(
    mock_docker_client, flow_run, default_docker_worker_job_configuration
):
    default_docker_worker_job_configuration.image_pull_policy = "Never"
    default_docker_worker_job_configuration.image = "prefect"
    default_docker_worker_job_configuration.prepare_for_flow_run(flow_run=flow_run)
    async with DockerWorker(work_pool_name="test") as worker:
        await worker.run(
            flow_run=flow_run, configuration=default_docker_worker_job_configuration
        )
    mock_docker_client.images.pull.assert_not_called()


async def test_image_pull_policy_if_not_present_pulls_image_if_not_present(
    mock_docker_client, flow_run, default_docker_worker_job_configuration
):
    from docker.errors import ImageNotFound

    mock_docker_client.images.get.side_effect = ImageNotFound("No way, bub")

    default_docker_worker_job_configuration.image_pull_policy = "IfNotPresent"
    default_docker_worker_job_configuration.image = "prefect"
    default_docker_worker_job_configuration.prepare_for_flow_run(flow_run=flow_run)
    async with DockerWorker(work_pool_name="test") as worker:
        await worker.run(
            flow_run=flow_run, configuration=default_docker_worker_job_configuration
        )
    mock_docker_client.images.pull.assert_called_once()
    mock_docker_client.images.pull.assert_called_with("prefect", None)


async def test_image_pull_policy_if_not_present_does_not_pull_image_if_present(
    mock_docker_client, flow_run, default_docker_worker_job_configuration
):
    from docker.models.images import Image

    mock_docker_client.images.get.return_value = Image()

    default_docker_worker_job_configuration.image_pull_policy = "IfNotPresent"
    default_docker_worker_job_configuration.image = "prefect"
    default_docker_worker_job_configuration.prepare_for_flow_run(flow_run=flow_run)
    async with DockerWorker(work_pool_name="test") as worker:
        await worker.run(
            flow_run=flow_run, configuration=default_docker_worker_job_configuration
        )

    mock_docker_client.images.pull.assert_not_called()


@pytest.mark.parametrize("platform", ["win32", "darwin"])
async def test_does_not_add_docker_host_gateway_on_other_platforms(
    mock_docker_client,
    monkeypatch,
    platform,
    flow_run,
    default_docker_worker_job_configuration,
):
    monkeypatch.setattr("sys.platform", platform)

    default_docker_worker_job_configuration.prepare_for_flow_run(flow_run=flow_run)
    async with DockerWorker(work_pool_name="test") as worker:
        await worker.run(
            flow_run=flow_run, configuration=default_docker_worker_job_configuration
        )

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
@pytest.mark.usefixtures("use_hosted_api_server")
async def test_warns_if_docker_version_does_not_support_host_gateway_on_linux(
    mock_docker_client,
    explicit_api_url,
    monkeypatch,
    flow_run,
    default_docker_worker_job_configuration,
):
    monkeypatch.setattr("sys.platform", "linux")

    mock_docker_client.version.return_value = {"Version": "19.1.1"}

    default_docker_worker_job_configuration.env = (
        {"PREFECT_API_URL": explicit_api_url} if explicit_api_url else {}
    )
    default_docker_worker_job_configuration.prepare_for_flow_run(flow_run=flow_run)
    with pytest.warns(
        UserWarning,
        match=(
            "`host.docker.internal` could not be automatically resolved.*"
            "feature is not supported on Docker Engine v19.1.1"
        ),
    ):
        async with DockerWorker(work_pool_name="test") as worker:
            await worker.run(
                flow_run=flow_run,
                configuration=default_docker_worker_job_configuration,
            )

    mock_docker_client.containers.create.assert_called_once()
    call_extra_hosts = mock_docker_client.containers.create.call_args[1].get(
        "extra_hosts"
    )
    assert not call_extra_hosts


async def test_does_not_warn_about_gateway_if_user_has_provided_nonlocal_api_url(
    mock_docker_client,
    monkeypatch,
    flow_run,
    default_docker_worker_job_configuration,
):
    monkeypatch.setattr("sys.platform", "linux")
    mock_docker_client.version.return_value = {"Version": "19.1.1"}

    default_docker_worker_job_configuration.env = {
        "PREFECT_API_URL": "http://my-domain.test/api"
    }
    default_docker_worker_job_configuration.prepare_for_flow_run(flow_run=flow_run)
    with assert_does_not_warn():
        async with DockerWorker(work_pool_name="test") as worker:
            await worker.run(
                flow_run=flow_run,
                configuration=default_docker_worker_job_configuration,
            )

    mock_docker_client.containers.create.assert_called_once()
    call_extra_hosts = mock_docker_client.containers.create.call_args[1].get(
        "extra_hosts"
    )
    assert not call_extra_hosts


async def test_task_infra_pid_includes_host_and_container_id(
    mock_docker_client, flow_run, default_docker_worker_job_configuration
):
    async with DockerWorker(work_pool_name="test") as worker:
        result = await worker.run(
            flow_run=flow_run, configuration=default_docker_worker_job_configuration
        )
    assert result.identifier == f"{FAKE_BASE_URL}:{FAKE_CONTAINER_ID}"


async def test_task_status_receives_result_identifier(
    mock_docker_client, flow_run, default_docker_worker_job_configuration
):
    fake_status = MagicMock(spec=anyio.abc.TaskStatus)
    async with DockerWorker(work_pool_name="test") as worker:
        result = await worker.run(
            flow_run=flow_run,
            configuration=default_docker_worker_job_configuration,
            task_status=fake_status,
        )
    fake_status.started.assert_called_once_with(result.identifier)


@pytest.mark.usefixtures("use_hosted_api_server")
@pytest.mark.parametrize("platform", ["win32", "darwin"])
async def test_does_not_warn_about_gateway_if_not_using_linux(
    mock_docker_client,
    platform,
    monkeypatch,
    flow_run,
    default_docker_worker_job_configuration,
):
    monkeypatch.setattr("sys.platform", platform)
    mock_docker_client.version.return_value = {"Version": "19.1.1"}

    with assert_does_not_warn():
        async with DockerWorker(work_pool_name="test") as worker:
            await worker.run(
                flow_run=flow_run, configuration=default_docker_worker_job_configuration
            )

    mock_docker_client.containers.create.assert_called_once()
    call_extra_hosts = mock_docker_client.containers.create.call_args[1].get(
        "extra_hosts"
    )
    assert not call_extra_hosts


@pytest.mark.flaky(max_runs=3)
async def test_container_result(
    docker_client_with_cleanup: "DockerClient",
    flow_run,
    default_docker_worker_job_configuration,
):
    async with DockerWorker(work_pool_name="test") as worker:
        result = await worker.run(
            flow_run=flow_run, configuration=default_docker_worker_job_configuration
        )
        assert bool(result)
        assert result.status_code == 0
        assert result.identifier
        _, container_id = worker._parse_infrastructure_pid(result.identifier)
        container = docker_client_with_cleanup.containers.get(container_id)
        assert container is not None


@pytest.mark.flaky(max_runs=3)
async def test_container_auto_remove(
    docker_client_with_cleanup: "DockerClient",
    flow_run,
    default_docker_worker_job_configuration,
):
    from docker.errors import NotFound

    default_docker_worker_job_configuration.auto_remove = True

    async with DockerWorker(work_pool_name="test") as worker:
        result = await worker.run(
            flow_run=flow_run, configuration=default_docker_worker_job_configuration
        )
        assert bool(result)
        assert result.status_code == 0
        assert result.identifier
        with pytest.raises(NotFound):
            _, container_id = worker._parse_infrastructure_pid(result.identifier)
            docker_client_with_cleanup.containers.get(container_id)


@pytest.mark.flaky(max_runs=3)
async def test_container_metadata(
    docker_client_with_cleanup: "DockerClient",
    flow_run,
    default_docker_worker_job_configuration,
):
    default_docker_worker_job_configuration.name = "test-container-name"
    default_docker_worker_job_configuration.labels = {"test.foo": "a", "test.bar": "b"}
    default_docker_worker_job_configuration.prepare_for_flow_run(flow_run=flow_run)
    async with DockerWorker(work_pool_name="test") as worker:
        result = await worker.run(
            flow_run=flow_run, configuration=default_docker_worker_job_configuration
        )

        _, container_id = worker._parse_infrastructure_pid(result.identifier)
    container: "Container" = docker_client_with_cleanup.containers.get(container_id)
    assert container.name == "test-container-name"
    assert container.labels["test.foo"] == "a"
    assert container.labels["test.bar"] == "b"
    assert container.image.tags[0] == get_prefect_image_name()

    for key, value in CONTAINER_LABELS.items():
        assert container.labels[key] == value


@pytest.mark.flaky(max_runs=3)
async def test_container_name_collision(
    docker_client_with_cleanup: "DockerClient",
    flow_run,
    default_docker_worker_job_configuration,
):
    # Generate a unique base name to avoid collisions with existing images
    base_name = uuid.uuid4().hex

    default_docker_worker_job_configuration.name = base_name
    default_docker_worker_job_configuration.auto_remove = False
    default_docker_worker_job_configuration.prepare_for_flow_run(flow_run)
    async with DockerWorker(work_pool_name="test") as worker:
        result = await worker.run(
            flow_run=flow_run, configuration=default_docker_worker_job_configuration
        )

        _, container_id = worker._parse_infrastructure_pid(result.identifier)
        created_container: "Container" = docker_client_with_cleanup.containers.get(
            container_id
        )
        assert created_container.name == base_name

        result = await worker.run(
            flow_run=flow_run, configuration=default_docker_worker_job_configuration
        )
        _, container_id = worker._parse_infrastructure_pid(result.identifier)
        created_container: "Container" = docker_client_with_cleanup.containers.get(
            container_id
        )
        assert created_container.name == base_name + "-1"


@pytest.mark.flaky(max_runs=3)
async def test_container_result_async(
    docker_client_with_cleanup: "DockerClient",
    flow_run,
    default_docker_worker_job_configuration,
):
    async with DockerWorker(work_pool_name="test") as worker:
        result = await worker.run(
            flow_run=flow_run, configuration=default_docker_worker_job_configuration
        )
        assert bool(result)
        assert result.status_code == 0
        assert result.identifier
        _, container_id = worker._parse_infrastructure_pid(result.identifier)
        container = docker_client_with_cleanup.containers.get(container_id)
        assert container is not None


async def test_stream_container_logs(
    capsys, mock_docker_client, flow_run, default_docker_worker_job_configuration
):
    mock_container = mock_docker_client.containers.get.return_value
    mock_container.logs = MagicMock(return_value=[b"hello", b"world"])

    async with DockerWorker(work_pool_name="test") as worker:
        await worker.run(
            flow_run=flow_run, configuration=default_docker_worker_job_configuration
        )

    captured = capsys.readouterr()
    assert "hello\nworld\n" in captured.out


async def test_logs_warning_when_container_marked_for_removal(
    caplog, mock_docker_client, flow_run, default_docker_worker_job_configuration
):
    warning = (
        "Docker container fake-name was marked for removal before logs "
        "could be retrieved. Output will not be streamed"
    )
    mock_container = mock_docker_client.containers.get.return_value
    mock_container.logs = MagicMock(side_effect=docker.errors.APIError(warning))

    async with DockerWorker(work_pool_name="test") as worker:
        await worker.run(
            flow_run=flow_run, configuration=default_docker_worker_job_configuration
        )

    assert "Docker container fake-name was marked for removal" in caplog.text


async def test_logs_when_unexpected_docker_error(
    caplog, mock_docker_client, flow_run, default_docker_worker_job_configuration
):
    mock_container = mock_docker_client.containers.get.return_value
    mock_container.logs = MagicMock(side_effect=docker.errors.APIError("..."))

    async with DockerWorker(work_pool_name="test") as worker:
        await worker.run(
            flow_run=flow_run, configuration=default_docker_worker_job_configuration
        )

    assert (
        "An unexpected Docker API error occurred while streaming output from container"
        " fake-name." in caplog.text
    )


@pytest.mark.flaky(max_runs=3)
async def test_stream_container_logs_on_real_container(
    capsys, flow_run, default_docker_worker_job_configuration
):
    default_docker_worker_job_configuration.command = "echo hello"
    async with DockerWorker(work_pool_name="test") as worker:
        await worker.run(
            flow_run=flow_run, configuration=default_docker_worker_job_configuration
        )

    captured = capsys.readouterr()
    assert "hello" in captured.out


async def test_worker_errors_out_on_ephemeral_apis():
    with pytest.raises(RuntimeError, match="ephemeral"):
        async with DockerWorker(work_pool_name="test", test_mode=False) as worker:
            await worker.run()


async def test_kill_infrastructure_calls_container_stop(
    mock_docker_client, default_docker_worker_job_configuration
):
    async with DockerWorker(work_pool_name="test") as worker:
        await worker.kill_infrastructure(
            infrastructure_pid=f"{FAKE_BASE_URL}:{FAKE_CONTAINER_ID}",
            configuration=default_docker_worker_job_configuration,
            grace_seconds=0,
        )
    mock_docker_client.containers.get.return_value.stop.assert_called_once()


async def test_kill_infrastructure_calls_container_stop_with_correct_grace_seconds(
    mock_docker_client, default_docker_worker_job_configuration
):
    GRACE_SECONDS = 42
    async with DockerWorker(work_pool_name="test") as worker:
        await worker.kill_infrastructure(
            infrastructure_pid=f"{FAKE_BASE_URL}:{FAKE_CONTAINER_ID}",
            configuration=default_docker_worker_job_configuration,
            grace_seconds=GRACE_SECONDS,
        )

    mock_docker_client.containers.get.return_value.stop.assert_called_with(
        timeout=GRACE_SECONDS
    )


async def test_kill_infrastructure_raises_infra_not_available_with_bad_host_url(
    mock_docker_client, default_docker_worker_job_configuration
):
    BAD_BASE_URL = "bad-base-url"
    expected_string = "".join(
        [
            f"Unable to stop container {FAKE_CONTAINER_ID!r}: the current Docker API ",
            f"URL {mock_docker_client.api.base_url!r} does not match the expected ",
            f"API base URL {BAD_BASE_URL}.",
        ]
    )
    with pytest.raises(InfrastructureNotAvailable, match=re.escape(expected_string)):
        async with DockerWorker(work_pool_name="test") as worker:
            await worker.kill_infrastructure(
                infrastructure_pid=f"{BAD_BASE_URL}:{FAKE_CONTAINER_ID}",
                configuration=default_docker_worker_job_configuration,
                grace_seconds=0,
            )


async def test_kill_infrastructure_raises_infra_not_found_with_bad_container_id(
    mock_docker_client, default_docker_worker_job_configuration
):
    mock_docker_client.containers.get.side_effect = [docker.errors.NotFound("msg")]

    BAD_CONTAINER_ID = "bad-container-id"
    with pytest.raises(
        InfrastructureNotFound,
        match=(
            f"Unable to stop container {BAD_CONTAINER_ID!r}: The container was not"
            " found."
        ),
    ):
        async with DockerWorker(work_pool_name="test") as worker:
            await worker.kill_infrastructure(
                infrastructure_pid=f"{FAKE_BASE_URL}:{BAD_CONTAINER_ID}",
                configuration=default_docker_worker_job_configuration,
                grace_seconds=0,
            )


async def test_emits_events(
    mock_docker_client, flow_run, default_docker_worker_job_configuration
):
    event_count = 0

    def event(*args, **kwargs):
        nonlocal event_count
        event_count += 1
        return event_count

    with patch("prefect_docker.worker.emit_event", side_effect=event) as mock_emit:
        async with DockerWorker(work_pool_name="test") as worker:
            await worker.run(
                flow_run=flow_run, configuration=default_docker_worker_job_configuration
            )

    worker_resource = worker._event_resource()
    worker_resource["prefect.resource.role"] = "worker"
    worker_related_resource = RelatedResource(__root__=worker_resource)

    mock_emit.assert_has_calls(
        [
            call(
                event="prefect.docker.container.created",
                resource={
                    "prefect.resource.id": "prefect.docker.container.fake-id",
                    "prefect.resource.name": "fake-name",
                },
                related=[worker_related_resource],
                follows=None,
            ),
            call(
                event="prefect.docker.container.running",
                resource={
                    "prefect.resource.id": "prefect.docker.container.fake-id",
                    "prefect.resource.name": "fake-name",
                },
                related=[worker_related_resource],
                follows=1,
            ),
            call(
                event="prefect.docker.container.exited",
                resource={
                    "prefect.resource.id": "prefect.docker.container.fake-id",
                    "prefect.resource.name": "fake-name",
                },
                related=[worker_related_resource],
                follows=2,
            ),
        ]
    )


async def test_emits_event_container_creation_failure(
    mock_docker_client, flow_run, default_docker_worker_job_configuration
):
    import docker.errors

    mock_docker_client.containers.create.side_effect = docker.errors.APIError(
        "test error"
    )

    worker_resource = None
    with patch("prefect_docker.worker.emit_event") as mock_emit:
        with pytest.raises(docker.errors.APIError, match="test error"):
            async with DockerWorker(work_pool_name="test") as worker:
                worker_resource = worker._event_resource()
                await worker.run(
                    flow_run=flow_run,
                    configuration=default_docker_worker_job_configuration,
                )

        mock_emit.assert_called_once_with(
            event="prefect.docker.container.creation-failed",
            resource=worker_resource,
            related=[],
        )
