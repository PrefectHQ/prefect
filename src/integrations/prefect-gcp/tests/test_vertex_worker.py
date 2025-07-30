import uuid
from unittest.mock import MagicMock

import pydantic
import pytest
from google.cloud.aiplatform_v1.types.custom_job import Scheduling
from google.cloud.aiplatform_v1.types.job_state import JobState
from prefect_gcp.workers.vertex import (
    VertexAIWorker,
    VertexAIWorkerJobConfiguration,
    VertexAIWorkerResult,
)

from prefect.client.schemas import FlowRun


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


@pytest.fixture
def flow_run():
    return FlowRun(flow_id=uuid.uuid4(), name="my-flow-run-name")


class TestVertexAIWorkerJobConfiguration:
    async def test_validate_empty_job_spec(self, gcp_credentials):
        base_job_template = VertexAIWorker.get_default_base_job_template()
        base_job_template["job_configuration"]["job_spec"] = {}
        base_job_template["job_configuration"]["region"] = "us-central1"

        with pytest.raises(pydantic.ValidationError) as excinfo:
            await VertexAIWorkerJobConfiguration.from_template_and_values(
                base_job_template, {"credentials": gcp_credentials}
            )

        assert len(errs := excinfo.value.errors()) == 1
        loc, msg, type_ = [errs[0].get(k) for k in ("loc", "msg", "type")]
        assert "job_spec" in str(loc)
        assert type_ == "value_error"
        assert "/maximum_run_time_hours" in msg
        assert "/worker_pool_specs" in msg

    async def test_validate_incomplete_worker_pool_spec(self, gcp_credentials):
        base_job_template = VertexAIWorker.get_default_base_job_template()
        base_job_template["job_configuration"]["job_spec"] = {
            "maximum_run_time_hours": 1,
            "worker_pool_specs": [
                {
                    "replica_count": 1,
                    "container_spec": {"command": ["some", "command"]},
                    "machine_spec": {
                        "accelerator_type": "NVIDIA_TESLA_K80",
                    },
                },
            ],
        }
        base_job_template["job_configuration"]["region"] = "us-central1"

        with pytest.raises(pydantic.ValidationError) as excinfo:
            await VertexAIWorkerJobConfiguration.from_template_and_values(
                base_job_template, {"credentials": gcp_credentials}
            )

        assert len(errs := excinfo.value.errors()) == 1
        loc, msg, type_ = [errs[0].get(k) for k in ("loc", "msg", "type")]
        assert "job_spec" in str(loc)
        assert type_ == "value_error"
        assert "/worker_pool_specs/0/container_spec/image_uri" in msg
        assert "/worker_pool_specs/0/disk_spec" in msg
        assert "/worker_pool_specs/0/machine_spec/machine_type" in msg

    def test_gcp_project(self, job_config: VertexAIWorkerJobConfiguration):
        assert job_config.project == "gcp_credentials_project"

    def test_job_name(self, flow_run, job_config: VertexAIWorkerJobConfiguration):
        job_config.prepare_for_flow_run(flow_run, None, None)
        assert job_config.job_name.startswith("my-custom-ai-job")

        job_config.name = None
        job_config.prepare_for_flow_run(flow_run, None, None)
        assert job_config.job_name.startswith("my-flow-run-name")

    async def test_missing_service_account(self, flow_run, job_config):
        job_config.job_spec["service_account_name"] = None
        job_config.credentials._service_account_email = None

        with pytest.raises(
            ValueError, match="A service account is required for the Vertex job"
        ):
            job_config.prepare_for_flow_run(flow_run, None, None)

    def test_valid_command_formatting(
        self, flow_run, job_config: VertexAIWorkerJobConfiguration
    ):
        job_config.prepare_for_flow_run(flow_run, None, None)
        assert ["python", "-m", "prefect.engine"] == job_config.job_spec[
            "worker_pool_specs"
        ][0]["container_spec"]["command"]

        job_config.job_spec["worker_pool_specs"][0]["container_spec"]["command"] = (
            "echo -n hello"
        )
        job_config.prepare_for_flow_run(flow_run, None, None)
        assert ["echo", "-n", "hello"] == job_config.job_spec["worker_pool_specs"][0][
            "container_spec"
        ]["command"]


class TestVertexAIWorker:
    async def test_successful_worker_run(self, flow_run, job_config):
        async with VertexAIWorker("test-pool") as worker:
            job_config.prepare_for_flow_run(flow_run, None, None)
            result = await worker.run(flow_run=flow_run, configuration=job_config)
            assert (
                job_config.credentials.job_service_async_client.create_custom_job.call_count
                == 1
            )
            custom_job_spec = job_config.credentials.job_service_async_client.create_custom_job.call_args[
                1
            ]["custom_job"].job_spec

            assert custom_job_spec.service_account == "my-service-account"

            assert (
                job_config.credentials.job_service_async_client.get_custom_job.call_count
                == 1
            )
            assert result == VertexAIWorkerResult(
                status_code=0, identifier="mock_display_name"
            )

    async def test_initiate_run_does_not_wait_for_completion(
        self, flow_run, job_config
    ):
        async with VertexAIWorker("test-pool") as worker:
            job_config.prepare_for_flow_run(flow_run, None, None)
            await worker._initiate_run(flow_run=flow_run, configuration=job_config)

            job_config.credentials.job_service_async_client.create_custom_job.assert_called_once()
            # The worker doesn't wait for the job to complete, so the get_custom_job call should not have been made
            job_config.credentials.job_service_async_client.get_custom_job.assert_not_called()

    async def test_missing_scheduling(self, flow_run, job_config):
        job_config.job_spec["scheduling"] = None

        async with VertexAIWorker("test-pool") as worker:
            job_config.prepare_for_flow_run(flow_run, None, None)
            await worker.run(flow_run=flow_run, configuration=job_config)

    async def test_params_worker_run(self, flow_run, job_config):
        async with VertexAIWorker("test-pool") as worker:
            # Initialize scheduling parameters
            maximum_run_time_hours = job_config.job_spec["maximum_run_time_hours"]
            max_wait_duration = job_config.job_spec["scheduling"]["max_wait_duration"]
            timeout = str(maximum_run_time_hours * 60 * 60) + "s"
            scheduling = Scheduling(
                timeout=timeout, max_wait_duration=max_wait_duration
            )

            # Additional params
            enable_web_access = job_config.job_spec["enable_web_access"]
            enable_dashboard_access = job_config.job_spec["enable_dashboard_access"]

            job_config.prepare_for_flow_run(flow_run, None, None)
            result = await worker.run(flow_run=flow_run, configuration=job_config)

            custom_job_spec = job_config.credentials.job_service_async_client.create_custom_job.call_args[
                1
            ]["custom_job"].job_spec

            # Assert scheduling parameters
            assert custom_job_spec.scheduling.timeout == scheduling.timeout
            assert (
                custom_job_spec.scheduling.strategy == Scheduling.Strategy["FLEX_START"]
            )
            assert (
                custom_job_spec.scheduling.max_wait_duration
                == scheduling.max_wait_duration
            )
            # Assert additional parameters
            assert custom_job_spec.enable_web_access == enable_web_access
            assert custom_job_spec.enable_dashboard_access == enable_dashboard_access

            assert (
                job_config.credentials.job_service_async_client.get_custom_job.call_count
                == 1
            )
            assert result == VertexAIWorkerResult(
                status_code=0, identifier="mock_display_name"
            )

    async def test_failed_worker_run(self, flow_run, job_config):
        job_config.prepare_for_flow_run(flow_run, None, None)
        error_msg = "something went kablooey"
        error_job_display_name = "catastrophization"
        job_config.credentials.job_service_async_client.get_custom_job.return_value = (
            MagicMock(
                name="error_mock_name",
                state=JobState.JOB_STATE_FAILED,
                error=MagicMock(message=error_msg),
                display_name=error_job_display_name,
            )
        )
        async with VertexAIWorker("test-pool") as worker:
            with pytest.raises(RuntimeError, match=error_msg):
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

    def test_prefect_api_key_secret_removes_env_var_and_adds_secret_ref(
        self, service_account_info, gcp_credentials, flow_run
    ):
        """Test that configuring a Prefect API key secret removes the env var and adds secret reference."""
        job_config = VertexAIWorkerJobConfiguration(
            name="my-custom-ai-job",
            region="us-central1",
            credentials=gcp_credentials,
            prefect_api_key_secret_name="my-prefect-api-key",
            prefect_api_key_secret_version="1",
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
        job_config.env["PREFECT_API_KEY"] = "pnu_test_key"

        job_config.prepare_for_flow_run(flow_run, None, None)

        # PREFECT_API_KEY should be removed from env
        assert "PREFECT_API_KEY" not in job_config.env

        # Secret reference should be added
        assert "PREFECT_API_KEY_SECRET_REF" in job_config.env
        expected_secret_ref = (
            f"projects/{gcp_credentials.project}/secrets/my-prefect-api-key/versions/1"
        )
        assert job_config.env["PREFECT_API_KEY_SECRET_REF"] == expected_secret_ref

    def test_prefect_api_auth_string_secret_removes_env_var_and_adds_secret_ref(
        self, service_account_info, gcp_credentials, flow_run
    ):
        """Test that configuring a Prefect API auth string secret removes the env var and adds secret reference."""
        job_config = VertexAIWorkerJobConfiguration(
            name="my-custom-ai-job",
            region="us-central1",
            credentials=gcp_credentials,
            prefect_api_auth_string_secret_name="my-prefect-auth-string",
            prefect_api_auth_string_secret_version="latest",
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
        job_config.env["PREFECT_API_AUTH_STRING"] = "test_auth_string"

        job_config.prepare_for_flow_run(flow_run, None, None)

        # PREFECT_API_AUTH_STRING should be removed from env
        assert "PREFECT_API_AUTH_STRING" not in job_config.env

        # Secret reference should be added
        assert "PREFECT_API_AUTH_STRING_SECRET_REF" in job_config.env
        expected_secret_ref = f"projects/{gcp_credentials.project}/secrets/my-prefect-auth-string/versions/latest"
        assert (
            job_config.env["PREFECT_API_AUTH_STRING_SECRET_REF"] == expected_secret_ref
        )

    def test_both_secrets_configured(
        self, service_account_info, gcp_credentials, flow_run
    ):
        """Test that both API key and auth string secrets can be configured simultaneously."""
        job_config = VertexAIWorkerJobConfiguration(
            name="my-custom-ai-job",
            region="us-central1",
            credentials=gcp_credentials,
            prefect_api_key_secret_name="my-prefect-api-key",
            prefect_api_key_secret_version="2",
            prefect_api_auth_string_secret_name="my-prefect-auth-string",
            prefect_api_auth_string_secret_version="3",
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
        job_config.env["PREFECT_API_KEY"] = "pnu_test_key"
        job_config.env["PREFECT_API_AUTH_STRING"] = "test_auth_string"

        job_config.prepare_for_flow_run(flow_run, None, None)

        # Both should be removed from env
        assert "PREFECT_API_KEY" not in job_config.env
        assert "PREFECT_API_AUTH_STRING" not in job_config.env

        # Both secret references should be added
        assert "PREFECT_API_KEY_SECRET_REF" in job_config.env
        assert "PREFECT_API_AUTH_STRING_SECRET_REF" in job_config.env

        expected_api_key_ref = (
            f"projects/{gcp_credentials.project}/secrets/my-prefect-api-key/versions/2"
        )
        expected_auth_string_ref = f"projects/{gcp_credentials.project}/secrets/my-prefect-auth-string/versions/3"

        assert job_config.env["PREFECT_API_KEY_SECRET_REF"] == expected_api_key_ref
        assert (
            job_config.env["PREFECT_API_AUTH_STRING_SECRET_REF"]
            == expected_auth_string_ref
        )

    def test_secret_version_defaults_to_latest(
        self, service_account_info, gcp_credentials, flow_run
    ):
        """Test that secret version defaults to 'latest' when not specified."""
        job_config = VertexAIWorkerJobConfiguration(
            name="my-custom-ai-job",
            region="us-central1",
            credentials=gcp_credentials,
            prefect_api_key_secret_name="my-prefect-api-key",
            # No version specified - should default to 'latest'
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

        job_config.env["PREFECT_API_KEY"] = "pnu_test_key"
        job_config.prepare_for_flow_run(flow_run, None, None)

        expected_secret_ref = f"projects/{gcp_credentials.project}/secrets/my-prefect-api-key/versions/latest"
        assert job_config.env["PREFECT_API_KEY_SECRET_REF"] == expected_secret_ref

    def test_no_secrets_configured_preserves_env_vars(
        self, service_account_info, gcp_credentials, flow_run
    ):
        """Test that when no secrets are configured, environment variables are preserved."""
        job_config = VertexAIWorkerJobConfiguration(
            name="my-custom-ai-job",
            region="us-central1",
            credentials=gcp_credentials,
            # No secret names configured
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
        job_config.env["PREFECT_API_KEY"] = "pnu_test_key"
        job_config.env["PREFECT_API_AUTH_STRING"] = "test_auth_string"

        job_config.prepare_for_flow_run(flow_run, None, None)

        # Both should be preserved in env
        assert job_config.env["PREFECT_API_KEY"] == "pnu_test_key"
        assert job_config.env["PREFECT_API_AUTH_STRING"] == "test_auth_string"

        # No secret references should be added
        assert "PREFECT_API_KEY_SECRET_REF" not in job_config.env
        assert "PREFECT_API_AUTH_STRING_SECRET_REF" not in job_config.env
