import os
from pathlib import Path
from unittest.mock import MagicMock

import anyio.abc
import httpx
import kubernetes
import kubernetes as k8s
import pendulum
import pydantic
import pytest
from kubernetes.config import ConfigException
from urllib3.exceptions import MaxRetryError

import prefect
from prefect.client import get_client
from prefect.flow_runners import (
    DockerFlowRunner,
    KubernetesFlowRunner,
    KubernetesImagePullPolicy,
    KubernetesRestartPolicy,
    SubprocessFlowRunner,
    UniversalFlowRunner,
    base_flow_run_environment,
    get_prefect_image_name,
)
from prefect.orion.schemas.data import DataDocument
from prefect.settings import PREFECT_API_KEY, PREFECT_API_URL, temporary_settings
from prefect.testing.utilities import kubernetes_environments_equal


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
        with temporary_settings(updates={PREFECT_API_URL: k8s_api_url}):
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
        assert namespace == "foo"

    async def test_uses_service_account_name_setting(
        self,
        mock_k8s_client,
        mock_watch,
        mock_k8s_batch_client,
        flow_run,
        use_hosted_orion,
    ):
        mock_watch.stream = self._mock_pods_stream_that_returns_running_pod

        await KubernetesFlowRunner(service_account_name="foo").submit_flow_run(
            flow_run, MagicMock()
        )
        mock_k8s_batch_client.create_namespaced_job.assert_called_once()
        service_account_name = mock_k8s_batch_client.create_namespaced_job.call_args[0][
            1
        ]["spec"]["template"]["spec"]["serviceAccountName"]
        assert service_account_name == "foo"

    async def test_default_env_includes_base_flow_run_environment(
        self,
        mock_k8s_client,
        mock_watch,
        mock_k8s_batch_client,
        flow_run,
        use_hosted_orion,
    ):
        mock_watch.stream = self._mock_pods_stream_that_returns_running_pod

        with temporary_settings(
            updates={
                PREFECT_API_URL: "http://orion:4200/api",
                PREFECT_API_KEY: "my-api-key",
            }
        ):
            expected_environment = base_flow_run_environment()
            await KubernetesFlowRunner().submit_flow_run(flow_run, MagicMock())

        mock_k8s_batch_client.create_namespaced_job.assert_called_once()
        call_env = mock_k8s_batch_client.create_namespaced_job.call_args[0][1]["spec"][
            "template"
        ]["spec"]["containers"][0]["env"]
        assert kubernetes_environments_equal(call_env, expected_environment)

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
