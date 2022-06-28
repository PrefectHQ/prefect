import sys
import warnings
from pathlib import Path
from unittest.mock import MagicMock

import anyio
import anyio.abc
import pytest

import prefect
from prefect.docker import Image, ImageNotFound, NotFound, docker_client
from prefect.flow_runners import (
    MIN_COMPAT_PREFECT_VERSION,
    DockerFlowRunner,
    ImagePullPolicy,
    get_prefect_image_name,
)
from prefect.orion.schemas.data import DataDocument
from prefect.settings import PREFECT_API_URL, temporary_settings
from prefect.testing.utilities import assert_does_not_warn


class TestDockerFlowRunner:
    @pytest.fixture(autouse=True)
    def skip_if_docker_is_not_installed(self):
        pytest.importorskip("docker")

    @pytest.fixture
    def mock_docker_client(self, monkeypatch):
        docker = pytest.importorskip("docker")

        mock = MagicMock(spec=docker.DockerClient)
        mock.version.return_value = {"Version": "20.10"}

        monkeypatch.setattr(
            "prefect.flow_runners.DockerFlowRunner._get_client",
            MagicMock(return_value=mock),
        )
        return mock

    @pytest.fixture(autouse=True)
    async def configure_remote_storage(self, set_up_kv_storage):
        pass

    def test_runner_type(self):
        assert DockerFlowRunner().typename == "docker"

    async def test_creates_container_then_marks_as_started(
        self, flow_run, mock_docker_client, use_hosted_orion
    ):
        fake_status = MagicMock(spec=anyio.abc.TaskStatus)
        # By raising an exception when started is called we can assert the process
        # is opened before this time
        fake_status.started.side_effect = RuntimeError("Started called!")

        with pytest.raises(RuntimeError, match="Started called!"):

            await DockerFlowRunner().submit_flow_run(flow_run, fake_status)

        fake_status.started.assert_called_once()
        mock_docker_client.containers.create.assert_called_once()
        # The returned container is started
        mock_docker_client.containers.create().start.assert_called_once()

    async def test_container_name_matches_flow_run_name(
        self, mock_docker_client, flow_run, use_hosted_orion
    ):
        flow_run.name = "hello-flow-run"

        await DockerFlowRunner().submit_flow_run(flow_run, MagicMock())
        mock_docker_client.containers.create.assert_called_once()
        call_name = mock_docker_client.containers.create.call_args[1].get("name")
        assert call_name == "hello-flow-run"

    @pytest.mark.parametrize(
        "run_name,container_name",
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
    async def test_container_name_creates_valid_name(
        self, mock_docker_client, flow_run, use_hosted_orion, run_name, container_name
    ):
        flow_run.name = run_name

        await DockerFlowRunner().submit_flow_run(flow_run, MagicMock())
        mock_docker_client.containers.create.assert_called_once()
        call_name = mock_docker_client.containers.create.call_args[1].get("name")
        assert call_name == container_name

    async def test_container_name_falls_back_to_id(
        self, mock_docker_client, flow_run, use_hosted_orion
    ):
        flow_run.name = "--__...."  # All invalid characters

        await DockerFlowRunner().submit_flow_run(flow_run, MagicMock())
        mock_docker_client.containers.create.assert_called_once()
        call_name = mock_docker_client.containers.create.call_args[1].get("name")
        assert call_name == flow_run.id

    @pytest.mark.parametrize("collision_count", (0, 1, 5))
    async def test_container_name_includes_index_on_conflict(
        self, mock_docker_client, flow_run, use_hosted_orion, collision_count
    ):
        import docker.errors

        flow_run.name = "flow-run-name"

        if collision_count:
            # Add the basic name first
            existing_names = [f"{flow_run.name}"]
            for i in range(1, collision_count):
                existing_names.append(f"{flow_run.name}-{i}")
        else:
            existing_names = []

        def fail_if_name_exists(*args, **kwargs):
            if kwargs.get("name") in existing_names:
                raise docker.errors.APIError(
                    "Conflict. The container name 'foobar' is already in use"
                )
            return MagicMock()  # A container

        mock_docker_client.containers.create.side_effect = fail_if_name_exists

        await DockerFlowRunner().submit_flow_run(flow_run, MagicMock())

        assert mock_docker_client.containers.create.call_count == collision_count + 1
        call_name = mock_docker_client.containers.create.call_args[1].get("name")
        expected_name = (
            f"{flow_run.name}"
            if not collision_count
            else f"{flow_run.name}-{collision_count}"
        )
        assert call_name == expected_name

    async def test_container_creation_failure_reraises_if_not_name_conflict(
        self, mock_docker_client, flow_run, use_hosted_orion
    ):
        import docker.errors

        mock_docker_client.containers.create.side_effect = docker.errors.APIError(
            "test error"
        )

        with pytest.raises(docker.errors.APIError, match="test error"):
            await DockerFlowRunner().submit_flow_run(flow_run, MagicMock())

    async def test_uses_image_setting(
        self, mock_docker_client, flow_run, use_hosted_orion
    ):

        await DockerFlowRunner(image="foo").submit_flow_run(flow_run, MagicMock())
        mock_docker_client.containers.create.assert_called_once()
        call_image = mock_docker_client.containers.create.call_args[1].get("image")
        assert call_image == "foo"

    async def test_uses_volumes_setting(
        self, mock_docker_client, flow_run, use_hosted_orion
    ):

        await DockerFlowRunner(volumes=["a:b", "c:d"]).submit_flow_run(
            flow_run, MagicMock()
        )
        mock_docker_client.containers.create.assert_called_once()
        call_volumes = mock_docker_client.containers.create.call_args[1].get("volumes")
        assert "a:b" in call_volumes
        assert "c:d" in call_volumes

    @pytest.mark.parametrize("networks", [[], ["a"], ["a", "b"]])
    async def test_uses_network_setting(
        self, mock_docker_client, flow_run, use_hosted_orion, networks
    ):

        await DockerFlowRunner(networks=networks).submit_flow_run(flow_run, MagicMock())
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

    async def test_includes_prefect_labels(
        self, mock_docker_client, flow_run, use_hosted_orion
    ):

        await DockerFlowRunner().submit_flow_run(flow_run, MagicMock())

        mock_docker_client.containers.create.assert_called_once()
        call_labels = mock_docker_client.containers.create.call_args[1].get("labels")
        assert call_labels == {
            "io.prefect.flow-run-id": str(flow_run.id),
        }

    async def test_uses_label_setting(
        self, mock_docker_client, flow_run, use_hosted_orion
    ):

        await DockerFlowRunner(labels={"foo": "FOO", "bar": "BAR"}).submit_flow_run(
            flow_run, MagicMock()
        )
        mock_docker_client.containers.create.assert_called_once()
        call_labels = mock_docker_client.containers.create.call_args[1].get("labels")
        assert "foo" in call_labels and "bar" in call_labels
        assert call_labels["foo"] == "FOO"
        assert call_labels["bar"] == "BAR"
        assert "io.prefect.flow-run-id" in call_labels, "prefect labels still included"

    async def test_uses_network_mode_setting(
        self, mock_docker_client, flow_run, use_hosted_orion
    ):

        await DockerFlowRunner(network_mode="bridge").submit_flow_run(
            flow_run, MagicMock()
        )
        mock_docker_client.containers.create.assert_called_once()
        network_mode = mock_docker_client.containers.create.call_args[1].get(
            "network_mode"
        )
        assert network_mode == "bridge"

    async def test_uses_env_setting(
        self, mock_docker_client, flow_run, use_hosted_orion
    ):

        await DockerFlowRunner(env={"foo": "FOO", "bar": "BAR"}).submit_flow_run(
            flow_run, MagicMock()
        )
        mock_docker_client.containers.create.assert_called_once()
        call_env = mock_docker_client.containers.create.call_args[1].get("environment")
        assert "foo" in call_env and "bar" in call_env
        assert call_env["foo"] == "FOO"
        assert call_env["bar"] == "BAR"

    @pytest.mark.parametrize("localhost", ["localhost", "127.0.0.1"])
    async def test_network_mode_defaults_to_host_if_using_localhost_api_on_linux(
        self, mock_docker_client, flow_run, localhost, monkeypatch
    ):
        monkeypatch.setattr("sys.platform", "linux")

        await DockerFlowRunner(
            env=dict(PREFECT_API_URL=f"http://{localhost}/test")
        ).submit_flow_run(flow_run, MagicMock())
        mock_docker_client.containers.create.assert_called_once()
        network_mode = mock_docker_client.containers.create.call_args[1].get(
            "network_mode"
        )
        assert network_mode == "host"

    async def test_network_mode_defaults_to_none_if_using_networks(
        self, mock_docker_client, flow_run
    ):
        # Despite using localhost for the API, we will set the network mode to `None`
        # because `networks` and `network_mode` cannot both be set.
        await DockerFlowRunner(
            env=dict(PREFECT_API_URL="http://localhost/test"),
            networks=["test"],
        ).submit_flow_run(flow_run, MagicMock())
        mock_docker_client.containers.create.assert_called_once()
        network_mode = mock_docker_client.containers.create.call_args[1].get(
            "network_mode"
        )
        assert network_mode is None

    async def test_network_mode_defaults_to_none_if_using_nonlocal_api(
        self, mock_docker_client, flow_run
    ):

        await DockerFlowRunner(
            env=dict(PREFECT_API_URL="http://foo/test")
        ).submit_flow_run(flow_run, MagicMock())
        mock_docker_client.containers.create.assert_called_once()
        network_mode = mock_docker_client.containers.create.call_args[1].get(
            "network_mode"
        )
        assert network_mode is None

    async def test_network_mode_defaults_to_none_if_not_on_linux(
        self, mock_docker_client, flow_run, monkeypatch
    ):
        monkeypatch.setattr("sys.platform", "darwin")

        await DockerFlowRunner(
            env=dict(PREFECT_API_URL="http://localhost/test")
        ).submit_flow_run(flow_run, MagicMock())

        mock_docker_client.containers.create.assert_called_once()
        network_mode = mock_docker_client.containers.create.call_args[1].get(
            "network_mode"
        )
        assert network_mode is None

    async def test_network_mode_defaults_to_none_if_api_url_cannot_be_parsed(
        self, mock_docker_client, flow_run, monkeypatch
    ):
        monkeypatch.setattr("sys.platform", "darwin")

        # It is hard to actually get urlparse to fail, so we'll just raise an error
        # manually
        monkeypatch.setattr(
            "urllib.parse.urlparse", MagicMock(side_effect=ValueError("test"))
        )

        with pytest.warns(UserWarning, match="Failed to parse host"):
            await DockerFlowRunner(env=dict(PREFECT_API_URL="foo")).submit_flow_run(
                flow_run, MagicMock()
            )

        mock_docker_client.containers.create.assert_called_once()
        network_mode = mock_docker_client.containers.create.call_args[1].get(
            "network_mode"
        )
        assert network_mode is None

    async def test_replaces_localhost_api_with_dockerhost_when_not_using_host_network(
        self, mock_docker_client, flow_run, use_hosted_orion, hosted_orion_api
    ):

        await DockerFlowRunner(network_mode="bridge").submit_flow_run(
            flow_run, MagicMock()
        )
        mock_docker_client.containers.create.assert_called_once()
        call_env = mock_docker_client.containers.create.call_args[1].get("environment")
        assert "PREFECT_API_URL" in call_env
        assert call_env["PREFECT_API_URL"] == hosted_orion_api.replace(
            "localhost", "host.docker.internal"
        )

    async def test_does_not_replace_localhost_api_when_using_host_network(
        self,
        mock_docker_client,
        flow_run,
        use_hosted_orion,
        hosted_orion_api,
        monkeypatch,
    ):
        # We will warn if setting 'host' network mode on non-linux platforms
        monkeypatch.setattr("sys.platform", "linux")

        await DockerFlowRunner(network_mode="host").submit_flow_run(
            flow_run, MagicMock()
        )
        mock_docker_client.containers.create.assert_called_once()
        call_env = mock_docker_client.containers.create.call_args[1].get("environment")
        assert "PREFECT_API_URL" in call_env
        assert call_env["PREFECT_API_URL"] == hosted_orion_api

    async def test_warns_at_runtime_when_using_host_network_mode_on_non_linux_platform(
        self,
        mock_docker_client,
        flow_run,
        use_hosted_orion,
        hosted_orion_api,
        monkeypatch,
    ):
        monkeypatch.setattr("sys.platform", "darwin")

        with assert_does_not_warn():
            runner = DockerFlowRunner(network_mode="host")

        with pytest.warns(
            UserWarning,
            match="'host' network mode is not supported on platform 'darwin'",
        ):
            await runner.submit_flow_run(flow_run, MagicMock())

        mock_docker_client.containers.create.assert_called_once()
        network_mode = mock_docker_client.containers.create.call_args[1].get(
            "network_mode"
        )
        assert network_mode == "host", "The setting is passed to dockerpy still"

    async def test_does_not_override_user_provided_api_host(
        self, mock_docker_client, flow_run, use_hosted_orion
    ):

        await DockerFlowRunner(
            env={"PREFECT_API_URL": "http://localhost/api"}
        ).submit_flow_run(flow_run, MagicMock())
        mock_docker_client.containers.create.assert_called_once()
        call_env = mock_docker_client.containers.create.call_args[1].get("environment")
        assert call_env.get("PREFECT_API_URL") == "http://localhost/api"

    async def test_adds_docker_host_gateway_on_linux(
        self, mock_docker_client, flow_run, use_hosted_orion, monkeypatch
    ):
        monkeypatch.setattr("sys.platform", "linux")

        await DockerFlowRunner().submit_flow_run(flow_run, MagicMock())

        mock_docker_client.containers.create.assert_called_once()
        call_extra_hosts = mock_docker_client.containers.create.call_args[1].get(
            "extra_hosts"
        )
        assert call_extra_hosts == {"host.docker.internal": "host-gateway"}

    async def test_default_image_pull_policy_pulls_image_with_latest_tag(
        self, mock_docker_client, flow_run, use_hosted_orion
    ):
        await DockerFlowRunner(image="prefect:latest").submit_flow_run(
            flow_run, MagicMock()
        )
        mock_docker_client.images.pull.assert_called_once()
        mock_docker_client.images.pull.assert_called_with("prefect", "latest")

    async def test_default_image_pull_policy_pulls_image_with_no_tag(
        self, mock_docker_client, flow_run, use_hosted_orion
    ):
        await DockerFlowRunner(image="prefect").submit_flow_run(flow_run, MagicMock())
        mock_docker_client.images.pull.assert_called_once()
        mock_docker_client.images.pull.assert_called_with("prefect", None)

    async def test_default_image_pull_policy_pulls_image_with_tag_other_than_latest_if_not_present(
        self, mock_docker_client, flow_run, use_hosted_orion
    ):
        mock_docker_client.images.get.side_effect = ImageNotFound("No way, bub")

        await DockerFlowRunner(image="prefect:omega").submit_flow_run(
            flow_run, MagicMock()
        )
        mock_docker_client.images.pull.assert_called_once()
        mock_docker_client.images.pull.assert_called_with("prefect", "omega")

    async def test_default_image_pull_policy_does_not_pull_image_with_tag_other_than_latest_if_present(
        self, mock_docker_client, flow_run, use_hosted_orion
    ):
        mock_docker_client.images.get.return_value = Image()

        await DockerFlowRunner(image="prefect:omega").submit_flow_run(
            flow_run, MagicMock()
        )
        mock_docker_client.images.pull.assert_not_called()

    async def test_image_pull_policy_always_pulls(
        self, mock_docker_client, flow_run, use_hosted_orion
    ):
        await DockerFlowRunner(
            image="prefect", image_pull_policy=ImagePullPolicy.ALWAYS
        ).submit_flow_run(flow_run, MagicMock())
        mock_docker_client.images.get.assert_not_called()
        mock_docker_client.images.pull.assert_called_once()
        mock_docker_client.images.pull.assert_called_with("prefect", None)

    async def test_image_pull_policy_never_does_not_pull(
        self, mock_docker_client, flow_run, use_hosted_orion
    ):
        await DockerFlowRunner(
            image="prefect", image_pull_policy=ImagePullPolicy.NEVER
        ).submit_flow_run(flow_run, MagicMock())
        mock_docker_client.images.pull.assert_not_called()

    async def test_image_pull_policy_if_not_present_pulls_image_if_not_present(
        self, mock_docker_client, flow_run, use_hosted_orion
    ):
        mock_docker_client.images.get.side_effect = ImageNotFound("No way, bub")

        await DockerFlowRunner(
            image="prefect", image_pull_policy=ImagePullPolicy.IF_NOT_PRESENT
        ).submit_flow_run(flow_run, MagicMock())
        mock_docker_client.images.pull.assert_called_once()
        mock_docker_client.images.pull.assert_called_with("prefect", None)

    async def test_image_pull_policy_if_not_present_does_not_pull_image_if_present(
        self, mock_docker_client, flow_run, use_hosted_orion
    ):
        mock_docker_client.images.get.return_value = Image()

        await DockerFlowRunner(
            image="prefect", image_pull_policy=ImagePullPolicy.IF_NOT_PRESENT
        ).submit_flow_run(flow_run, MagicMock())
        mock_docker_client.images.pull.assert_not_called()

    @pytest.mark.parametrize("platform", ["win32", "darwin"])
    async def test_does_not_add_docker_host_gateway_on_other_platforms(
        self, mock_docker_client, flow_run, use_hosted_orion, monkeypatch, platform
    ):
        monkeypatch.setattr("sys.platform", platform)

        await DockerFlowRunner().submit_flow_run(flow_run, MagicMock())

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
    async def test_warns_if_docker_version_does_not_support_host_gateway_on_linux(
        self,
        mock_docker_client,
        flow_run,
        use_hosted_orion,
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
            await DockerFlowRunner(
                env={"PREFECT_API_URL": explicit_api_url} if explicit_api_url else {}
            ).submit_flow_run(flow_run, MagicMock())

        mock_docker_client.containers.create.assert_called_once()
        call_extra_hosts = mock_docker_client.containers.create.call_args[1].get(
            "extra_hosts"
        )
        assert not call_extra_hosts

    async def test_does_not_warn_about_gateway_if_user_has_provided_nonlocal_api_url(
        self,
        mock_docker_client,
        flow_run,
        monkeypatch,
    ):
        monkeypatch.setattr("sys.platform", "linux")
        mock_docker_client.version.return_value = {"Version": "19.1.1"}

        with assert_does_not_warn():
            await DockerFlowRunner(
                env={"PREFECT_API_URL": "http://my-domain.test/api"}
            ).submit_flow_run(flow_run, MagicMock())

        mock_docker_client.containers.create.assert_called_once()
        call_extra_hosts = mock_docker_client.containers.create.call_args[1].get(
            "extra_hosts"
        )
        assert not call_extra_hosts

    @pytest.mark.parametrize("platform", ["win32", "darwin"])
    async def test_does_not_warn_about_gateway_if_not_using_linux(
        self,
        mock_docker_client,
        flow_run,
        platform,
        monkeypatch,
        use_hosted_orion,
    ):
        monkeypatch.setattr("sys.platform", platform)
        mock_docker_client.version.return_value = {"Version": "19.1.1"}

        with assert_does_not_warn():
            await DockerFlowRunner().submit_flow_run(flow_run, MagicMock())

        mock_docker_client.containers.create.assert_called_once()
        call_extra_hosts = mock_docker_client.containers.create.call_args[1].get(
            "extra_hosts"
        )
        assert not call_extra_hosts

    async def test_raises_on_submission_with_ephemeral_api(
        self, mock_docker_client, flow_run
    ):
        with pytest.raises(
            RuntimeError,
            match="cannot be used with an ephemeral server",
        ):
            await DockerFlowRunner().submit_flow_run(flow_run, MagicMock())

    async def test_no_raise_on_submission_with_hosted_api(
        self, mock_docker_client, flow_run, use_hosted_orion
    ):
        await DockerFlowRunner().submit_flow_run(flow_run, MagicMock())

    @pytest.mark.service("docker")
    async def test_executes_flow_run_with_hosted_api(
        self,
        flow_run,
        orion_client,
        use_hosted_orion,
        hosted_orion_api,
        prefect_settings_test_deployment,
    ):
        fake_status = MagicMock(spec=anyio.abc.TaskStatus)

        flow_run = await orion_client.create_flow_run_from_deployment(
            prefect_settings_test_deployment
        )

        assert await DockerFlowRunner().submit_flow_run(flow_run, fake_status)

        fake_status.started.assert_called_once()
        flow_run = await orion_client.read_flow_run(flow_run.id)
        runtime_settings = await orion_client.resolve_datadoc(flow_run.state.result())

        runtime_api_url = PREFECT_API_URL.value_from(runtime_settings)
        assert runtime_api_url == (
            hosted_orion_api
            if sys.platform == "linux"
            else hosted_orion_api.replace("localhost", "host.docker.internal")
        )

    @pytest.mark.service("docker")
    @pytest.mark.skipif(
        MIN_COMPAT_PREFECT_VERSION > prefect.__version__.split("+")[0],
        reason=f"Expected breaking change in next version: {MIN_COMPAT_PREFECT_VERSION}",
    )
    @pytest.mark.skipif(
        sys.version_info >= (3, 10) and MIN_COMPAT_PREFECT_VERSION == "2.0a13",
        reason="We did not publish a 3.10 image for 2.0a13",
    )
    async def test_execution_is_compatible_with_old_prefect_container_version(
        self,
        flow_run,
        orion_client,
        use_hosted_orion,
        python_executable_test_deployment,
    ):
        """
        This test confirms that the flow runner can properly start a flow run in a
        container running an old version of Prefect. This tests for regression in the
        path of "starting a flow run" as well as basic API communication.

        When making a breaking change to the API, it's likely that no compatible image
        will exist. If so, bump MIN_COMPAT_PREFECT_VERSION past the current prefect
        version and this test will be skipped until a compatible image can be found.
        """
        fake_status = MagicMock(spec=anyio.abc.TaskStatus)

        flow_run = await orion_client.create_flow_run_from_deployment(
            python_executable_test_deployment
        )

        assert await DockerFlowRunner(
            image=get_prefect_image_name(MIN_COMPAT_PREFECT_VERSION)
        ).submit_flow_run(flow_run, fake_status)

        fake_status.started.assert_called_once()
        flow_run = await orion_client.read_flow_run(flow_run.id)
        assert flow_run.state.is_completed()

    @pytest.mark.service("docker")
    async def test_executing_flow_run_has_rw_access_to_volumes(
        self,
        flow_run,
        orion_client,
        use_hosted_orion,
        tmp_path,
    ):
        @prefect.flow
        def my_flow():
            Path("/root/mount/writefile").resolve().write_text("bar")
            return Path("/root/mount/readfile").resolve().read_text()

        flow_id = await orion_client.create_flow(my_flow)

        flow_data = DataDocument.encode("cloudpickle", my_flow)

        deployment_id = await orion_client.create_deployment(
            flow_id=flow_id,
            name="prefect_file_test_deployment",
            flow_data=flow_data,
        )

        fake_status = MagicMock(spec=anyio.abc.TaskStatus)

        flow_run = await orion_client.create_flow_run_from_deployment(deployment_id)

        # Write to a file that the flow will read from
        (tmp_path / "readfile").write_text("foo")

        assert await DockerFlowRunner(
            volumes=[f"{tmp_path}:/root/mount"]
        ).submit_flow_run(flow_run, fake_status)

        fake_status.started.assert_called_once()
        flow_run = await orion_client.read_flow_run(flow_run.id)
        file_contents = await orion_client.resolve_datadoc(flow_run.state.result())
        assert file_contents == "foo"

        assert (tmp_path / "writefile").read_text() == "bar"

    @pytest.mark.service("docker")
    @pytest.mark.parametrize("stream_output", [True, False])
    async def test_stream_output_controls_local_printing(
        self, deployment, capsys, orion_client, stream_output, use_hosted_orion
    ):
        flow_run = await orion_client.create_flow_run_from_deployment(deployment.id)

        assert await DockerFlowRunner(stream_output=stream_output).submit_flow_run(
            flow_run, MagicMock(spec=anyio.abc.TaskStatus)
        )

        output = capsys.readouterr()
        assert output.err == "", "stderr is never populated"

        if not stream_output:
            assert output.out == ""
        else:
            assert "Finished in state" in output.out, "Log from the engine is present"
            assert "\n\n" not in output.out, "Line endings are not double terminated"

    @pytest.mark.service("docker")
    async def test_executing_flow_run_has_environment_variables(
        self,
        flow_run,
        orion_client,
        use_hosted_orion,
        os_environ_test_deployment,
    ):
        fake_status = MagicMock(spec=anyio.abc.TaskStatus)

        flow_run = await orion_client.create_flow_run_from_deployment(
            os_environ_test_deployment
        )

        assert await DockerFlowRunner(
            env={"TEST_FOO": "foo", "TEST_BAR": "bar"}
        ).submit_flow_run(flow_run, fake_status)

        fake_status.started.assert_called_once()
        flow_run = await orion_client.read_flow_run(flow_run.id)
        flow_run_environ = await orion_client.resolve_datadoc(flow_run.state.result())
        assert "TEST_FOO" in flow_run_environ and "TEST_BAR" in flow_run_environ
        assert flow_run_environ["TEST_FOO"] == "foo"
        assert flow_run_environ["TEST_BAR"] == "bar"

    @pytest.mark.service("docker")
    async def test_failure_to_connect_returns_bad_exit_code(
        self,
        flow_run,
        orion_client,
        prefect_settings_test_deployment,
    ):
        fake_status = MagicMock(spec=anyio.abc.TaskStatus)

        flow_run = await orion_client.create_flow_run_from_deployment(
            prefect_settings_test_deployment
        )

        with temporary_settings(updates={PREFECT_API_URL: "http://fail.test"}):
            assert not await DockerFlowRunner().submit_flow_run(flow_run, fake_status)

        fake_status.started.assert_called_once()

        flow_run = await orion_client.read_flow_run(flow_run.id)
        # The flow _cannot_ be failed by the flow run engine because it cannot talk to
        # the API. Something else will need to be responsible for failing the run.
        assert not flow_run.state.is_final()

    @pytest.mark.service("docker")
    def test_check_for_required_development_image(self):
        with docker_client() as client:
            tag = get_prefect_image_name()
            build_cmd = f"`docker build {prefect.__root_path__} -t {tag!r}`"

            try:
                client.images.get(tag)
            except NotFound:
                raise RuntimeError(
                    "Docker service tests require the development image tag to be "
                    "available. Build the image with " + build_cmd
                )

            output = client.containers.run(tag, "prefect --version")
            container_version = output.decode().strip()
            test_run_version = prefect.__version__

            if container_version != test_run_version:
                # We are in a local run, just warn if the versions do not match
                warnings.warn(
                    f"The development Docker image with tag {tag!r} has version "
                    f"{container_version!r} but tests were run with version "
                    f"{test_run_version!r}. You may safely ignore this warning if you "
                    "have intentionally not built a new test image. Rebuild the image "
                    "with " + build_cmd
                )

            client.close()
