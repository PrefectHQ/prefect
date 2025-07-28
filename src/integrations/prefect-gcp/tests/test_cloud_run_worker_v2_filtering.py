import pytest
from prefect_gcp.credentials import GcpCredentials
from prefect_gcp.models.cloud_run_v2 import SecretKeySelector
from prefect_gcp.workers.cloud_run_v2 import CloudRunWorkerJobV2Configuration


@pytest.fixture
def job_body():
    return {
        "client": "prefect",
        "launchStage": None,
        "template": {
            "template": {
                "maxRetries": None,
                "timeout": None,
                "vpcAccess": {
                    "connector": None,
                },
                "containers": [
                    {
                        "env": [],
                        "command": None,
                        "args": "-m prefect.engine",
                        "resources": {
                            "limits": {
                                "cpu": None,
                                "memory": None,
                            },
                        },
                    },
                ],
            }
        },
    }


@pytest.fixture
def cloud_run_worker_v2_job_config(service_account_info, job_body):
    return CloudRunWorkerJobV2Configuration(
        name="my-job-name",
        job_body=job_body,
        credentials=GcpCredentials(service_account_info=service_account_info),
        region="us-central1",
        timeout=86400,
        env={"ENV1": "VALUE1", "ENV2": "VALUE2"},
    )


class TestCloudRunWorkerJobV2ConfigurationFiltering:
    def test_populate_env_filters_plaintext_api_key_when_secret_configured(
        self, cloud_run_worker_v2_job_config
    ):
        # Add plaintext API key to env
        cloud_run_worker_v2_job_config.env["PREFECT_API_KEY"] = "plaintext-api-key"
        cloud_run_worker_v2_job_config.prefect_api_key_secret = SecretKeySelector(
            secret="prefect-api-key", version="latest"
        )
        cloud_run_worker_v2_job_config._populate_env()

        env_vars = cloud_run_worker_v2_job_config.job_body["template"]["template"][
            "containers"
        ][0]["env"]

        # Should not contain plaintext version
        assert {"name": "PREFECT_API_KEY", "value": "plaintext-api-key"} not in env_vars
        # Should contain secret version
        assert {
            "name": "PREFECT_API_KEY",
            "valueSource": {
                "secretKeyRef": {"secret": "prefect-api-key", "version": "latest"}
            },
        } in env_vars
        # Other env vars should still be present
        assert {"name": "ENV1", "value": "VALUE1"} in env_vars
        assert {"name": "ENV2", "value": "VALUE2"} in env_vars

    def test_populate_env_filters_plaintext_auth_string_when_secret_configured(
        self, cloud_run_worker_v2_job_config
    ):
        # Add plaintext auth string to env
        cloud_run_worker_v2_job_config.env["PREFECT_API_AUTH_STRING"] = (
            "plaintext-auth-string"
        )
        cloud_run_worker_v2_job_config.prefect_api_auth_string_secret = (
            SecretKeySelector(secret="prefect-auth-string", version="latest")
        )
        cloud_run_worker_v2_job_config._populate_env()

        env_vars = cloud_run_worker_v2_job_config.job_body["template"]["template"][
            "containers"
        ][0]["env"]

        # Should not contain plaintext version
        assert {
            "name": "PREFECT_API_AUTH_STRING",
            "value": "plaintext-auth-string",
        } not in env_vars
        # Should contain secret version
        assert {
            "name": "PREFECT_API_AUTH_STRING",
            "valueSource": {
                "secretKeyRef": {"secret": "prefect-auth-string", "version": "latest"}
            },
        } in env_vars
        # Other env vars should still be present
        assert {"name": "ENV1", "value": "VALUE1"} in env_vars
        assert {"name": "ENV2", "value": "VALUE2"} in env_vars

    def test_populate_env_filters_both_plaintext_when_secrets_configured(
        self, cloud_run_worker_v2_job_config
    ):
        # Add plaintext versions to env
        cloud_run_worker_v2_job_config.env["PREFECT_API_KEY"] = "plaintext-api-key"
        cloud_run_worker_v2_job_config.env["PREFECT_API_AUTH_STRING"] = (
            "plaintext-auth-string"
        )
        cloud_run_worker_v2_job_config.prefect_api_key_secret = SecretKeySelector(
            secret="prefect-api-key", version="latest"
        )
        cloud_run_worker_v2_job_config.prefect_api_auth_string_secret = (
            SecretKeySelector(secret="prefect-auth-string", version="latest")
        )
        cloud_run_worker_v2_job_config._populate_env()

        env_vars = cloud_run_worker_v2_job_config.job_body["template"]["template"][
            "containers"
        ][0]["env"]

        # Should not contain plaintext versions
        assert {"name": "PREFECT_API_KEY", "value": "plaintext-api-key"} not in env_vars
        assert {
            "name": "PREFECT_API_AUTH_STRING",
            "value": "plaintext-auth-string",
        } not in env_vars
        # Should contain secret versions
        assert {
            "name": "PREFECT_API_KEY",
            "valueSource": {
                "secretKeyRef": {"secret": "prefect-api-key", "version": "latest"}
            },
        } in env_vars
        assert {
            "name": "PREFECT_API_AUTH_STRING",
            "valueSource": {
                "secretKeyRef": {"secret": "prefect-auth-string", "version": "latest"}
            },
        } in env_vars
        # Other env vars should still be present
        assert {"name": "ENV1", "value": "VALUE1"} in env_vars
        assert {"name": "ENV2", "value": "VALUE2"} in env_vars

    def test_populate_env_keeps_plaintext_when_no_secrets_configured(
        self, cloud_run_worker_v2_job_config
    ):
        # Add plaintext versions to env but don't configure secrets
        cloud_run_worker_v2_job_config.env["PREFECT_API_KEY"] = "plaintext-api-key"
        cloud_run_worker_v2_job_config.env["PREFECT_API_AUTH_STRING"] = (
            "plaintext-auth-string"
        )
        cloud_run_worker_v2_job_config._populate_env()

        env_vars = cloud_run_worker_v2_job_config.job_body["template"]["template"][
            "containers"
        ][0]["env"]

        # Should contain plaintext versions since no secrets are configured
        assert {"name": "PREFECT_API_KEY", "value": "plaintext-api-key"} in env_vars
        assert {
            "name": "PREFECT_API_AUTH_STRING",
            "value": "plaintext-auth-string",
        } in env_vars
        # Other env vars should still be present
        assert {"name": "ENV1", "value": "VALUE1"} in env_vars
        assert {"name": "ENV2", "value": "VALUE2"} in env_vars
