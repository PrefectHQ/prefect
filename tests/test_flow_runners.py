import os
import shutil
import subprocess
import sys
import warnings
from pathlib import Path
from typing import NamedTuple
from unittest.mock import MagicMock

import anyio
import anyio.abc
import coolname
import httpx
import kubernetes
import kubernetes as k8s
import pendulum
import pydantic
import pytest
from docker.errors import ImageNotFound
from docker.models.images import Image
from kubernetes.config import ConfigException
from typing_extensions import Literal
from urllib3.exceptions import MaxRetryError

import prefect
from prefect.client import get_client
from prefect.flow_runners import (
    MIN_COMPAT_PREFECT_VERSION,
    DockerFlowRunner,
    FlowRunner,
    ImagePullPolicy,
    KubernetesFlowRunner,
    KubernetesImagePullPolicy,
    KubernetesRestartPolicy,
    SubprocessFlowRunner,
    UniversalFlowRunner,
    base_flow_run_environment,
    get_prefect_image_name,
    lookup_flow_runner,
    python_version_minor,
    register_flow_runner,
)
from prefect.orion.schemas.core import FlowRunnerSettings
from prefect.orion.schemas.data import DataDocument
from prefect.settings import PREFECT_API_KEY, PREFECT_API_URL
from prefect.utilities.testing import (
    AsyncMock,
    assert_does_not_warn,
    kubernetes_environments_equal,
    temporary_settings,
)


class VersionInfo(NamedTuple):
    major: int
    minor: int
    micro: int
    releaselevel: str
    serial: int


def fake_python_version(
    major=sys.version_info.major,
    minor=sys.version_info.minor,
    micro=sys.version_info.micro,
    releaselevel=sys.version_info.releaselevel,
    serial=sys.version_info.serial,
):
    return VersionInfo(major, minor, micro, releaselevel, serial)


@pytest.fixture
def venv_environment_path(tmp_path):
    """
    Generates a temporary venv environment with development dependencies installed
    """

    environment_path = tmp_path / "test"

    # Create the virtual environment, include system site packages to avoid reinstalling
    # prefect which takes ~40 seconds instead of ~4 seconds.
    subprocess.check_output(
        [sys.executable, "-m", "venv", str(environment_path), "--system-site-packages"]
    )

    # Install prefect within the virtual environment
    # --system-site-packages makes this irreleveant, but we retain this in case we want
    # to have a slower test in the future that uses a clean environment.
    # subprocess.check_output(
    #     [
    #         str(environment_path / "bin" / "python"),
    #         "-m",
    #         "pip",
    #         "install",
    #         "-e",
    #         f"{prefect.__root_path__}[dev]",
    #     ]
    # )

    return environment_path


@pytest.fixture
def virtualenv_environment_path(tmp_path):
    """
    Generates a temporary virtualenv environment with development dependencies installed
    """
    pytest.importorskip("virtualenv")

    environment_path = tmp_path / "test"

    # Create the virtual environment, include system site packages to avoid reinstalling
    # prefect which takes ~40 seconds instead of ~4 seconds.
    subprocess.check_output(
        ["virtualenv", str(environment_path), "--system-site-packages"]
    )

    # Install prefect within the virtual environment
    # --system-site-packages makes this irreleveant, but we retain this in case we want
    # to have a slower test in the future that uses a clean environment.
    # subprocess.check_output(
    #     [
    #         str(environment_path / "bin" / "python"),
    #         "-m",
    #         "pip",
    #         "install",
    #         "-e",
    #         f"{prefect.__root_path__}[dev]",
    #     ]
    # )

    return environment_path


@pytest.fixture
def conda_environment_path(tmp_path):
    """
    Generates a temporary anaconda environment with development dependencies installed

    Will not be usable by `--name`, only `--prefix`.
    """
    if not shutil.which("conda"):
        pytest.skip("`conda` is not installed.")

    # Generate base creation command with the temporary path as the prefix for
    # automatic cleanup
    environment_path: Path = tmp_path / f"test-{coolname.generate_slug(2)}"
    create_env_command = [
        "conda",
        "create",
        "-y",
        "--prefix",
        str(environment_path),
    ]

    # Get the current conda environment so we can clone it for speedup
    current_conda_env = os.environ.get("CONDA_PREFIX")
    if current_conda_env:
        create_env_command.extend(["--clone", current_conda_env])

    else:
        # Otherwise, specify a matching python version up to `minor`
        # We cannot match up to `micro` because it is not always available in conda
        v = sys.version_info
        python_version = f"{v.major}.{v.minor}"
        create_env_command.append(f"python={python_version}")

    print(f"Creating conda environment at {environment_path}")
    subprocess.check_output(create_env_command)

    # Install prefect within the virtual environment
    # Developers using conda should have a matching environment from `--clone`.
    if not current_conda_env:

        # Link packages from the current installation instead of reinstalling
        conda_site_packages = (
            environment_path / "lib" / f"python{python_version}" / "site-packages"
        )
        local_site_packages = (
            Path(sys.prefix) / "lib" / f"python{python_version}" / "site-packages"
        )
        print(f"Linking packages from {local_site_packages} -> {conda_site_packages}")
        for local_pkg in local_site_packages.iterdir():
            conda_pkg = conda_site_packages / local_pkg.name
            if not conda_pkg.exists():
                conda_pkg.symlink_to(local_pkg, target_is_directory=local_pkg.is_dir())

        # Linking is takes ~10s while faster than reinstalling in the environment takes
        # ~60s. This blurb is retained for the future as we may encounter issues with
        # linking and prefer to do the slow but correct installation.
        # subprocess.check_output(
        #     [
        #         "conda",
        #         "run",
        #         "--prefix",
        #         str(environment_path),
        #         "pip",
        #         "install",
        #         "-e",
        #         f"{prefect.__root_path__}[dev]",
        #     ]
        # )

    return environment_path


@pytest.fixture
async def python_executable_test_deployment(orion_client):
    """
    A deployment for a flow that returns the current python executable path for
    testing that flows are run with the correct python version
    """

    @prefect.flow
    def my_flow():
        import sys

        return sys.executable

    flow_id = await orion_client.create_flow(my_flow)

    flow_data = DataDocument.encode("cloudpickle", my_flow)

    deployment_id = await orion_client.create_deployment(
        flow_id=flow_id,
        name="python_executable_test_deployment",
        flow_data=flow_data,
    )

    return deployment_id


@pytest.fixture
async def os_environ_test_deployment(orion_client):
    """
    A deployment for a flow that returns the current environment variables for testing
    that flows are run with environment variables populated.
    """

    @prefect.flow
    def my_flow():
        import os

        return os.environ

    flow_id = await orion_client.create_flow(my_flow)

    flow_data = DataDocument.encode("cloudpickle", my_flow)

    deployment_id = await orion_client.create_deployment(
        flow_id=flow_id,
        name="os_environ_test_deployment",
        flow_data=flow_data,
    )

    return deployment_id


@pytest.fixture
async def prefect_settings_test_deployment(orion_client):
    """
    A deployment for a flow that returns the current Prefect settings object.
    """

    @prefect.flow
    def my_flow():
        import prefect.settings

        return prefect.settings.get_current_settings()

    flow_id = await orion_client.create_flow(my_flow)

    flow_data = DataDocument.encode("cloudpickle", my_flow)

    deployment_id = await orion_client.create_deployment(
        flow_id=flow_id,
        name="prefect_settings_test_deployment",
        flow_data=flow_data,
    )

    return deployment_id


class TestFlowRunner:
    def test_has_no_type(self):
        with pytest.raises(pydantic.ValidationError):
            FlowRunner()

    async def test_does_not_implement_submission(self):
        with pytest.raises(NotImplementedError):
            await FlowRunner(typename="test").submit_flow_run(None, None)

    def test_logger_based_on_name(self):
        assert FlowRunner(typename="foobar").logger.name == "prefect.flow_runner.foobar"


class TestFlowRunnerRegistration:
    def test_register_and_lookup(self):
        @register_flow_runner
        class TestFlowRunnerConfig(FlowRunner):
            typename: Literal["test"] = "test"

        assert lookup_flow_runner("test") == TestFlowRunnerConfig

    def test_to_settings(self):
        flow_runner = UniversalFlowRunner(env={"foo": "bar"})
        assert flow_runner.to_settings() == FlowRunnerSettings(
            type="universal", config={"env": {"foo": "bar"}}
        )

    def test_from_settings(self):
        settings = FlowRunnerSettings(type="universal", config={"env": {"foo": "bar"}})
        assert FlowRunner.from_settings(settings) == UniversalFlowRunner(
            env={"foo": "bar"}
        )


class TestBaseFlowRunEnvironment:
    def test_empty_by_default(self):
        assert base_flow_run_environment() == {}

    def test_includes_api_url_and_key_when_set(self):
        with temporary_settings(PREFECT_API_KEY="foo", PREFECT_API_URL="bar"):
            assert base_flow_run_environment() == {
                "PREFECT_API_KEY": "foo",
                "PREFECT_API_URL": "bar",
            }


class TestUniversalFlowRunner:
    def test_unner_type(self):
        assert UniversalFlowRunner().typename == "universal"

    async def test_raises_submission_error(self):
        with pytest.raises(
            RuntimeError,
            match="universal flow runner cannot be used to submit flow runs",
        ):
            await UniversalFlowRunner().submit_flow_run(None, None)


class TestSubprocessFlowRunner:
    def test_runner_type(self):
        assert SubprocessFlowRunner().typename == "subprocess"

    async def test_creates_subprocess_then_marks_as_started(
        self, monkeypatch, flow_run
    ):
        monkeypatch.setattr("anyio.open_process", AsyncMock())
        fake_status = MagicMock(spec=anyio.abc.TaskStatus)
        # By raising an exception when started is called we can assert the process
        # is opened before this time
        fake_status.started.side_effect = RuntimeError("Started called!")

        with pytest.raises(RuntimeError, match="Started called!"):
            await SubprocessFlowRunner().submit_flow_run(flow_run, fake_status)

        fake_status.started.assert_called_once()
        anyio.open_process.assert_awaited_once()

    async def test_creates_subprocess_with_current_python_executable(
        self, monkeypatch, flow_run
    ):
        monkeypatch.setattr(
            "anyio.open_process",
            # TODO: Consider more robust mocking for opened processes
            AsyncMock(side_effect=RuntimeError("Exit without streaming from process.")),
        )
        with pytest.raises(RuntimeError, match="Exit without streaming"):
            await SubprocessFlowRunner().submit_flow_run(flow_run, MagicMock())

        anyio.open_process.assert_awaited_once_with(
            [sys.executable, "-m", "prefect.engine", flow_run.id.hex],
            stderr=subprocess.STDOUT,
            env=os.environ,
        )

    @pytest.mark.parametrize(
        "condaenv",
        ["test", Path("/test"), Path("~/test")],
        ids=["by name", "by abs path", "by home path"],
    )
    async def test_creates_subprocess_with_conda_command(
        self, monkeypatch, flow_run, condaenv
    ):
        monkeypatch.setattr(
            "anyio.open_process",
            # TODO: Consider more robust mocking for opened processes
            AsyncMock(side_effect=RuntimeError("Exit without streaming from process.")),
        )

        with pytest.raises(RuntimeError, match="Exit without streaming"):
            await SubprocessFlowRunner(condaenv=condaenv).submit_flow_run(
                flow_run, MagicMock()
            )

        name_or_prefix = (
            ["--name", condaenv]
            if not isinstance(condaenv, Path)
            else ["--prefix", str(condaenv.expanduser().resolve())]
        )

        anyio.open_process.assert_awaited_once_with(
            [
                "conda",
                "run",
                *name_or_prefix,
                "python",
                "-m",
                "prefect.engine",
                flow_run.id.hex,
            ],
            stderr=subprocess.STDOUT,
            env=os.environ,
        )

    async def test_creates_subprocess_with_virtualenv_command_and_env(
        self, monkeypatch, flow_run
    ):
        # PYTHONHOME must be unset in the subprocess
        monkeypatch.setenv("PYTHONHOME", "FOO")

        monkeypatch.setattr(
            "anyio.open_process",
            # TODO: Consider more robust mocking for opened processes
            AsyncMock(side_effect=RuntimeError("Exit without streaming from process.")),
        )
        with pytest.raises(RuntimeError, match="Exit without streaming"):
            await SubprocessFlowRunner(virtualenv="~/fakevenv").submit_flow_run(
                flow_run, MagicMock()
            )

        # Replicate expected generation of virtual environment call
        virtualenv_path = Path("~/fakevenv").expanduser()
        python_executable = str(virtualenv_path / "bin" / "python")
        expected_env = os.environ.copy()
        expected_env["PATH"] = (
            str(virtualenv_path / "bin") + os.pathsep + expected_env["PATH"]
        )
        expected_env.pop("PYTHONHOME")
        expected_env["VIRTUAL_ENV"] = str(virtualenv_path)

        anyio.open_process.assert_awaited_once_with(
            [
                python_executable,
                "-m",
                "prefect.engine",
                flow_run.id.hex,
            ],
            stderr=subprocess.STDOUT,
            env=expected_env,
        )

    async def test_executes_flow_run_with_system_python(
        self, python_executable_test_deployment, orion_client
    ):
        fake_status = MagicMock(spec=anyio.abc.TaskStatus)

        flow_run = await orion_client.create_flow_run_from_deployment(
            python_executable_test_deployment
        )

        happy_exit = await SubprocessFlowRunner().submit_flow_run(flow_run, fake_status)

        assert happy_exit
        fake_status.started.assert_called_once()
        state = (await orion_client.read_flow_run(flow_run.id)).state
        runtime_python = await orion_client.resolve_datadoc(state.result())
        assert runtime_python == sys.executable

    @pytest.mark.service("environment")
    async def test_executes_flow_run_in_virtualenv(
        self,
        flow_run,
        orion_client,
        virtualenv_environment_path,
        python_executable_test_deployment,
    ):
        flow_run = await orion_client.create_flow_run_from_deployment(
            python_executable_test_deployment
        )

        happy_exit = await SubprocessFlowRunner(
            virtualenv=virtualenv_environment_path
        ).submit_flow_run(flow_run, MagicMock(spec=anyio.abc.TaskStatus))

        assert happy_exit
        state = (await orion_client.read_flow_run(flow_run.id)).state
        runtime_python = await orion_client.resolve_datadoc(state.result())
        assert runtime_python == str(virtualenv_environment_path / "bin" / "python")

    @pytest.mark.service("environment")
    async def test_executes_flow_run_in_venv(
        self,
        flow_run,
        orion_client,
        venv_environment_path,
        python_executable_test_deployment,
    ):
        flow_run = await orion_client.create_flow_run_from_deployment(
            python_executable_test_deployment
        )

        happy_exit = await SubprocessFlowRunner(
            virtualenv=venv_environment_path
        ).submit_flow_run(flow_run, MagicMock(spec=anyio.abc.TaskStatus))

        assert happy_exit
        state = (await orion_client.read_flow_run(flow_run.id)).state
        runtime_python = await orion_client.resolve_datadoc(state.result())
        assert runtime_python == str(venv_environment_path / "bin" / "python")

    @pytest.mark.service("environment")
    async def test_executes_flow_run_in_conda_environment(
        self,
        flow_run,
        orion_client,
        conda_environment_path,
        python_executable_test_deployment,
    ):
        flow_run = await orion_client.create_flow_run_from_deployment(
            python_executable_test_deployment
        )

        happy_exit = await SubprocessFlowRunner(
            condaenv=conda_environment_path,
            stream_output=True,
        ).submit_flow_run(flow_run, MagicMock(spec=anyio.abc.TaskStatus))

        assert happy_exit
        state = (await orion_client.read_flow_run(flow_run.id)).state
        runtime_python = await orion_client.resolve_datadoc(state.result())
        assert runtime_python == str(conda_environment_path / "bin" / "python")

    @pytest.mark.parametrize("stream_output", [True, False])
    async def test_stream_output_controls_local_printing(
        self, deployment, capsys, orion_client, stream_output
    ):
        flow_run = await orion_client.create_flow_run_from_deployment(deployment.id)

        assert await SubprocessFlowRunner(stream_output=stream_output).submit_flow_run(
            flow_run, MagicMock(spec=anyio.abc.TaskStatus)
        )

        output = capsys.readouterr()
        assert output.err == "", "stderr is never populated"

        if not stream_output:
            assert output.out == ""
        else:
            assert "Finished in state" in output.out, "Log from the engine is present"
            assert "\n\n" not in output.out, "Line endings are not double terminated"


class TestGetPrefectImageName:
    async def test_tag_includes_python_minor_version(self, monkeypatch):
        monkeypatch.setattr("prefect.__version__", "2.0.0")
        assert (
            get_prefect_image_name()
            == f"prefecthq/prefect:2.0.0-python{python_version_minor()}"
        )

    @pytest.mark.parametrize("prerelease", ["a", "a5", "b1", "rc2"])
    async def test_tag_includes_prereleases(self, monkeypatch, prerelease):
        monkeypatch.setattr("prefect.__version__", "2.0.0" + prerelease)
        assert (
            get_prefect_image_name()
            == f"prefecthq/prefect:2.0.0{prerelease}-python{python_version_minor()}"
        )

    async def test_tag_detects_development(self, monkeypatch):
        monkeypatch.setattr("prefect.__version__", "2.0.0+5.g6fcc2b9a")
        monkeypatch.setattr("sys.version_info", fake_python_version(major=3, minor=10))
        assert get_prefect_image_name() == "prefecthq/prefect:dev-python3.10"


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

        with temporary_settings(PREFECT_API_URL="http://fail.test"):
            assert not await DockerFlowRunner().submit_flow_run(flow_run, fake_status)

        fake_status.started.assert_called_once()

        flow_run = await orion_client.read_flow_run(flow_run.id)
        # The flow _cannot_ be failed by the flow run engine because it cannot talk to
        # the API. Something else will need to be responsible for failing the run.
        assert not flow_run.state.is_final()

    @pytest.mark.service("docker")
    def test_check_for_required_development_image(self):
        import docker.client
        import docker.errors

        client = docker.client.from_env()
        tag = get_prefect_image_name()
        build_cmd = f"`docker build {prefect.__root_path__} -t {tag!r}`"

        try:
            client.images.get(tag)
        except docker.errors.NotFound as exc:
            raise RuntimeError(
                "Docker service tests require the development image tag to be "
                "available. Build the image with " + build_cmd
            )

        output = client.containers.run(tag, "prefect version")
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


class TestKubernetesFlowRunner:
    @pytest.fixture(autouse=True)
    def skip_if_kubernetes_is_not_installed(self):
        pytest.importorskip("kubernetes")

    @pytest.fixture(autouse=True)
    async def configure_remote_storage(self, set_up_kv_storage):
        pass

    @pytest.fixture
    def mock_watch(self, monkeypatch):
        kubernetes = pytest.importorskip("kubernetes")

        mock = MagicMock()

        monkeypatch.setattr("kubernetes.watch.Watch", MagicMock(return_value=mock))
        return mock

    @pytest.fixture
    def mock_cluster_config(self, monkeypatch):
        kubernetes = pytest.importorskip("kubernetes")
        mock = MagicMock()

        monkeypatch.setattr(
            "kubernetes.config",
            mock,
        )
        return mock

    @pytest.fixture
    def mock_k8s_client(self, monkeypatch, mock_cluster_config):
        kubernetes = pytest.importorskip("kubernetes")

        mock = MagicMock(spec=k8s.client.CoreV1Api)

        monkeypatch.setattr("prefect.flow_runners.KubernetesFlowRunner.client", mock)
        return mock

    @pytest.fixture
    def mock_k8s_batch_client(self, monkeypatch, mock_cluster_config):
        kubernetes = pytest.importorskip("kubernetes")

        mock = MagicMock(spec=k8s.client.BatchV1Api)

        monkeypatch.setattr(
            "prefect.flow_runners.KubernetesFlowRunner.batch_client", mock
        )
        return mock

    @pytest.fixture
    async def k8s_orion_client(self, k8s_hosted_orion):
        kubernetes = pytest.importorskip("kubernetes")

        async with get_client() as orion_client:
            yield orion_client

    @pytest.fixture
    def k8s_hosted_orion(self):
        """
        Sets `PREFECT_API_URL` and to the k8s-hosted API endpoint.
        """
        kubernetes = pytest.importorskip("kubernetes")

        # TODO: pytest flag to configure this URL
        k8s_api_url = "http://localhost:4205/api"
        with temporary_settings(PREFECT_API_URL=k8s_api_url):
            yield k8s_api_url

    @pytest.fixture
    async def require_k8s_cluster(self, k8s_hosted_orion):
        """
        Skip any test that uses this fixture if a connection to a live
        Kubernetes cluster is not available.
        """
        skip_message = "Could not reach live Kubernetes cluster."
        try:
            k8s.config.load_kube_config()
        except ConfigException:
            pytest.skip(skip_message)

        try:
            client = k8s.client.VersionApi(k8s.client.ApiClient())
            client.get_code()
        except MaxRetryError:
            pytest.skip(skip_message)

        # TODO: Check API server health
        health_check = f"{k8s_hosted_orion}/health"
        try:
            async with httpx.AsyncClient() as http_client:
                await http_client.get(health_check)
        except httpx.ConnectError:
            pytest.skip("Kubernetes-hosted Orion is unavailable.")

    @staticmethod
    def _mock_pods_stream_that_returns_running_pod(*args, **kwargs):
        job_pod = MagicMock(spec=kubernetes.client.V1Pod)
        job_pod.status.phase = "Running"

        job = MagicMock(spec=kubernetes.client.V1Job)
        job.status.completion_time = pendulum.now("utc").timestamp()

        return [{"object": job_pod}, {"object": job}]

    def test_runner_type(restart_policy):
        assert KubernetesFlowRunner().typename == "kubernetes"

    async def test_creates_job(
        self,
        flow_run,
        mock_k8s_batch_client,
        mock_k8s_client,
        mock_watch,
        use_hosted_orion,
    ):
        mock_watch.stream = self._mock_pods_stream_that_returns_running_pod

        flow_run.name = "My Flow"
        fake_status = MagicMock(spec=anyio.abc.TaskStatus)
        await KubernetesFlowRunner().submit_flow_run(flow_run, fake_status)
        mock_k8s_client.read_namespaced_pod_status.assert_called_once()
        flow_id = str(flow_run.id)

        expected_data = {
            "metadata": {
                f"generateName": "my-flow",
                "namespace": "default",
                "labels": {
                    "io.prefect.flow-run-id": flow_id,
                    "io.prefect.flow-run-name": "my-flow",
                    "app": "orion",
                },
            },
            "spec": {
                "template": {
                    "spec": {
                        "restartPolicy": "Never",
                        "containers": [
                            {
                                "name": "job",
                                "image": get_prefect_image_name(),
                                "command": [
                                    "python",
                                    "-m",
                                    "prefect.engine",
                                    flow_id,
                                ],
                                "env": [
                                    {
                                        "name": key,
                                        "value": value,
                                    }
                                    for key, value in base_flow_run_environment().items()
                                ],
                            }
                        ],
                        "serviceAccountName": "default"
                    }
                },
                "backoff_limit": 4,
            },
        }

        mock_k8s_batch_client.create_namespaced_job.assert_called_with(
            "default", expected_data
        )

        fake_status.started.assert_called_once()

    @pytest.mark.parametrize(
        "run_name,job_name",
        [
            ("_flow_run", "flow-run"),
            ("...flow_run", "flow-run"),
            ("._-flow_run", "flow-run"),
            ("9flow-run", "9flow-run"),
            ("-flow.run", "flow-run"),
            ("flow*run", "flow-run"),
            ("flow9.-foo_bar^x", "flow9-foo-bar-x"),
        ],
    )
    async def test_job_name_creates_valid_name(
        self,
        mock_k8s_client,
        mock_watch,
        mock_k8s_batch_client,
        flow_run,
        use_hosted_orion,
        run_name,
        job_name,
    ):
        mock_watch.stream = self._mock_pods_stream_that_returns_running_pod
        flow_run.name = run_name

        await KubernetesFlowRunner().submit_flow_run(flow_run, MagicMock())
        mock_k8s_batch_client.create_namespaced_job.assert_called_once()
        call_name = mock_k8s_batch_client.create_namespaced_job.call_args[0][1][
            "metadata"
        ]["generateName"]
        assert call_name == job_name

    async def test_job_name_falls_back_to_id(
        self,
        mock_k8s_client,
        mock_watch,
        mock_k8s_batch_client,
        flow_run,
        use_hosted_orion,
    ):
        flow_run.name = " !@#$%"  # All invalid characters
        mock_watch.stream = self._mock_pods_stream_that_returns_running_pod

        await KubernetesFlowRunner().submit_flow_run(flow_run, MagicMock())
        mock_k8s_batch_client.create_namespaced_job.assert_called_once()
        call_name = mock_k8s_batch_client.create_namespaced_job.call_args[0][1][
            "metadata"
        ]["generateName"]
        assert call_name == str(flow_run.id)

    async def test_uses_image_setting(
        self,
        mock_k8s_client,
        mock_watch,
        mock_k8s_batch_client,
        flow_run,
        use_hosted_orion,
    ):
        mock_watch.stream = self._mock_pods_stream_that_returns_running_pod

        await KubernetesFlowRunner(image="foo").submit_flow_run(flow_run, MagicMock())
        mock_k8s_batch_client.create_namespaced_job.assert_called_once()
        image = mock_k8s_batch_client.create_namespaced_job.call_args[0][1]["spec"][
            "template"
        ]["spec"]["containers"][0]["image"]
        assert image == "foo"

    async def test_uses_labels_setting(
        self,
        mock_k8s_client,
        mock_watch,
        mock_k8s_batch_client,
        flow_run,
        use_hosted_orion,
    ):
        mock_watch.stream = self._mock_pods_stream_that_returns_running_pod

        await KubernetesFlowRunner(labels={"foo": "FOO", "bar": "BAR"}).submit_flow_run(
            flow_run, MagicMock()
        )
        mock_k8s_batch_client.create_namespaced_job.assert_called_once()
        labels = mock_k8s_batch_client.create_namespaced_job.call_args[0][1][
            "metadata"
        ]["labels"]
        assert labels["foo"] == "FOO"
        assert labels["bar"] == "BAR"
        assert (
            "io.prefect.flow-run-id" in labels and "io.prefect.flow-run-name" in labels
        ), "prefect labels still included"


    async def test_uses_namespace_setting(
        self,
        mock_k8s_client,
        mock_watch,
        mock_k8s_batch_client,
        flow_run,
        use_hosted_orion,
    ):
        mock_watch.stream = self._mock_pods_stream_that_returns_running_pod

        await KubernetesFlowRunner(namespace="foo").submit_flow_run(
            flow_run, MagicMock()
        )
        mock_k8s_batch_client.create_namespaced_job.assert_called_once()
        namespace = mock_k8s_batch_client.create_namespaced_job.call_args[0][1][
            "metadata"
        ]["namespace"]
        assert(namespace == "foo")

    async def test_uses_service_account_setting(
        self,
        mock_k8s_client,
        mock_watch,
        mock_k8s_batch_client,
        flow_run,
        use_hosted_orion,
    ):
        mock_watch.stream = self._mock_pods_stream_that_returns_running_pod

        await KubernetesFlowRunner(service_account="foo").submit_flow_run(flow_run, MagicMock())
        mock_k8s_batch_client.create_namespaced_job.assert_called_once()
        service_account = mock_k8s_batch_client.create_namespaced_job.call_args[0][1]["spec"][
            "template"
        ]["spec"]["serviceAccountName"]
        assert service_account == "foo"


    async def test_default_env_includes_api_url_and_key(
        self,
        mock_k8s_client,
        mock_watch,
        mock_k8s_batch_client,
        flow_run,
        use_hosted_orion,
        hosted_orion_api,
    ):
        mock_watch.stream = self._mock_pods_stream_that_returns_running_pod

        with temporary_settings(
            PREFECT_API_URL="http://orion:4200/api", PREFECT_API_KEY="my-api-key"
        ):
            await KubernetesFlowRunner().submit_flow_run(flow_run, MagicMock())
        mock_k8s_batch_client.create_namespaced_job.assert_called_once()
        call_env = mock_k8s_batch_client.create_namespaced_job.call_args[0][1]["spec"][
            "template"
        ]["spec"]["containers"][0]["env"]
        assert kubernetes_environments_equal(
            call_env,
            [
                {"name": "PREFECT_API_KEY", "value": "my-api-key"},
                {"name": "PREFECT_API_URL", "value": "http://orion:4200/api"},
            ],
        )

    async def test_does_not_override_user_provided_variables(
        self,
        mock_k8s_client,
        mock_watch,
        mock_k8s_batch_client,
        flow_run,
        use_hosted_orion,
        hosted_orion_api,
    ):
        mock_watch.stream = self._mock_pods_stream_that_returns_running_pod

        base_env = base_flow_run_environment()

        await KubernetesFlowRunner(
            env={key: "foo" for key in base_env}
        ).submit_flow_run(flow_run, MagicMock())
        mock_k8s_batch_client.create_namespaced_job.assert_called_once()
        call_env = mock_k8s_batch_client.create_namespaced_job.call_args[0][1]["spec"][
            "template"
        ]["spec"]["containers"][0]["env"]
        assert kubernetes_environments_equal(
            call_env, [{"name": key, "value": "foo"} for key in base_env]
        )

    async def test_includes_base_environment_if_user_set_other_env_vars(
        self,
        mock_k8s_client,
        mock_watch,
        mock_k8s_batch_client,
        flow_run,
        use_hosted_orion,
        hosted_orion_api,
    ):
        mock_watch.stream = self._mock_pods_stream_that_returns_running_pod

        await KubernetesFlowRunner(env={"WATCH": 1}).submit_flow_run(
            flow_run, MagicMock()
        )
        mock_k8s_batch_client.create_namespaced_job.assert_called_once()
        call_env = mock_k8s_batch_client.create_namespaced_job.call_args[0][1]["spec"][
            "template"
        ]["spec"]["containers"][0]["env"]
        assert kubernetes_environments_equal(
            call_env, {**base_flow_run_environment(), "WATCH": "1"}
        )

    async def test_defaults_to_unspecified_image_pull_policy(
        self,
        mock_k8s_client,
        mock_watch,
        mock_k8s_batch_client,
        flow_run,
        use_hosted_orion,
        hosted_orion_api,
    ):
        mock_watch.stream = self._mock_pods_stream_that_returns_running_pod

        await KubernetesFlowRunner().submit_flow_run(flow_run, MagicMock())
        mock_k8s_batch_client.create_namespaced_job.assert_called_once()
        call_image_pull_policy = mock_k8s_batch_client.create_namespaced_job.call_args[
            0
        ][1]["spec"]["template"]["spec"]["containers"][0].get("imagePullPolicy")
        assert call_image_pull_policy is None

    async def test_uses_specified_image_pull_policy(
        self,
        mock_k8s_client,
        mock_watch,
        mock_k8s_batch_client,
        flow_run,
        use_hosted_orion,
        hosted_orion_api,
    ):
        mock_watch.stream = self._mock_pods_stream_that_returns_running_pod

        await KubernetesFlowRunner(
            image_pull_policy=KubernetesImagePullPolicy.IF_NOT_PRESENT
        ).submit_flow_run(flow_run, MagicMock())
        mock_k8s_batch_client.create_namespaced_job.assert_called_once()
        call_image_pull_policy = mock_k8s_batch_client.create_namespaced_job.call_args[
            0
        ][1]["spec"]["template"]["spec"]["containers"][0].get("imagePullPolicy")
        assert call_image_pull_policy == "IfNotPresent"

    async def test_defaults_to_unspecified_restart_policy(
        self,
        mock_k8s_client,
        mock_watch,
        mock_k8s_batch_client,
        flow_run,
        use_hosted_orion,
        hosted_orion_api,
    ):
        mock_watch.stream = self._mock_pods_stream_that_returns_running_pod

        await KubernetesFlowRunner().submit_flow_run(flow_run, MagicMock())
        mock_k8s_batch_client.create_namespaced_job.assert_called_once()
        call_restart_policy = mock_k8s_batch_client.create_namespaced_job.call_args[0][
            1
        ]["spec"]["template"]["spec"].get("imagePullPolicy")
        assert call_restart_policy is None

    async def test_uses_specified_restart_policy(
        self,
        mock_k8s_client,
        mock_watch,
        mock_k8s_batch_client,
        flow_run,
        use_hosted_orion,
        hosted_orion_api,
    ):
        mock_watch.stream = self._mock_pods_stream_that_returns_running_pod

        await KubernetesFlowRunner(
            restart_policy=KubernetesRestartPolicy.ON_FAILURE
        ).submit_flow_run(flow_run, MagicMock())
        mock_k8s_batch_client.create_namespaced_job.assert_called_once()
        call_restart_policy = mock_k8s_batch_client.create_namespaced_job.call_args[0][
            1
        ]["spec"]["template"]["spec"].get("restartPolicy")
        assert call_restart_policy == "OnFailure"

    async def test_raises_on_submission_with_ephemeral_api(self, flow_run):
        with pytest.raises(
            RuntimeError,
            match="cannot be used with an ephemeral server",
        ):
            await KubernetesFlowRunner().submit_flow_run(flow_run, MagicMock())

    async def test_no_raise_on_submission_with_hosted_api(
        self,
        mock_cluster_config,
        mock_k8s_batch_client,
        mock_k8s_client,
        flow_run,
        use_hosted_orion,
    ):
        await KubernetesFlowRunner().submit_flow_run(flow_run, MagicMock())

    async def test_defaults_to_incluster_config(
        self,
        mock_k8s_client,
        mock_watch,
        mock_cluster_config,
        mock_k8s_batch_client,
        flow_run,
        use_hosted_orion,
    ):
        mock_watch.stream = self._mock_pods_stream_that_returns_running_pod
        fake_status = MagicMock(spec=anyio.abc.TaskStatus)

        await KubernetesFlowRunner().submit_flow_run(flow_run, fake_status)

        mock_cluster_config.incluster_config.load_incluster_config.assert_called_once()
        assert not mock_cluster_config.load_kube_config.called

    async def test_uses_cluster_config_if_not_in_cluster(
        self,
        mock_k8s_client,
        mock_watch,
        mock_cluster_config,
        mock_k8s_batch_client,
        flow_run,
        use_hosted_orion,
    ):
        mock_watch.stream = self._mock_pods_stream_that_returns_running_pod
        fake_status = MagicMock(spec=anyio.abc.TaskStatus)

        mock_cluster_config.incluster_config.load_incluster_config.side_effect = (
            ConfigException()
        )

        await KubernetesFlowRunner().submit_flow_run(flow_run, fake_status)

        mock_cluster_config.load_kube_config.assert_called_once()

    @pytest.mark.service("kubernetes")
    async def test_executing_flow_run_has_environment_variables(
        self, k8s_orion_client, require_k8s_cluster
    ):
        """
        Test KubernetesFlowRunner against an API server running in a live
        k8s cluster.

        NOTE: Before running this, you will need to do the following:
            - Create an orion deployment: `prefect dev kubernetes-manifest | kubectl apply -f -`
            - Forward port 4200 in the cluster to port 4205 locally: `kubectl port-forward deployment/orion 4205:4200`
        """
        fake_status = MagicMock(spec=anyio.abc.TaskStatus)

        # TODO: pytest flags to configure this URL
        in_cluster_k8s_api_url = "http://orion:4200/api"

        @prefect.flow
        def my_flow():
            import os

            return os.environ

        flow_id = await k8s_orion_client.create_flow(my_flow)

        flow_data = DataDocument.encode("cloudpickle", my_flow)

        deployment_id = await k8s_orion_client.create_deployment(
            flow_id=flow_id,
            name="k8s_test_deployment",
            flow_data=flow_data,
        )

        flow_run = await k8s_orion_client.create_flow_run_from_deployment(deployment_id)

        # When we submit the flow run, we need to use the Prefect URL that
        # the job needs to reach the k8s-hosted API inside the cluster, not
        # the URL that the tests used, which use a port forwarded to
        # localhost.
        assert await KubernetesFlowRunner(
            env={
                "TEST_FOO": "foo",
                "PREFECT_API_URL": in_cluster_k8s_api_url,
            }
        ).submit_flow_run(flow_run, fake_status)

        fake_status.started.assert_called_once()
        flow_run = await k8s_orion_client.read_flow_run(flow_run.id)
        flow_run_environ = await k8s_orion_client.resolve_datadoc(
            flow_run.state.result()
        )
        assert "TEST_FOO" in flow_run_environ
        assert flow_run_environ["TEST_FOO"] == "foo"


# The following tests are for configuration options and can test all relevant types


@pytest.mark.parametrize(
    "runner_type", [UniversalFlowRunner, SubprocessFlowRunner, DockerFlowRunner]
)
class TestFlowRunnerConfigEnv:
    def test_flow_runner_env_config(self, runner_type):
        assert runner_type(env={"foo": "bar"}).env == {"foo": "bar"}

    def test_flow_runner_env_config_casts_to_strings(self, runner_type):
        assert runner_type(env={"foo": 1}).env == {"foo": "1"}

    def test_flow_runner_env_config_errors_if_not_castable(self, runner_type):
        with pytest.raises(pydantic.ValidationError):
            runner_type(env={"foo": object()})

    def test_flow_runner_env_to_settings(self, runner_type):
        runner = runner_type(env={"foo": "bar"})
        settings = runner.to_settings()
        assert settings.config["env"] == runner.env


@pytest.mark.parametrize("runner_type", [SubprocessFlowRunner, DockerFlowRunner])
class TestFlowRunnerConfigStreamOutput:
    def test_flow_runner_stream_output_config(self, runner_type):
        assert runner_type(stream_output=True).stream_output == True

    def test_flow_runner_stream_output_config_casts_to_bool(self, runner_type):
        assert runner_type(stream_output=1).stream_output == True

    def test_flow_runner_stream_output_config_errors_if_not_castable(self, runner_type):
        with pytest.raises(pydantic.ValidationError):
            runner_type(stream_output=object())

    @pytest.mark.parametrize("value", [True, False])
    def test_flow_runner_stream_output_to_settings(self, runner_type, value):
        runner = runner_type(stream_output=value)
        settings = runner.to_settings()
        assert settings.config["stream_output"] == value


@pytest.mark.parametrize("runner_type", [SubprocessFlowRunner])
class TestFlowRunnerConfigCondaEnv:
    @pytest.mark.parametrize("value", ["test", Path("test")])
    def test_flow_runner_condaenv_config(self, runner_type, value):
        assert runner_type(condaenv=value).condaenv == value

    def test_flow_runner_condaenv_config_casts_to_string(self, runner_type):
        assert runner_type(condaenv=1).condaenv == "1"

    @pytest.mark.parametrize("value", [f"~{os.sep}test", f"{os.sep}test"])
    def test_flow_runner_condaenv_config_casts_to_path(self, runner_type, value):
        assert runner_type(condaenv=value).condaenv == Path(value)

    def test_flow_runner_condaenv_config_errors_if_not_castable(self, runner_type):
        with pytest.raises(pydantic.ValidationError):
            runner_type(condaenv=object())

    @pytest.mark.parametrize("value", ["test", Path("test")])
    def test_flow_runner_condaenv_to_settings(self, runner_type, value):
        runner = runner_type(condaenv=value)
        settings = runner.to_settings()
        assert settings.config["condaenv"] == value

    def test_flow_runner_condaenv_cannot_be_provided_with_virtualenv(self, runner_type):
        with pytest.raises(
            pydantic.ValidationError, match="cannot provide both a conda and virtualenv"
        ):
            runner_type(condaenv="foo", virtualenv="bar")


@pytest.mark.parametrize("runner_type", [SubprocessFlowRunner])
class TestFlowRunnerConfigVirtualEnv:
    def test_flow_runner_virtualenv_config(self, runner_type):
        path = Path("~").expanduser()
        assert runner_type(virtualenv=path).virtualenv == path

    def test_flow_runner_virtualenv_config_casts_to_path(self, runner_type):
        assert runner_type(virtualenv="~/test").virtualenv == Path("~/test")
        assert (
            Path("~/test") != Path("~/test").expanduser()
        ), "We do not want to expand user at configuration time"

    def test_flow_runner_virtualenv_config_errors_if_not_castable(self, runner_type):
        with pytest.raises(pydantic.ValidationError):
            runner_type(virtualenv=object())

    def test_flow_runner_virtualenv_to_settings(self, runner_type):
        runner = runner_type(virtualenv=Path("~/test"))
        settings = runner.to_settings()
        assert settings.config["virtualenv"] == Path("~/test")


@pytest.mark.parametrize("runner_type", [DockerFlowRunner])
class TestFlowRunnerConfigVolumes:
    def test_flow_runner_volumes_config(self, runner_type):
        volumes = ["a:b", "c:d"]
        assert runner_type(volumes=volumes).volumes == volumes

    def test_flow_runner_volumes_config_does_not_expand_paths(self, runner_type):
        assert runner_type(volumes=["~/a:b"]).volumes == ["~/a:b"]

    def test_flow_runner_volumes_config_casts_to_list(self, runner_type):
        assert type(runner_type(volumes={"a:b", "c:d"}).volumes) == list

    def test_flow_runner_volumes_config_errors_if_invalid_format(self, runner_type):
        with pytest.raises(
            pydantic.ValidationError, match="Invalid volume specification"
        ):
            runner_type(volumes=["a"])

    def test_flow_runner_volumes_config_errors_if_invalid_type(self, runner_type):
        with pytest.raises(pydantic.ValidationError):
            runner_type(volumes={"a": "b"})

    def test_flow_runner_volumes_to_settings(self, runner_type):
        runner = runner_type(volumes=["a:b", "c:d"])
        settings = runner.to_settings()
        assert settings.config["volumes"] == ["a:b", "c:d"]


@pytest.mark.parametrize("runner_type", [DockerFlowRunner])
class TestFlowRunnerConfigNetworks:
    def test_flow_runner_networks_config(self, runner_type):
        networks = ["a", "b"]
        assert runner_type(networks=networks).networks == networks

    def test_flow_runner_networks_config_casts_to_list(self, runner_type):
        assert type(runner_type(networks={"a", "b"}).networks) == list

    def test_flow_runner_networks_config_errors_if_invalid_type(self, runner_type):
        with pytest.raises(pydantic.ValidationError):
            runner_type(volumes={"foo": "bar"})

    def test_flow_runner_networks_to_settings(self, runner_type):
        runner = runner_type(networks=["a", "b"])
        settings = runner.to_settings()
        assert settings.config["networks"] == ["a", "b"]


@pytest.mark.parametrize("runner_type", [DockerFlowRunner])
class TestFlowRunnerConfigAutoRemove:
    def test_flow_runner_auto_remove_config(self, runner_type):
        assert runner_type(auto_remove=True).auto_remove == True

    def test_flow_runner_auto_remove_config_casts_to_bool(self, runner_type):
        assert runner_type(auto_remove=1).auto_remove == True

    def test_flow_runner_auto_remove_config_errors_if_not_castable(self, runner_type):
        with pytest.raises(pydantic.ValidationError):
            runner_type(auto_remove=object())

    @pytest.mark.parametrize("value", [True, False])
    def test_flow_runner_auto_remove_to_settings(self, runner_type, value):
        runner = runner_type(auto_remove=value)
        settings = runner.to_settings()
        assert settings.config["auto_remove"] == value


@pytest.mark.parametrize("runner_type", [DockerFlowRunner])
class TestFlowRunnerConfigImage:
    def test_flow_runner_image_config_defaults_to_orion_image(self, runner_type):
        assert runner_type().image == get_prefect_image_name()

    def test_flow_runner_image_config(self, runner_type):
        value = "foo"
        assert runner_type(image=value).image == value

    def test_flow_runner_image_config_casts_to_string(self, runner_type):
        assert runner_type(image=1).image == "1"

    def test_flow_runner_image_config_errors_if_not_castable(self, runner_type):
        with pytest.raises(pydantic.ValidationError):
            runner_type(image=object())

    def test_flow_runner_image_to_settings(self, runner_type):
        runner = runner_type(image="test")
        settings = runner.to_settings()
        assert settings.config["image"] == "test"


@pytest.mark.parametrize("runner_type", [DockerFlowRunner])
class TestFlowRunnerConfigLabels:
    def test_flow_runner_labels_config(self, runner_type):
        assert runner_type(labels={"foo": "bar"}).labels == {"foo": "bar"}

    def test_flow_runner_labels_config_casts_to_strings(self, runner_type):
        assert runner_type(labels={"foo": 1}).labels == {"foo": "1"}

    def test_flow_runner_labels_config_errors_if_not_castable(self, runner_type):
        with pytest.raises(pydantic.ValidationError):
            runner_type(labels={"foo": object()})

    def test_flow_runner_labels_to_settings(self, runner_type):
        runner = runner_type(labels={"foo": "bar"})
        settings = runner.to_settings()
        assert settings.config["labels"] == runner.labels
