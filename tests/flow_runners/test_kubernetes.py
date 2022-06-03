import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Dict
from unittest.mock import MagicMock

import anyio.abc
import httpx
import kubernetes
import kubernetes as k8s
import pendulum
import pytest
import yaml
from jsonpatch import JsonPatch
from kubernetes.config import ConfigException
from pydantic import ValidationError
from urllib3.exceptions import MaxRetryError

import prefect
from prefect.client import get_client
from prefect.flow_runners import (
    KubernetesFlowRunner,
    KubernetesImagePullPolicy,
    KubernetesRestartPolicy,
    base_flow_run_environment,
)
from prefect.flow_runners.kubernetes import KubernetesManifest
from prefect.orion.schemas.core import FlowRun
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
        pytest.importorskip("kubernetes")

        mock = MagicMock()

        monkeypatch.setattr("kubernetes.watch.Watch", MagicMock(return_value=mock))
        return mock

    @pytest.fixture
    def mock_cluster_config(self, monkeypatch):
        pytest.importorskip("kubernetes")

        mock = MagicMock()

        monkeypatch.setattr("kubernetes.config", mock)
        return mock

    @pytest.fixture
    def mock_k8s_client(self, monkeypatch, mock_cluster_config):
        pytest.importorskip("kubernetes")

        mock = MagicMock(spec=k8s.client.CoreV1Api)

        @contextmanager
        def get_client(_):
            yield mock

        monkeypatch.setattr(
            "prefect.flow_runners.KubernetesFlowRunner.get_client",
            get_client,
        )
        return mock

    @pytest.fixture
    def mock_k8s_batch_client(self, monkeypatch, mock_cluster_config):
        pytest.importorskip("kubernetes")

        mock = MagicMock(spec=k8s.client.BatchV1Api)

        @contextmanager
        def get_batch_client(_):
            yield mock

        monkeypatch.setattr(
            "prefect.flow_runners.KubernetesFlowRunner.get_batch_client",
            get_batch_client,
        )
        return mock

    @staticmethod
    def _mock_pods_stream_that_returns_running_pod(*args, **kwargs):
        job_pod = MagicMock(spec=kubernetes.client.V1Pod)
        job_pod.status.phase = "Running"

        job = MagicMock(spec=kubernetes.client.V1Job)
        job.status.completion_time = pendulum.now("utc").timestamp()

        return [{"object": job_pod}, {"object": job}]

    def test_runner_type(restart_policy):
        assert KubernetesFlowRunner().typename == "kubernetes"

    def test_building_a_job_is_idempotent(self, flow_run: FlowRun):
        """Building a Job twice from the same FlowRun should return different copies
        of the Job manifest with identical values"""
        flow_runner = KubernetesFlowRunner()
        first_time = flow_runner.build_job(flow_run)
        second_time = flow_runner.build_job(flow_run)
        assert first_time is not second_time
        assert first_time == second_time

    async def test_creates_job_by_building_a_manifest(
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
        flow_runner = KubernetesFlowRunner()
        expected_manifest = flow_runner.build_job(flow_run)
        await flow_runner.submit_flow_run(flow_run, fake_status)
        mock_k8s_client.read_namespaced_pod_status.assert_called_once()

        mock_k8s_batch_client.create_namespaced_job.assert_called_with(
            "default",
            expected_manifest,
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

    async def test_warns_and_replaces_user_supplied_restart_policy(
        self,
        mock_k8s_client,
        mock_watch,
        mock_k8s_batch_client,
        flow_run,
        use_hosted_orion,
        hosted_orion_api,
    ):
        mock_watch.stream = self._mock_pods_stream_that_returns_running_pod

        with pytest.warns(DeprecationWarning, match="restart_policy is deprecated"):
            flow_runner = KubernetesFlowRunner(
                restart_policy=KubernetesRestartPolicy.ON_FAILURE
            )

        await flow_runner.submit_flow_run(flow_run, MagicMock())
        mock_k8s_batch_client.create_namespaced_job.assert_called_once()
        call_restart_policy = mock_k8s_batch_client.create_namespaced_job.call_args[0][
            1
        ]["spec"]["template"]["spec"].get("restartPolicy")
        assert call_restart_policy == "Never"

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


class TestIntegrationWithRealKubernetesCluster:
    @pytest.fixture
    async def k8s_orion_client(self, k8s_hosted_orion):
        pytest.importorskip("kubernetes")

        async with get_client() as orion_client:
            yield orion_client

    @pytest.fixture
    def k8s_hosted_orion(self, tmp_path):
        """
        Sets `PREFECT_API_URL` and to the k8s-hosted API endpoint.
        """
        pytest.importorskip("kubernetes")

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
            with k8s.client.ApiClient() as client:
                k8s.client.VersionApi(api_client=client).get_code()
                client.rest_client.pool_manager.clear()
        except MaxRetryError:
            pytest.skip(skip_message)

        # TODO: Check API server health
        health_check = f"{k8s_hosted_orion}/health"
        try:
            async with httpx.AsyncClient() as http_client:
                await http_client.get(health_check)
        except httpx.ConnectError:
            pytest.skip("Kubernetes-hosted Orion is unavailable.")

    @pytest.fixture(scope="module")
    async def results_directory(self) -> Path:
        """In order to share results reliably with the Kubernetes cluster, we need to be
        somehwere in the user's directory tree for the most cross-platform
        compatibilty. It's challenging to coordinate /tmp/ directories across systems"""
        directory = Path(os.getcwd()) / ".prefect-results"
        os.makedirs(directory, exist_ok=True)
        for filename in os.listdir(directory):
            os.unlink(directory / filename)
        return directory

    @pytest.mark.service("kubernetes")
    async def test_executing_flow_run_has_environment_variables(
        self,
        k8s_orion_client,
        results_directory: Path,
        require_k8s_cluster,
    ):
        """
        Test KubernetesFlowRunner against an API server running in a live
        k8s cluster.

        NOTE: Before running this, you will need to do the following:
            - Create an orion deployment: `prefect orion kubernetes-manifest | kubectl apply -f -`
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
        #
        # In order to receive results back from the flow, we need to share a filesystem
        # between the job and our host, which we'll do by mounting the /tmp/ directory
        # from the test host using a hostPath volumeMount to the directory that matches
        # tempfile.gettempdir(), which is what prefect.blocks.storage.TempStorageBlock
        # uses
        assert await KubernetesFlowRunner(
            env={
                "TEST_FOO": "foo",
                "PREFECT_API_URL": in_cluster_k8s_api_url,
            },
            customizations=[
                {
                    "op": "add",
                    "path": "/spec/template/spec/volumes",
                    "value": [
                        {
                            "name": "results-volume",
                            "hostPath": {"path": str(results_directory)},
                        }
                    ],
                },
                {
                    "op": "add",
                    "path": "/spec/template/spec/containers/0/volumeMounts",
                    "value": [{"name": "results-volume", "mountPath": "/tmp/prefect/"}],
                },
            ],
        ).submit_flow_run(flow_run, fake_status)

        fake_status.started.assert_called_once()
        flow_run = await k8s_orion_client.read_flow_run(flow_run.id)
        result = flow_run.state.result()

        # replace the container's /tmp/ with gettempdir() so we can get at the results
        result.blob = result.blob.replace(
            b"/tmp/prefect/", str(results_directory).encode() + b"/"
        )

        flow_run_environ = await k8s_orion_client.resolve_datadoc(result)
        assert "TEST_FOO" in flow_run_environ
        assert flow_run_environ["TEST_FOO"] == "foo"


class TestCustomizingBaseJob:
    """Tests scenarios where a user is providing a customized base Job template"""

    def test_validates_against_an_empty_job(self, flow_run: FlowRun):
        """We should give a human-friendly error when the user provides an empty custom
        Job manifest"""
        with pytest.raises(ValidationError) as excinfo:
            KubernetesFlowRunner(job={})

        assert excinfo.value.errors() == [
            {
                "loc": ("job",),
                "msg": (
                    "Job is missing required attributes at the following paths: "
                    "/apiVersion, /kind, /metadata, /spec"
                ),
                "type": "value_error",
            }
        ]

    def test_validates_for_a_job_missing_deeper_attributes(self, flow_run: FlowRun):
        """We should give a human-friendly error when the user provides an incomplete
        custom Job manifest"""
        with pytest.raises(ValidationError) as excinfo:
            KubernetesFlowRunner(
                job={
                    "apiVersion": "batch/v1",
                    "kind": "Job",
                    "metadata": {},
                    "spec": {"template": {"spec": {}}},
                }
            )

        assert excinfo.value.errors() == [
            {
                "loc": ("job",),
                "msg": (
                    "Job is missing required attributes at the following paths: "
                    "/metadata/labels, /spec/template/spec/containers"
                ),
                "type": "value_error",
            }
        ]

    def test_validates_for_a_job_with_incompatible_values(self, flow_run: FlowRun):
        """We should give a human-friendly error when the user provides a custom Job
        manifest that is attempting to change required values."""
        with pytest.raises(ValidationError) as excinfo:
            KubernetesFlowRunner(
                job={
                    "apiVersion": "v1",
                    "kind": "JobbledyJunk",
                    "metadata": {"labels": {}},
                    "spec": {
                        "template": {
                            "spec": {
                                "containers": [
                                    {
                                        "name": "prefect-job",
                                        "env": [],
                                    }
                                ]
                            }
                        }
                    },
                }
            )

        assert excinfo.value.errors() == [
            {
                "loc": ("job",),
                "msg": (
                    "Job has incompatble values for the following attributes: "
                    "/apiVersion must have value 'batch/v1', "
                    "/kind must have value 'Job'"
                ),
                "type": "value_error",
            }
        ]

    def test_user_can_supply_the_minimum_viable_value(self, flow_run: FlowRun):
        """Documenting the minimum viable Job that can be provided"""
        manifest = KubernetesFlowRunner(
            job=KubernetesFlowRunner.base_job_manifest()
        ).build_job(flow_run)

        # probe a few attributes to check for sanity
        assert manifest["metadata"]["labels"] == {
            "app": "orion",
            "io.prefect.flow-run-id": str(flow_run.id),
            "io.prefect.flow-run-name": flow_run.name,
        }
        assert manifest["spec"]["template"]["spec"]["containers"][0]["command"] == [
            "python",
            "-m",
            "prefect.engine",
            str(flow_run.id),
        ]

    def test_user_supplied_base_job_with_labels(self, flow_run: FlowRun):
        """The user can supply a custom base job with labels and they will be
        included in the final manifest"""
        manifest = KubernetesFlowRunner(
            job={
                "apiVersion": "batch/v1",
                "kind": "Job",
                "metadata": {"labels": {"my-custom-label": "sweet"}},
                "spec": {
                    "template": {
                        "spec": {
                            "containers": [
                                {
                                    "name": "prefect-job",
                                    "env": [],
                                }
                            ]
                        }
                    }
                },
            }
        ).build_job(flow_run)

        assert manifest["metadata"]["labels"] == {
            # the labels provided in the user's job base
            "my-custom-label": "sweet",
            # prefect's labels
            "app": "orion",
            "io.prefect.flow-run-id": str(flow_run.id),
            "io.prefect.flow-run-name": flow_run.name,
        }

    def test_user_can_supply_a_sidecar_container_and_volume(self, flow_run: FlowRun):
        """The user can supply a custom base job that includes more complex
        modifications, like a sidecar container and volumes"""
        manifest = KubernetesFlowRunner(
            job={
                "apiVersion": "batch/v1",
                "kind": "Job",
                "metadata": {"labels": {}},
                "spec": {
                    "template": {
                        "spec": {
                            "containers": [
                                {
                                    "name": "prefect-job",
                                    "env": [],
                                },
                                {
                                    "name": "my-sidecar",
                                    "image": "cool-peeps/cool-code:latest",
                                    "volumeMounts": [
                                        {"name": "data-volume", "mountPath": "/data/"}
                                    ],
                                },
                            ],
                            "volumes": [
                                {"name": "data-volume", "hostPath": "/all/the/data/"}
                            ],
                        }
                    }
                },
            }
        ).build_job(flow_run)

        pod = manifest["spec"]["template"]["spec"]

        assert pod["volumes"] == [{"name": "data-volume", "hostPath": "/all/the/data/"}]

        # the prefect-job container is still populated
        assert pod["containers"][0]["name"] == "prefect-job"
        assert pod["containers"][0]["command"] == [
            "python",
            "-m",
            "prefect.engine",
            str(flow_run.id),
        ]

        assert pod["containers"][1] == {
            "name": "my-sidecar",
            "image": "cool-peeps/cool-code:latest",
            "volumeMounts": [{"name": "data-volume", "mountPath": "/data/"}],
        }


class TestCustomizingJob:
    """Tests scenarios where the user is providing targeted RFC 6902 JSON patches to
    customize their Job"""

    @staticmethod
    def find_environment_variable(manifest: KubernetesManifest, name: str) -> Dict:
        pod = manifest["spec"]["template"]["spec"]
        env = pod["containers"][0]["env"]
        for variable in env:
            if variable["name"] == name:
                return variable
        assert False, f"{name} not found in pod environment variables: {env!r}"

    def test_providing_a_secret_key_as_an_environment_variable(self, flow_run):
        manifest = KubernetesFlowRunner(
            customizations=[
                {
                    "op": "add",
                    "path": "/spec/template/spec/containers/0/env/-",
                    "value": {
                        "name": "MY_API_TOKEN",
                        "valueFrom": {
                            "secretKeyRef": {
                                "name": "the-secret-name",
                                "key": "api-token",
                            }
                        },
                    },
                }
            ],
        ).build_job(flow_run)

        variable = self.find_environment_variable(manifest, "MY_API_TOKEN")
        assert variable == {
            "name": "MY_API_TOKEN",
            "valueFrom": {
                "secretKeyRef": {
                    "name": "the-secret-name",
                    "key": "api-token",
                }
            },
        }

        # prefect variables are still present
        self.find_environment_variable(manifest, "PREFECT_TEST_MODE")

    def test_setting_pod_resource_requests(self, flow_run):
        manifest = KubernetesFlowRunner(
            customizations=[
                {
                    "op": "add",
                    "path": "/spec/template/spec/resources",
                    "value": {"limits": {"memory": "8Gi", "cpu": "4000m"}},
                }
            ],
        ).build_job(flow_run)

        pod = manifest["spec"]["template"]["spec"]
        assert pod["resources"]["limits"] == {
            "memory": "8Gi",
            "cpu": "4000m",
        }

        # prefect's orchestration values are still there
        assert pod["completions"] == 1

    def test_requesting_a_fancy_gpu(self, flow_run):
        manifest = KubernetesFlowRunner(
            customizations=[
                {
                    "op": "add",
                    "path": "/spec/template/spec/resources",
                    "value": {"limits": {}},
                },
                {
                    "op": "add",
                    "path": "/spec/template/spec/resources/limits",
                    "value": {"nvidia.com/gpu": 2},
                },
                {
                    "op": "add",
                    "path": "/spec/template/spec/nodeSelector",
                    "value": {"cloud.google.com/gke-accelerator": "nvidia-tesla-k80"},
                },
            ],
        ).build_job(flow_run)

        pod = manifest["spec"]["template"]["spec"]
        assert pod["resources"]["limits"] == {
            "nvidia.com/gpu": 2,
        }
        assert pod["nodeSelector"] == {
            "cloud.google.com/gke-accelerator": "nvidia-tesla-k80",
        }

        # prefect's orchestration values are still there
        assert pod["completions"] == 1

    def test_label_with_slash_in_it(self, flow_run):
        """Documenting the use of ~1 to stand in for a /, according to RFC 6902"""
        manifest = KubernetesFlowRunner(
            customizations=[
                {
                    "op": "add",
                    "path": "/metadata/labels/example.com~1a-cool-key",
                    "value": "hi!",
                }
            ],
        ).build_job(flow_run)

        labels = manifest["metadata"]["labels"]
        assert labels["example.com/a-cool-key"] == "hi!"

        # prefect's identification labels are still there
        assert labels["io.prefect.flow-run-id"] == str(flow_run.id)
        assert labels["io.prefect.flow-run-name"] == flow_run.name


class TestLoadingManifestsFromFiles:
    @pytest.fixture
    def example(self) -> KubernetesManifest:
        return {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {"labels": {"my-custom-label": "sweet"}},
            "spec": {
                "template": {
                    "spec": {
                        "containers": [
                            {
                                "name": "prefect-job",
                                "env": [],
                            }
                        ]
                    }
                }
            },
        }

    @pytest.fixture
    def example_yaml(self, tmp_path: Path, example: KubernetesManifest) -> Path:
        filename = tmp_path / "example.yaml"
        with open(filename, "w") as f:
            yaml.dump(example, f)
        yield filename

    def test_job_from_yaml(self, example: KubernetesManifest, example_yaml: Path):
        assert KubernetesFlowRunner.job_from_file(example_yaml) == example

    @pytest.fixture
    def example_json(self, tmp_path: Path, example: KubernetesManifest) -> Path:
        filename = tmp_path / "example.json"
        with open(filename, "w") as f:
            json.dump(example, f)
        yield filename

    def test_job_from_json(self, example: KubernetesManifest, example_json: Path):
        assert KubernetesFlowRunner.job_from_file(example_json) == example


class TestLoadingPatchesFromFiles:
    def test_assumptions_about_jsonpatch(self):
        """Assert our assumptions about the behavior of the jsonpatch library, so we
        can be alert to any upstream changes"""
        patch_1 = JsonPatch([{"op": "add", "path": "/hi", "value": "there"}])
        patch_2 = JsonPatch([{"op": "add", "path": "/hi", "value": "there"}])
        patch_3 = JsonPatch([{"op": "add", "path": "/different", "value": "there"}])
        assert patch_1 is not patch_2
        assert patch_1 == patch_2
        assert patch_1 != patch_3

        assert list(patch_1) == list(patch_2)
        assert list(patch_1) != list(patch_3)

        assert patch_1.apply({}) == patch_2.apply({})
        assert patch_1.apply({}) != patch_3.apply({})

    @pytest.fixture
    def example(self) -> JsonPatch:
        return JsonPatch(
            [
                {
                    "op": "add",
                    "path": "/spec/template/spec/containers/0/env/-",
                    "value": {
                        "name": "MY_API_TOKEN",
                        "valueFrom": {
                            "secretKeyRef": {
                                "name": "the-secret-name",
                                "key": "api-token",
                            }
                        },
                    },
                },
                {
                    "op": "add",
                    "path": "/spec/template/spec/resources",
                    "value": {"limits": {"memory": "8Gi", "cpu": "4000m"}},
                },
            ]
        )

    @pytest.fixture
    def example_yaml(self, tmp_path: Path, example: JsonPatch) -> Path:
        filename = tmp_path / "example.yaml"
        with open(filename, "w") as f:
            yaml.dump(list(example), f)
        yield filename

    def test_patch_from_yaml(self, example: KubernetesManifest, example_yaml: Path):
        assert KubernetesFlowRunner.customize_from_file(example_yaml) == example

    @pytest.fixture
    def example_json(self, tmp_path: Path, example: JsonPatch) -> Path:
        filename = tmp_path / "example.json"
        with open(filename, "w") as f:
            json.dump(list(example), f)
        yield filename

    def test_patch_from_json(self, example: KubernetesManifest, example_json: Path):
        assert KubernetesFlowRunner.customize_from_file(example_json) == example
