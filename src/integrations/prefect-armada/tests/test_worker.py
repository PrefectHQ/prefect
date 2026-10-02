import uuid
from unittest.mock import MagicMock

import anyio.abc
import grpc
import pytest
from armada_client.armada import submit_pb2
from conftest import FakeRpcError, make_job_submit_response
from prefect_armada import ArmadaWorker
from prefect_armada.credentials import ArmadaClusterConfig, ArmadaCredentials
from prefect_armada.worker import ArmadaWorkerJobConfiguration
from pydantic import ValidationError

from prefect.client.schemas import FlowRun
from prefect.exceptions import InfrastructureError, InfrastructureNotFound
from prefect.utilities.dockerutils import get_prefect_image_name
from prefect.workers.base import BaseWorker
from prefect.workers.utilities import get_locally_installed_worker_metadata


@pytest.fixture(autouse=True)
def mock_observer(monkeypatch: pytest.MonkeyPatch):
    mocks = MagicMock()
    monkeypatch.setattr("prefect_armada.worker.start_observer", mocks.start)
    monkeypatch.setattr("prefect_armada.worker.stop_observer", mocks.stop)
    monkeypatch.setattr("prefect_armada.worker.observe_job_set", mocks.observe)
    return mocks


@pytest.fixture(autouse=True)
def armada_client(mock_armada_client):
    """Keeps the worker's startup queue check from dialing a real Armada server."""
    return mock_armada_client


@pytest.fixture
def flow_run():
    return FlowRun(flow_id=uuid.uuid4(), name="my-flow-run-name")


@pytest.fixture
async def default_configuration():
    return await ArmadaWorkerJobConfiguration.from_template_and_values(
        ArmadaWorker.get_default_base_job_template(), {}
    )


class TestArmadaWorkerJobConfiguration:
    def test_default_template_is_a_job_submit_request(self):
        template = ArmadaWorker.get_default_base_job_template()
        job_manifest = template["job_configuration"]["job_manifest"]

        assert job_manifest["podSpec"]["restartPolicy"] == "Never"
        assert job_manifest["podSpec"]["containers"][0]["name"] == "prefect-job"
        assert set(template["variables"]["properties"]) >= {
            "armada_host",
            "armada_port",
            "armada_disable_ssl",
            "armada_root_certificates_path",
            "api_dns_name",
            "queue",
            "job_set_id",
            "namespace",
            "priority",
            "image",
            "cpu_request",
            "memory_limit",
            "cluster_config",
            "credentials",
        }

    async def test_validates_missing_pod_spec(self):
        with pytest.raises(ValidationError, match="missing required attributes"):
            ArmadaWorkerJobConfiguration(job_manifest={"namespace": "default"})

    async def test_validates_incompatible_restart_policy(self):
        with pytest.raises(ValidationError, match="incompatible values"):
            ArmadaWorkerJobConfiguration(
                job_manifest={
                    "podSpec": {
                        "restartPolicy": "Always",
                        "containers": [{"name": "prefect-job"}],
                    }
                }
            )

    async def test_accepts_the_protobuf_pod_spec_field_name(self):
        configuration = ArmadaWorkerJobConfiguration(
            job_manifest={
                "pod_spec": {
                    "restartPolicy": "Never",
                    "containers": [{"name": "prefect-job"}],
                }
            }
        )

        assert "podSpec" in configuration.job_manifest
        assert "pod_spec" not in configuration.job_manifest

    async def test_namespace_is_added_to_the_manifest(self):
        configuration = ArmadaWorkerJobConfiguration(
            namespace="my-namespace",
            job_manifest={
                "podSpec": {
                    "restartPolicy": "Never",
                    "containers": [{"name": "prefect-job"}],
                }
            },
        )

        assert configuration.job_manifest["namespace"] == "my-namespace"

    async def test_prepare_for_flow_run_populates_the_manifest(
        self, default_configuration, flow_run
    ):
        default_configuration.prepare_for_flow_run(flow_run)
        manifest = default_configuration.job_manifest
        container = manifest["podSpec"]["containers"][0]

        assert container["image"] == get_prefect_image_name()
        assert container["args"] == ["prefect", "flow-run", "execute"]
        assert manifest["namespace"] == "default"
        assert manifest["labels"]["prefect.io/flow-run-id"] == str(flow_run.id)
        assert manifest["annotations"]["prefect.io/flow-run-id"] == str(flow_run.id)
        assert manifest["externalJobUri"] == f"prefect://flow-run/{flow_run.id}"
        assert default_configuration.job_set_id.endswith(str(flow_run.id))

    async def test_prepare_for_flow_run_converts_env_to_a_list(
        self, default_configuration, flow_run
    ):
        default_configuration.env = {"MY_VAR": "my-value"}
        default_configuration.prepare_for_flow_run(flow_run)

        env = default_configuration.job_manifest["podSpec"]["containers"][0]["env"]

        assert {"name": "MY_VAR", "value": "my-value"} in env
        assert all(isinstance(entry, dict) for entry in env)

    async def test_prepare_for_flow_run_preserves_hardcoded_env_entries(self, flow_run):
        template = ArmadaWorker.get_default_base_job_template()
        template["job_configuration"]["job_manifest"]["podSpec"]["containers"][0][
            "env"
        ] = [
            {
                "name": "MY_SECRET",
                "valueFrom": {"secretKeyRef": {"name": "secret", "key": "key"}},
            }
        ]
        configuration = await ArmadaWorkerJobConfiguration.from_template_and_values(
            template, {}
        )

        configuration.prepare_for_flow_run(flow_run)

        env = configuration.job_manifest["podSpec"]["containers"][0]["env"]
        assert {
            "name": "MY_SECRET",
            "valueFrom": {"secretKeyRef": {"name": "secret", "key": "key"}},
        } in env
        assert any(entry.get("name") == "PREFECT__FLOW_RUN_ID" for entry in env)

    async def test_prepare_for_flow_run_rewrites_a_local_api_url(
        self, default_configuration, flow_run
    ):
        default_configuration.api_dns_name = "172.18.0.1"
        default_configuration.env = {"PREFECT_API_URL": "http://127.0.0.1:4200/api"}

        default_configuration.prepare_for_flow_run(flow_run)

        env = default_configuration.job_manifest["podSpec"]["containers"][0]["env"]
        assert {
            "name": "PREFECT_API_URL",
            "value": "http://172.18.0.1:4200/api",
        } in env

    async def test_prepare_for_flow_run_rewrites_a_local_api_url_in_list_env(
        self, default_configuration, flow_run
    ):
        default_configuration.api_dns_name = "172.18.0.1"
        default_configuration.env = [
            {"name": "PREFECT_API_URL", "value": "http://localhost:4200/api"}
        ]

        default_configuration.prepare_for_flow_run(flow_run)

        env = default_configuration.job_manifest["podSpec"]["containers"][0]["env"]
        assert {
            "name": "PREFECT_API_URL",
            "value": "http://172.18.0.1:4200/api",
        } in env

    async def test_prepare_for_flow_run_leaves_a_routable_api_url_alone(
        self, default_configuration, flow_run, caplog
    ):
        default_configuration.api_dns_name = "172.18.0.1"
        default_configuration.env = {
            "PREFECT_API_URL": "http://prefect.example.com:4200/api"
        }

        default_configuration.prepare_for_flow_run(flow_run)

        env = default_configuration.job_manifest["podSpec"]["containers"][0]["env"]
        assert {
            "name": "PREFECT_API_URL",
            "value": "http://prefect.example.com:4200/api",
        } in env
        assert "resolves to the job's own pod" not in caplog.text

    async def test_prepare_for_flow_run_warns_about_an_unreachable_api_url(
        self, default_configuration, flow_run, caplog
    ):
        default_configuration.env = {"PREFECT_API_URL": "http://127.0.0.1:4200/api"}

        default_configuration.prepare_for_flow_run(flow_run)

        assert "resolves to the job's own pod" in caplog.text
        assert "api_dns_name" in caplog.text
        # The URL is left as-is; there is nothing to replace it with
        env = default_configuration.job_manifest["podSpec"]["containers"][0]["env"]
        assert {
            "name": "PREFECT_API_URL",
            "value": "http://127.0.0.1:4200/api",
        } in env

    async def test_api_dns_name_comes_from_the_work_pool_variables(self):
        configuration = await ArmadaWorkerJobConfiguration.from_template_and_values(
            ArmadaWorker.get_default_base_job_template(),
            {"api_dns_name": "172.18.0.1"},
        )

        assert configuration.api_dns_name == "172.18.0.1"

    async def test_prepare_for_flow_run_slugifies_labels_and_annotations(
        self, default_configuration, flow_run
    ):
        default_configuration.labels = {"my label": "my value"}
        default_configuration.annotations = {"my annotation": "an arbitrary: value"}

        default_configuration.prepare_for_flow_run(flow_run)

        manifest = default_configuration.job_manifest
        assert manifest["labels"]["my-label"] == "my-value"
        # Annotation values are arbitrary strings, so only keys are slugified
        assert manifest["annotations"]["my-annotation"] == "an arbitrary: value"

    async def test_prepare_for_flow_run_keeps_a_configured_job_set_id(
        self, default_configuration, flow_run
    ):
        default_configuration.job_set_id = "my-job-set"
        default_configuration.prepare_for_flow_run(flow_run)

        assert default_configuration.job_set_id == "my-job-set"

    async def test_prepare_for_flow_run_keeps_a_configured_image(self, flow_run):
        configuration = await ArmadaWorkerJobConfiguration.from_template_and_values(
            ArmadaWorker.get_default_base_job_template(),
            {"image": "my-registry/my-image:latest"},
        )

        configuration.prepare_for_flow_run(flow_run)

        assert (
            configuration.job_manifest["podSpec"]["containers"][0]["image"]
            == "my-registry/my-image:latest"
        )

    async def test_resource_requests_are_templated(self, flow_run):
        configuration = await ArmadaWorkerJobConfiguration.from_template_and_values(
            ArmadaWorker.get_default_base_job_template(),
            {"cpu_request": "500m", "memory_limit": "1Gi"},
        )

        configuration.prepare_for_flow_run(flow_run)

        resources = configuration.job_manifest["podSpec"]["containers"][0]["resources"]
        assert resources["requests"]["cpu"] == "500m"
        assert resources["limits"]["memory"] == "1Gi"

    async def test_get_environment_variable_value(
        self, default_configuration, flow_run
    ):
        default_configuration.env = {"MY_VAR": "my-value"}
        default_configuration.prepare_for_flow_run(flow_run)

        assert default_configuration.get_environment_variable_value("MY_VAR") == (
            "my-value"
        )
        assert default_configuration.get_environment_variable_value("NOPE") is None

    def test_get_credentials_defaults_to_the_environment(self, default_configuration):
        credentials = default_configuration.get_credentials()

        assert isinstance(credentials, ArmadaCredentials)
        assert credentials.cluster_config is None

    def test_get_credentials_uses_the_cluster_config(self, default_configuration):
        cluster_config = ArmadaClusterConfig(host="armada.example.com")
        default_configuration.cluster_config = cluster_config

        credentials = default_configuration.get_credentials()

        assert credentials.cluster_config is cluster_config

    def test_get_credentials_prefers_the_credentials_block(self, default_configuration):
        credentials_config = ArmadaClusterConfig(host="from-credentials.example.com")
        default_configuration.credentials = ArmadaCredentials(
            cluster_config=credentials_config, token="abc123"
        )
        default_configuration.cluster_config = ArmadaClusterConfig(
            host="from-configuration.example.com"
        )

        credentials = default_configuration.get_credentials()

        assert credentials.cluster_config is credentials_config

    def test_get_credentials_combines_auth_and_cluster_config(
        self, default_configuration
    ):
        cluster_config = ArmadaClusterConfig(host="armada.example.com")
        default_configuration.credentials = ArmadaCredentials(token="abc123")
        default_configuration.cluster_config = cluster_config

        credentials = default_configuration.get_credentials()

        assert credentials.cluster_config == cluster_config
        assert credentials.token.get_secret_value() == "abc123"

    async def test_host_and_port_come_from_the_work_pool_variables(self):
        configuration = await ArmadaWorkerJobConfiguration.from_template_and_values(
            ArmadaWorker.get_default_base_job_template(),
            {"armada_host": "armada.example.com", "armada_port": 12345},
        )

        assert configuration.armada_host == "armada.example.com"
        assert configuration.armada_port == 12345
        assert configuration.get_credentials().get_cluster_config().target == (
            "armada.example.com:12345"
        )

    def test_host_and_port_override_the_cluster_config(self, default_configuration):
        default_configuration.cluster_config = ArmadaClusterConfig(
            host="from-block.example.com", port=50051, disable_ssl=True
        )
        default_configuration.armada_host = "armada.example.com"
        default_configuration.armada_port = 12345

        cluster_config = default_configuration.get_credentials().get_cluster_config()

        assert cluster_config.target == "armada.example.com:12345"
        # Settings the work pool does not carry are kept from the block
        assert cluster_config.disable_ssl is True

    def test_host_and_port_override_independently(self, default_configuration):
        default_configuration.cluster_config = ArmadaClusterConfig(
            host="from-block.example.com", port=50051
        )
        default_configuration.armada_port = 12345

        cluster_config = default_configuration.get_credentials().get_cluster_config()

        assert cluster_config.target == "from-block.example.com:12345"

    async def test_disable_ssl_comes_from_the_work_pool_variables(self):
        configuration = await ArmadaWorkerJobConfiguration.from_template_and_values(
            ArmadaWorker.get_default_base_job_template(),
            {"armada_host": "armada.example.com", "armada_disable_ssl": True},
        )

        cluster_config = configuration.get_credentials().get_cluster_config()

        assert cluster_config.disable_ssl is True
        # An insecure channel is used when no call credentials need carrying
        assert cluster_config.get_channel_credentials() is None

    def test_disable_ssl_overrides_the_cluster_config(self, default_configuration):
        default_configuration.cluster_config = ArmadaClusterConfig(
            host="from-block.example.com", disable_ssl=True
        )
        default_configuration.armada_disable_ssl = False

        cluster_config = default_configuration.get_credentials().get_cluster_config()

        assert cluster_config.host == "from-block.example.com"
        assert cluster_config.disable_ssl is False

    async def test_root_certificates_path_comes_from_the_work_pool_variables(
        self, tmp_path
    ):
        ca_file = tmp_path / "ca.crt"
        ca_file.write_text("-----BEGIN CERTIFICATE-----\nwork-pool\n")
        configuration = await ArmadaWorkerJobConfiguration.from_template_and_values(
            ArmadaWorker.get_default_base_job_template(),
            {
                "armada_host": "armada.example.com",
                "armada_root_certificates_path": str(ca_file),
            },
        )

        cluster_config = configuration.get_credentials().get_cluster_config()

        assert cluster_config.root_certificates_path == ca_file
        assert cluster_config._resolve_root_certificates() == (
            b"-----BEGIN CERTIFICATE-----\nwork-pool\n"
        )

    def test_root_certificates_path_overrides_the_cluster_config(
        self, default_configuration, tmp_path
    ):
        # A work pool pointed at its own CA must win over inline PEM on a block,
        # which would otherwise take precedence when the channel is opened.
        ca_file = tmp_path / "ca.crt"
        ca_file.write_text("-----BEGIN CERTIFICATE-----\nwork-pool\n")
        default_configuration.cluster_config = ArmadaClusterConfig(
            host="from-block.example.com",
            root_certificates="-----BEGIN CERTIFICATE-----\nfrom-block\n",
        )
        default_configuration.armada_root_certificates_path = str(ca_file)

        cluster_config = default_configuration.get_credentials().get_cluster_config()

        assert cluster_config.root_certificates is None
        assert cluster_config._resolve_root_certificates() == (
            b"-----BEGIN CERTIFICATE-----\nwork-pool\n"
        )

    def test_root_certificates_are_not_overridden_when_unset(
        self, default_configuration
    ):
        default_configuration.cluster_config = ArmadaClusterConfig(
            host="from-block.example.com",
            root_certificates="-----BEGIN CERTIFICATE-----\nfrom-block\n",
        )
        default_configuration.armada_host = "armada.example.com"

        cluster_config = default_configuration.get_credentials().get_cluster_config()

        assert cluster_config._resolve_root_certificates() == (
            b"-----BEGIN CERTIFICATE-----\nfrom-block\n"
        )

    def test_disable_ssl_is_not_overridden_when_unset(self, default_configuration):
        default_configuration.cluster_config = ArmadaClusterConfig(
            host="from-block.example.com", disable_ssl=True
        )
        default_configuration.armada_host = "armada.example.com"

        cluster_config = default_configuration.get_credentials().get_cluster_config()

        assert cluster_config.disable_ssl is True

    def test_host_and_port_override_the_credentials_block(self, default_configuration):
        default_configuration.credentials = ArmadaCredentials(
            cluster_config=ArmadaClusterConfig(host="from-block.example.com"),
            token="abc123",
        )
        default_configuration.armada_host = "armada.example.com"

        credentials = default_configuration.get_credentials()

        assert credentials.get_cluster_config().host == "armada.example.com"
        assert credentials.token.get_secret_value() == "abc123"


class TestArmadaWorker:
    async def test_submits_a_job_and_reports_its_pid(
        self, default_configuration, flow_run, mock_armada_client, mock_observer
    ):
        mock_armada_client.submit_jobs.return_value = make_job_submit_response()
        default_configuration.prepare_for_flow_run(flow_run)

        async with ArmadaWorker(work_pool_name="test") as worker:
            result = await worker.run(
                flow_run=flow_run, configuration=default_configuration
            )

        expected_pid = f"prefect:{default_configuration.job_set_id}:test-job-id"
        assert result.identifier == expected_pid
        assert result.status_code == 0

        call = mock_armada_client.submit_jobs.call_args[1]
        assert call["queue"] == "prefect"
        assert call["job_set_id"] == default_configuration.job_set_id
        assert (
            call["job_request_items"][0].pod_spec.containers[0].image
            == get_prefect_image_name()
        )

    async def test_task_status_receives_the_job_pid(
        self, default_configuration, flow_run, mock_armada_client
    ):
        mock_armada_client.submit_jobs.return_value = make_job_submit_response()
        default_configuration.prepare_for_flow_run(flow_run)
        fake_status = MagicMock(spec=anyio.abc.TaskStatus)

        async with ArmadaWorker(work_pool_name="test") as worker:
            result = await worker.run(
                flow_run=flow_run,
                configuration=default_configuration,
                task_status=fake_status,
            )

        fake_status.started.assert_called_once_with(result.identifier)

    async def test_registers_the_job_set_with_the_observer(
        self, default_configuration, flow_run, mock_armada_client, mock_observer
    ):
        mock_armada_client.submit_jobs.return_value = make_job_submit_response()
        default_configuration.prepare_for_flow_run(flow_run)

        async with ArmadaWorker(work_pool_name="test") as worker:
            await worker.run(flow_run=flow_run, configuration=default_configuration)

        mock_observer.observe.assert_called_once()
        assert mock_observer.observe.call_args[1]["queue"] == "prefect"
        assert (
            mock_observer.observe.call_args[1]["job_set_id"]
            == default_configuration.job_set_id
        )

    async def test_initiate_run_submits_a_job(
        self, default_configuration, flow_run, mock_armada_client
    ):
        mock_armada_client.submit_jobs.return_value = make_job_submit_response()
        default_configuration.prepare_for_flow_run(flow_run)

        async with ArmadaWorker(work_pool_name="test") as worker:
            await worker._initiate_run(
                flow_run=flow_run, configuration=default_configuration
            )

        mock_armada_client.submit_jobs.assert_awaited_once()

    async def test_raises_infrastructure_error_when_armada_rejects_the_job(
        self, default_configuration, flow_run, mock_armada_client
    ):
        mock_armada_client.submit_jobs.return_value = make_job_submit_response(
            error="pod spec is invalid"
        )
        default_configuration.prepare_for_flow_run(flow_run)

        async with ArmadaWorker(work_pool_name="test") as worker:
            with pytest.raises(InfrastructureError, match="pod spec is invalid"):
                await worker.run(flow_run=flow_run, configuration=default_configuration)

    async def test_raises_infrastructure_error_with_a_hint_for_a_missing_queue(
        self, default_configuration, flow_run, mock_armada_client
    ):
        mock_armada_client.submit_jobs.side_effect = FakeRpcError(
            grpc.StatusCode.NOT_FOUND, "queue not found"
        )
        default_configuration.prepare_for_flow_run(flow_run)

        async with ArmadaWorker(work_pool_name="test") as worker:
            with pytest.raises(
                InfrastructureError, match="Verify that the queue 'prefect' exists"
            ):
                await worker.run(flow_run=flow_run, configuration=default_configuration)

    async def test_raises_infrastructure_error_with_a_hint_for_mismatched_resources(
        self, default_configuration, flow_run, mock_armada_client
    ):
        # Armada rejects a container whose requests and limits differ.
        mock_armada_client.submit_jobs.side_effect = FakeRpcError(
            grpc.StatusCode.INVALID_ARGUMENT,
            "container prefect-job defines different resources for requests and limits",
        )
        default_configuration.prepare_for_flow_run(flow_run)

        async with ArmadaWorker(work_pool_name="test") as worker:
            with pytest.raises(
                InfrastructureError, match="requests to equal its limits"
            ):
                await worker.run(flow_run=flow_run, configuration=default_configuration)

    async def test_retries_job_submission(
        self, default_configuration, flow_run, mock_armada_client, monkeypatch
    ):
        monkeypatch.setenv(
            "PREFECT_INTEGRATIONS_ARMADA_WORKER_SUBMIT_JOB_RETRY_DELAY_SECONDS", "0"
        )
        monkeypatch.setenv(
            "PREFECT_INTEGRATIONS_ARMADA_WORKER_SUBMIT_JOB_RETRY_JITTER_MAX_SECONDS",
            "0",
        )
        mock_armada_client.submit_jobs.side_effect = [
            FakeRpcError(grpc.StatusCode.UNAVAILABLE, "connection refused"),
            make_job_submit_response(),
        ]
        default_configuration.prepare_for_flow_run(flow_run)

        async with ArmadaWorker(work_pool_name="test") as worker:
            result = await worker.run(
                flow_run=flow_run, configuration=default_configuration
            )

        assert result.identifier.endswith("test-job-id")
        assert mock_armada_client.submit_jobs.await_count == 2

    async def test_kill_infrastructure_cancels_the_job(
        self, default_configuration, mock_armada_client
    ):
        mock_armada_client.cancel_jobs.return_value = submit_pb2.CancellationResult(
            cancelled_ids=["test-job-id"]
        )

        async with ArmadaWorker(work_pool_name="test") as worker:
            await worker.kill_infrastructure(
                infrastructure_pid="prefect:my-job-set:test-job-id",
                configuration=default_configuration,
            )

        assert mock_armada_client.cancel_jobs.call_args[1] == {
            "queue": "prefect",
            "job_set_id": "my-job-set",
            "job_id": "test-job-id",
        }

    async def test_kill_infrastructure_raises_when_nothing_was_cancelled(
        self, default_configuration, mock_armada_client
    ):
        mock_armada_client.cancel_jobs.return_value = submit_pb2.CancellationResult()

        async with ArmadaWorker(work_pool_name="test") as worker:
            with pytest.raises(InfrastructureNotFound, match="could not be cancelled"):
                await worker.kill_infrastructure(
                    infrastructure_pid="prefect:my-job-set:test-job-id",
                    configuration=default_configuration,
                )

    async def test_kill_infrastructure_raises_when_the_job_is_not_found(
        self, default_configuration, mock_armada_client
    ):
        mock_armada_client.cancel_jobs.side_effect = FakeRpcError(
            grpc.StatusCode.NOT_FOUND, "no such job"
        )

        async with ArmadaWorker(work_pool_name="test") as worker:
            with pytest.raises(InfrastructureNotFound, match="not found in queue"):
                await worker.kill_infrastructure(
                    infrastructure_pid="prefect:my-job-set:test-job-id",
                    configuration=default_configuration,
                )

    async def test_kill_infrastructure_reraises_other_rpc_errors(
        self, default_configuration, mock_armada_client
    ):
        mock_armada_client.cancel_jobs.side_effect = FakeRpcError(
            grpc.StatusCode.PERMISSION_DENIED, "not allowed"
        )

        async with ArmadaWorker(work_pool_name="test") as worker:
            with pytest.raises(grpc.RpcError):
                await worker.kill_infrastructure(
                    infrastructure_pid="prefect:my-job-set:test-job-id",
                    configuration=default_configuration,
                )

    async def test_kill_infrastructure_rejects_a_malformed_pid(
        self, default_configuration, mock_armada_client
    ):
        async with ArmadaWorker(work_pool_name="test") as worker:
            with pytest.raises(ValueError, match="Invalid infrastructure_pid"):
                await worker.kill_infrastructure(
                    infrastructure_pid="not-a-pid",
                    configuration=default_configuration,
                )

    async def test_observer_starts_and_stops_with_the_worker(self, mock_observer):
        async with ArmadaWorker(work_pool_name="test"):
            mock_observer.start.assert_called_once()
            mock_observer.stop.assert_not_called()

        mock_observer.stop.assert_called_once()

    async def test_observer_can_be_disabled(
        self, mock_observer, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("PREFECT_INTEGRATIONS_ARMADA_OBSERVER_ENABLED", "false")

        async with ArmadaWorker(work_pool_name="test"):
            pass

        mock_observer.start.assert_not_called()
        mock_observer.stop.assert_not_called()


class TestQueueCheckOnStartup:
    async def test_worker_starts_when_the_queue_exists(self, mock_armada_client):
        async with ArmadaWorker(work_pool_name=f"test-{uuid.uuid4()}") as worker:
            assert worker.is_setup

        mock_armada_client.get_queue.assert_awaited_once_with(name="prefect")

    async def test_worker_exits_when_the_queue_does_not_exist(
        self, mock_armada_client, mock_observer, caplog
    ):
        mock_armada_client.get_queue.side_effect = FakeRpcError(
            grpc.StatusCode.NOT_FOUND, "could not find queue"
        )
        worker = ArmadaWorker(work_pool_name=f"test-{uuid.uuid4()}")

        with pytest.raises(SystemExit) as exc_info:
            async with worker:
                pytest.fail("The worker should not start without its queue")

        assert exc_info.value.code == 1
        assert "Armada queue 'prefect'" in caplog.text
        assert "does not exist" in caplog.text
        assert not worker.is_setup
        mock_observer.stop.assert_called_once()

    async def test_start_exits_when_the_queue_does_not_exist(self, mock_armada_client):
        mock_armada_client.get_queue.side_effect = FakeRpcError(
            grpc.StatusCode.NOT_FOUND, "could not find queue"
        )
        worker = ArmadaWorker(work_pool_name=f"test-{uuid.uuid4()}")

        with pytest.raises(SystemExit) as exc_info:
            await worker.start(run_once=True)

        assert exc_info.value.code == 1

    async def test_checks_the_queue_configured_on_the_work_pool(
        self, mock_armada_client
    ):
        template = ArmadaWorker.get_default_base_job_template()
        template["variables"]["properties"]["queue"]["default"] = "my-queue"

        async with ArmadaWorker(
            work_pool_name=f"test-{uuid.uuid4()}", base_job_template=template
        ):
            pass

        mock_armada_client.get_queue.assert_awaited_once_with(name="my-queue")

    @pytest.mark.parametrize(
        "status_code",
        [grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.PERMISSION_DENIED],
    )
    async def test_worker_starts_when_the_queue_cannot_be_checked(
        self, mock_armada_client, caplog, status_code
    ):
        mock_armada_client.get_queue.side_effect = FakeRpcError(status_code, "nope")

        async with ArmadaWorker(work_pool_name=f"test-{uuid.uuid4()}") as worker:
            assert worker.is_setup

        assert "Unable to verify that Armada queue 'prefect' exists" in caplog.text


class TestWorkPoolTypeMetadata:
    """The work pool creation UI is driven entirely by this metadata, so a worker
    missing any of it is either unselectable or unlabelled."""

    def test_worker_is_registered_under_its_type(self):
        assert BaseWorker.get_worker_class_from_type("armada") is ArmadaWorker

    def test_display_name(self):
        assert ArmadaWorker.get_display_name() == "Armada"

    def test_description(self):
        assert "Armada" in ArmadaWorker.get_description()

    def test_logo_url(self):
        assert ArmadaWorker.get_logo_url().endswith(".svg")

    def test_documentation_url(self):
        assert ArmadaWorker.get_documentation_url().startswith("https://")

    def test_collections_view_metadata(self):
        """Metadata the server merges into the `aggregate-worker-metadata` view."""
        metadata = get_locally_installed_worker_metadata()

        assert metadata["prefect-armada"]["armada"] == {
            "type": "armada",
            "display_name": "Armada",
            "description": ArmadaWorker.get_description(),
            "documentation_url": ArmadaWorker.get_documentation_url(),
            "logo_url": ArmadaWorker.get_logo_url(),
            "install_command": "pip install prefect-armada",
            "default_base_job_configuration": (
                ArmadaWorker.get_default_base_job_template()
            ),
            "is_beta": False,
        }
