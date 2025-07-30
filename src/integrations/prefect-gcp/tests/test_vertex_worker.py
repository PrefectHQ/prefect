import uuid
from unittest.mock import MagicMock, patch

import pydantic
import pytest
from google.cloud.aiplatform_v1.types.custom_job import Scheduling
from google.cloud.aiplatform_v1.types.job_state import JobState
from prefect_gcp.models.cloud_run_v2 import SecretKeySelector
from prefect_gcp.workers.vertex import (
    VertexAIWorker,
    VertexAIWorkerJobConfiguration,
    VertexAIWorkerResult,
)

from prefect.client.schemas import FlowRun


@pytest.fixture
def flow_run():
    return FlowRun(flow_id=uuid.uuid4(), name="my-flow-run-name")


@pytest.fixture
def job_config(service_account_info, gcp_credentials):
    return VertexAIWorkerJobConfiguration(
        name="my-custom-ai-job",
        region="ashenvale",
        credentials=gcp_credentials,
        job_spec={
            "service_account_name": "my-service-account",
            "maximum_run_time_hours": 1,
            "worker_pool_specs": [
                {
                    "replica_count": 1,
                    "container_spec": {
                        "image_uri": "gcr.io/your-project/your-repo:latest",
                        "command": ["python", "-m", "prefect.engine"],
                    },
                    "machine_spec": {
                        "machine_type": "n1-standard-4",
                        "accelerator_type": "NVIDIA_TESLA_K80",
                        "accelerator_count": 1,
                    },
                    "disk_spec": {
                        "boot_disk_type": "pd-ssd",
                        "boot_disk_size_gb": 100,
                    },
                }
            ],
            "scheduling": {
                "strategy": "FLEX_START",
                "max_wait_duration": "1800s",
            },
            "enable_web_access": True,
            "enable_dashboard_access": True,
        },
    )


class TestVertexAIWorkerJobConfiguration:
    def test_validate_empty_job_spec(self, service_account_info, gcp_credentials):
        with pytest.raises(pydantic.ValidationError, match="missing required"):
            VertexAIWorkerJobConfiguration(
                name="my-custom-ai-job",
                region="ashenvale",
                credentials=gcp_credentials,
                job_spec={},
            )

    def test_validate_incomplete_worker_pool_spec(
        self, service_account_info, gcp_credentials
    ):
        with pytest.raises(pydantic.ValidationError, match="missing required"):
            VertexAIWorkerJobConfiguration(
                name="my-custom-ai-job",
                region="ashenvale",
                credentials=gcp_credentials,
                job_spec={
                    "service_account_name": "my-service-account",
                    "maximum_run_time_hours": 1,
                    "worker_pool_specs": [
                        {"replica_count": 1}  # missing container_spec
                    ],
                },
            )

    def test_gcp_project(self, job_config):
        assert job_config.project == "gcp_credentials_project"

    def test_job_name(self, job_config):
        assert job_config.job_name.startswith("my-custom-ai-job-")
        # Ensure the UUID suffix is appended
        assert len(job_config.job_name.split("-")) >= 5

    def test_missing_service_account(self, service_account_info, gcp_credentials):
        # Remove service account from credentials for test isolation
        gcp_credentials._service_account_email = None

        job_config = VertexAIWorkerJobConfiguration(
            name="my-custom-ai-job",
            region="ashenvale",
            credentials=gcp_credentials,
            job_spec={
                "maximum_run_time_hours": 1,
                "worker_pool_specs": [
                    {
                        "replica_count": 1,
                        "container_spec": {
                            "image_uri": "gcr.io/your-project/your-repo:latest",
                        },
                        "machine_spec": {
                            "machine_type": "n1-standard-4",
                        },
                        "disk_spec": {
                            "boot_disk_type": "pd-ssd",
                            "boot_disk_size_gb": 100,
                        },
                    }
                ],
            },
        )
        flow_run = FlowRun.model_validate(
            {
                "id": "00000000-0000-0000-0000-000000000000",
                "name": "my-flow-run",
                "flow_id": "00000000-0000-0000-0000-000000000000",
                "state_type": "PENDING",
                "state_name": "Pending",
            }
        )
        with pytest.raises(ValueError, match="A service account is required"):
            job_config.prepare_for_flow_run(flow_run, None, None)

    def test_valid_command_formatting(
        self, service_account_info, gcp_credentials, flow_run
    ):
        job_config = VertexAIWorkerJobConfiguration(
            name="my-custom-ai-job",
            region="ashenvale",
            credentials=gcp_credentials,
            job_spec={
                "service_account_name": "my-service-account",
                "maximum_run_time_hours": 1,
                "worker_pool_specs": [
                    {
                        "replica_count": 1,
                        "container_spec": {
                            "image_uri": "gcr.io/your-project/your-repo:latest",
                            "command": "python -m prefect.engine",
                        },
                        "machine_spec": {
                            "machine_type": "n1-standard-4",
                        },
                        "disk_spec": {
                            "boot_disk_type": "pd-ssd",
                            "boot_disk_size_gb": 100,
                        },
                    }
                ],
            },
        )
        job_config.prepare_for_flow_run(flow_run, None, None)
        actual_command = job_config.job_spec["worker_pool_specs"][0]["container_spec"][
            "command"
        ]
        expected_command = ["python", "-m", "prefect.engine"]
        assert actual_command == expected_command


class TestVertexAIWorker:
    async def test_successful_worker_run(self, flow_run, job_config):
        job_config.prepare_for_flow_run(flow_run, None, None)
        job_display_name = "a-job-well-done"
        job_config.credentials.job_service_async_client.get_custom_job.return_value = (
            MagicMock(
                name="mock_name",
                state=JobState.JOB_STATE_SUCCEEDED,
                error=MagicMock(message=""),
                display_name=job_display_name,
            )
        )
        async with VertexAIWorker("test-pool") as worker:
            result = await worker.run(flow_run=flow_run, configuration=job_config)
            assert (
                job_config.credentials.job_service_async_client.create_custom_job.call_count
                == 1
            )
            assert (
                job_config.credentials.job_service_async_client.get_custom_job.call_count
                == 1
            )
            assert result == VertexAIWorkerResult(
                status_code=0, identifier=job_display_name
            )

    async def test_initiate_run_does_not_wait_for_completion(
        self, flow_run, job_config
    ):
        job_config.prepare_for_flow_run(flow_run, None, None)
        async with VertexAIWorker("test-pool") as worker:
            await worker._initiate_run(flow_run=flow_run, configuration=job_config)
            # create_custom_job is called but not get_custom_job
            assert (
                job_config.credentials.job_service_async_client.create_custom_job.call_count
                == 1
            )
            assert (
                job_config.credentials.job_service_async_client.get_custom_job.call_count
                == 0
            )

    async def test_missing_scheduling(self, flow_run, job_config):
        job_config.job_spec.pop("scheduling")
        job_config.prepare_for_flow_run(flow_run, None, None)
        job_display_name = "a-job-well-done"
        job_config.credentials.job_service_async_client.get_custom_job.return_value = (
            MagicMock(
                name="mock_name",
                state=JobState.JOB_STATE_SUCCEEDED,
                error=MagicMock(message=""),
                display_name=job_display_name,
            )
        )
        async with VertexAIWorker("test-pool") as worker:
            result = await worker.run(flow_run=flow_run, configuration=job_config)
            assert (
                job_config.credentials.job_service_async_client.create_custom_job.call_count
                == 1
            )
            assert (
                job_config.credentials.job_service_async_client.get_custom_job.call_count
                == 1
            )
            assert result == VertexAIWorkerResult(
                status_code=0, identifier=job_display_name
            )

    async def test_params_worker_run(self, flow_run, job_config):
        job_config.job_spec.update(
            {
                "scheduling": {
                    "strategy": Scheduling.Strategy.FLEX_START,
                    "max_wait_duration": "1800s",
                }
            }
        )
        job_config.prepare_for_flow_run(flow_run, None, None)
        job_display_name = "a-job-well-done"
        job_config.credentials.job_service_async_client.get_custom_job.return_value = (
            MagicMock(
                name="mock_name",
                state=JobState.JOB_STATE_SUCCEEDED,
                error=MagicMock(message=""),
                display_name=job_display_name,
            )
        )
        async with VertexAIWorker("test-pool") as worker:
            result = await worker.run(flow_run=flow_run, configuration=job_config)
            assert (
                job_config.credentials.job_service_async_client.create_custom_job.call_count
                == 1
            )
            assert (
                job_config.credentials.job_service_async_client.get_custom_job.call_count
                == 1
            )
            assert result == VertexAIWorkerResult(
                status_code=0, identifier=job_display_name
            )

    async def test_failed_worker_run(self, flow_run, job_config):
        job_config.prepare_for_flow_run(flow_run, None, None)
        job_display_name = "a-job-well-done"
        job_config.credentials.job_service_async_client.get_custom_job.return_value = (
            MagicMock(
                name="mock_name",
                state=JobState.JOB_STATE_FAILED,
                error=MagicMock(message="Test error message"),
                display_name=job_display_name,
            )
        )
        async with VertexAIWorker("test-pool") as worker:
            with pytest.raises(RuntimeError, match="Test error message"):
                await worker.run(flow_run=flow_run, configuration=job_config)
            assert (
                job_config.credentials.job_service_async_client.create_custom_job.call_count
                == 1
            )
            assert (
                job_config.credentials.job_service_async_client.get_custom_job.call_count
                == 1
            )

    async def test_cancelled_worker_run(self, flow_run, job_config):
        job_config.prepare_for_flow_run(flow_run, None, None)
        job_display_name = "a-job-well-done"
        job_config.credentials.job_service_async_client.get_custom_job.return_value = (
            MagicMock(
                name="cancelled_mock_name",
                state=JobState.JOB_STATE_CANCELLED,
                error=MagicMock(message=""),
                display_name=job_display_name,
            )
        )
        async with VertexAIWorker("test-pool") as worker:
            result = await worker.run(flow_run=flow_run, configuration=job_config)
            assert (
                job_config.credentials.job_service_async_client.create_custom_job.call_count
                == 1
            )
            assert (
                job_config.credentials.job_service_async_client.get_custom_job.call_count
                == 1
            )
            assert result == VertexAIWorkerResult(
                status_code=1, identifier=job_display_name
            )


class TestVertexAIWorkerSecrets:
    """Test Prefect API key and auth string secret configuration."""

    @patch("prefect_gcp.workers.vertex.secretmanager.SecretManagerServiceClient")
    def test_prefect_api_key_secret_fetches_and_sets_env_var(
        self, mock_client_class, service_account_info, gcp_credentials, flow_run
    ):
        """Test that configuring a Prefect API key secret fetches the value and sets it as env var."""
        # Mock the secret manager client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.payload.data.decode.return_value = "fetched_api_key_value"
        mock_client.access_secret_version.return_value = mock_response

        job_config = VertexAIWorkerJobConfiguration(
            name="my-custom-ai-job",
            region="us-central1",
            credentials=gcp_credentials,
            prefect_api_key_secret=SecretKeySelector(
                secret="my-prefect-api-key", version="1"
            ),
            job_spec={
                "service_account_name": "my-service-account",
                "maximum_run_time_hours": 1,
                "worker_pool_specs": [
                    {
                        "replica_count": 1,
                        "container_spec": {
                            "image_uri": "gcr.io/your-project/your-repo:latest",
                        },
                        "machine_spec": {
                            "machine_type": "n1-standard-4",
                        },
                        "disk_spec": {
                            "boot_disk_type": "pd-ssd",
                            "boot_disk_size_gb": 100,
                        },
                    }
                ],
            },
        )

        # Add PREFECT_API_KEY to env to simulate it being set
        job_config.env["PREFECT_API_KEY"] = "original_key"

        job_config.prepare_for_flow_run(flow_run, None, None)

        # PREFECT_API_KEY should contain the fetched secret value
        assert job_config.env["PREFECT_API_KEY"] == "fetched_api_key_value"

        # Verify secret was fetched correctly
        expected_secret_name = (
            f"projects/{gcp_credentials.project}/secrets/my-prefect-api-key/versions/1"
        )
        mock_client.access_secret_version.assert_called_once_with(
            request={"name": expected_secret_name}
        )

    @patch("prefect_gcp.workers.vertex.secretmanager.SecretManagerServiceClient")
    def test_prefect_api_auth_string_secret_fetches_and_sets_env_var(
        self, mock_client_class, service_account_info, gcp_credentials, flow_run
    ):
        """Test that configuring a Prefect API auth string secret fetches the value and sets it as env var."""
        # Mock the secret manager client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.payload.data.decode.return_value = "fetched_auth_string_value"
        mock_client.access_secret_version.return_value = mock_response

        job_config = VertexAIWorkerJobConfiguration(
            name="my-custom-ai-job",
            region="us-central1",
            credentials=gcp_credentials,
            prefect_api_auth_string_secret=SecretKeySelector(
                secret="my-prefect-auth-string", version="latest"
            ),
            job_spec={
                "service_account_name": "my-service-account",
                "maximum_run_time_hours": 1,
                "worker_pool_specs": [
                    {
                        "replica_count": 1,
                        "container_spec": {
                            "image_uri": "gcr.io/your-project/your-repo:latest",
                        },
                        "machine_spec": {
                            "machine_type": "n1-standard-4",
                        },
                        "disk_spec": {
                            "boot_disk_type": "pd-ssd",
                            "boot_disk_size_gb": 100,
                        },
                    }
                ],
            },
        )

        # Add PREFECT_API_AUTH_STRING to env to simulate it being set
        job_config.env["PREFECT_API_AUTH_STRING"] = "original_auth_string"

        job_config.prepare_for_flow_run(flow_run, None, None)

        # PREFECT_API_AUTH_STRING should contain the fetched secret value
        assert job_config.env["PREFECT_API_AUTH_STRING"] == "fetched_auth_string_value"

        # Verify secret was fetched correctly
        expected_secret_name = f"projects/{gcp_credentials.project}/secrets/my-prefect-auth-string/versions/latest"
        mock_client.access_secret_version.assert_called_once_with(
            request={"name": expected_secret_name}
        )

    @patch("prefect_gcp.workers.vertex.secretmanager.SecretManagerServiceClient")
    def test_both_secrets_configured(
        self, mock_client_class, service_account_info, gcp_credentials, flow_run
    ):
        """Test that both API key and auth string secrets can be configured simultaneously."""
        # Mock the secret manager client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Setup different responses for different secret calls
        def side_effect(request):
            mock_response = MagicMock()
            if "my-prefect-api-key" in request["name"]:
                mock_response.payload.data.decode.return_value = "fetched_api_key"
            elif "my-prefect-auth-string" in request["name"]:
                mock_response.payload.data.decode.return_value = "fetched_auth_string"
            return mock_response

        mock_client.access_secret_version.side_effect = side_effect

        job_config = VertexAIWorkerJobConfiguration(
            name="my-custom-ai-job",
            region="us-central1",
            credentials=gcp_credentials,
            prefect_api_key_secret=SecretKeySelector(
                secret="my-prefect-api-key", version="2"
            ),
            prefect_api_auth_string_secret=SecretKeySelector(
                secret="my-prefect-auth-string", version="3"
            ),
            job_spec={
                "service_account_name": "my-service-account",
                "maximum_run_time_hours": 1,
                "worker_pool_specs": [
                    {
                        "replica_count": 1,
                        "container_spec": {
                            "image_uri": "gcr.io/your-project/your-repo:latest",
                        },
                        "machine_spec": {
                            "machine_type": "n1-standard-4",
                        },
                        "disk_spec": {
                            "boot_disk_type": "pd-ssd",
                            "boot_disk_size_gb": 100,
                        },
                    }
                ],
            },
        )

        # Add both env vars to simulate them being set
        job_config.env["PREFECT_API_KEY"] = "original_key"
        job_config.env["PREFECT_API_AUTH_STRING"] = "original_auth_string"

        job_config.prepare_for_flow_run(flow_run, None, None)

        # Both should contain the fetched secret values
        assert job_config.env["PREFECT_API_KEY"] == "fetched_api_key"
        assert job_config.env["PREFECT_API_AUTH_STRING"] == "fetched_auth_string"

        # Verify both secrets were fetched
        assert mock_client.access_secret_version.call_count == 2

    def test_no_secrets_configured_preserves_env_vars(
        self, service_account_info, gcp_credentials, flow_run
    ):
        """Test that when no secrets are configured, environment variables are preserved."""
        job_config = VertexAIWorkerJobConfiguration(
            name="my-custom-ai-job",
            region="us-central1",
            credentials=gcp_credentials,
            # No secrets configured
            job_spec={
                "service_account_name": "my-service-account",
                "maximum_run_time_hours": 1,
                "worker_pool_specs": [
                    {
                        "replica_count": 1,
                        "container_spec": {
                            "image_uri": "gcr.io/your-project/your-repo:latest",
                        },
                        "machine_spec": {
                            "machine_type": "n1-standard-4",
                        },
                        "disk_spec": {
                            "boot_disk_type": "pd-ssd",
                            "boot_disk_size_gb": 100,
                        },
                    }
                ],
            },
        )

        # Add both env vars to simulate them being set
        job_config.env["PREFECT_API_KEY"] = "original_key"
        job_config.env["PREFECT_API_AUTH_STRING"] = "original_auth_string"

        job_config.prepare_for_flow_run(flow_run, None, None)

        # Both should be preserved unchanged
        assert job_config.env["PREFECT_API_KEY"] == "original_key"
        assert job_config.env["PREFECT_API_AUTH_STRING"] == "original_auth_string"

    @patch("prefect_gcp.workers.vertex.secretmanager.SecretManagerServiceClient")
    def test_secret_fetch_error_handling(
        self, mock_client_class, service_account_info, gcp_credentials, flow_run
    ):
        """Test that secret fetch errors are properly handled."""
        # Mock the secret manager client to raise an exception
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.access_secret_version.side_effect = Exception("Secret not found")

        job_config = VertexAIWorkerJobConfiguration(
            name="my-custom-ai-job",
            region="us-central1",
            credentials=gcp_credentials,
            prefect_api_key_secret=SecretKeySelector(
                secret="nonexistent-secret", version="1"
            ),
            job_spec={
                "service_account_name": "my-service-account",
                "maximum_run_time_hours": 1,
                "worker_pool_specs": [
                    {
                        "replica_count": 1,
                        "container_spec": {
                            "image_uri": "gcr.io/your-project/your-repo:latest",
                        },
                        "machine_spec": {
                            "machine_type": "n1-standard-4",
                        },
                        "disk_spec": {
                            "boot_disk_type": "pd-ssd",
                            "boot_disk_size_gb": 100,
                        },
                    }
                ],
            },
        )

        # Should raise a RuntimeError with descriptive message
        with pytest.raises(
            RuntimeError,
            match="Failed to fetch secret 'nonexistent-secret' version '1'",
        ):
            job_config.prepare_for_flow_run(flow_run, None, None)
