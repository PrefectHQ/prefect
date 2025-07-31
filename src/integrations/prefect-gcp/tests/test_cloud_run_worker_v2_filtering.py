import uuid

import pytest
from prefect_gcp.credentials import GcpCredentials
from prefect_gcp.models.cloud_run_v2 import SecretKeySelector
from prefect_gcp.workers.cloud_run_v2 import CloudRunWorkerJobV2Configuration

from prefect.client.schemas.objects import FlowRun


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
def flow_run():
    return FlowRun(flow_id=uuid.uuid4(), name="my-flow-run-name")


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

    def test_populate_env_filters_api_key_when_configured_via_env_from_secrets(
        self, cloud_run_worker_v2_job_config
    ):
        # Add plaintext API key to env
        cloud_run_worker_v2_job_config.env["PREFECT_API_KEY"] = "plaintext-api-key"
        # Configure API key via env_from_secrets instead of dedicated field
        cloud_run_worker_v2_job_config.env_from_secrets = {
            "PREFECT_API_KEY": SecretKeySelector(
                secret="prefect-api-key", version="latest"
            )
        }
        cloud_run_worker_v2_job_config._populate_env()

        env_vars = cloud_run_worker_v2_job_config.job_body["template"]["template"][
            "containers"
        ][0]["env"]

        # Should not contain plaintext version
        assert {"name": "PREFECT_API_KEY", "value": "plaintext-api-key"} not in env_vars
        # Should contain secret version from env_from_secrets
        assert {
            "name": "PREFECT_API_KEY",
            "valueSource": {
                "secretKeyRef": {"secret": "prefect-api-key", "version": "latest"}
            },
        } in env_vars
        # Other env vars should still be present
        assert {"name": "ENV1", "value": "VALUE1"} in env_vars
        assert {"name": "ENV2", "value": "VALUE2"} in env_vars

    def test_populate_env_filters_auth_string_when_configured_via_env_from_secrets(
        self, cloud_run_worker_v2_job_config
    ):
        # Add plaintext auth string to env
        cloud_run_worker_v2_job_config.env["PREFECT_API_AUTH_STRING"] = (
            "plaintext-auth-string"
        )
        # Configure auth string via env_from_secrets instead of dedicated field
        cloud_run_worker_v2_job_config.env_from_secrets = {
            "PREFECT_API_AUTH_STRING": SecretKeySelector(
                secret="prefect-auth-string", version="latest"
            )
        }
        cloud_run_worker_v2_job_config._populate_env()

        env_vars = cloud_run_worker_v2_job_config.job_body["template"]["template"][
            "containers"
        ][0]["env"]

        # Should not contain plaintext version
        assert {
            "name": "PREFECT_API_AUTH_STRING",
            "value": "plaintext-auth-string",
        } not in env_vars
        # Should contain secret version from env_from_secrets
        assert {
            "name": "PREFECT_API_AUTH_STRING",
            "valueSource": {
                "secretKeyRef": {"secret": "prefect-auth-string", "version": "latest"}
            },
        } in env_vars
        # Other env vars should still be present
        assert {"name": "ENV1", "value": "VALUE1"} in env_vars
        assert {"name": "ENV2", "value": "VALUE2"} in env_vars

    def test_populate_env_filters_both_when_configured_via_env_from_secrets(
        self, cloud_run_worker_v2_job_config
    ):
        # Add plaintext versions to env
        cloud_run_worker_v2_job_config.env["PREFECT_API_KEY"] = "plaintext-api-key"
        cloud_run_worker_v2_job_config.env["PREFECT_API_AUTH_STRING"] = (
            "plaintext-auth-string"
        )
        # Configure both via env_from_secrets
        cloud_run_worker_v2_job_config.env_from_secrets = {
            "PREFECT_API_KEY": SecretKeySelector(
                secret="prefect-api-key", version="latest"
            ),
            "PREFECT_API_AUTH_STRING": SecretKeySelector(
                secret="prefect-auth-string", version="latest"
            ),
        }
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
        # Should contain secret versions from env_from_secrets
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

    def test_populate_env_prioritizes_dedicated_secret_fields_over_env_from_secrets(
        self, cloud_run_worker_v2_job_config
    ):
        # Add plaintext versions to env
        cloud_run_worker_v2_job_config.env["PREFECT_API_KEY"] = "plaintext-api-key"
        cloud_run_worker_v2_job_config.env["PREFECT_API_AUTH_STRING"] = (
            "plaintext-auth-string"
        )
        # Configure via both dedicated fields and env_from_secrets
        cloud_run_worker_v2_job_config.prefect_api_key_secret = SecretKeySelector(
            secret="dedicated-api-key", version="latest"
        )
        cloud_run_worker_v2_job_config.prefect_api_auth_string_secret = (
            SecretKeySelector(secret="dedicated-auth-string", version="latest")
        )
        cloud_run_worker_v2_job_config.env_from_secrets = {
            "PREFECT_API_KEY": SecretKeySelector(
                secret="env-from-secrets-api-key", version="latest"
            ),
            "PREFECT_API_AUTH_STRING": SecretKeySelector(
                secret="env-from-secrets-auth-string", version="latest"
            ),
        }
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

        # Should contain dedicated field secrets (should be added after env_from_secrets)
        assert {
            "name": "PREFECT_API_KEY",
            "valueSource": {
                "secretKeyRef": {"secret": "dedicated-api-key", "version": "latest"}
            },
        } in env_vars
        assert {
            "name": "PREFECT_API_AUTH_STRING",
            "valueSource": {
                "secretKeyRef": {"secret": "dedicated-auth-string", "version": "latest"}
            },
        } in env_vars

        # Should also contain env_from_secrets versions
        assert {
            "name": "PREFECT_API_KEY",
            "valueSource": {
                "secretKeyRef": {
                    "secret": "env-from-secrets-api-key",
                    "version": "latest",
                }
            },
        } in env_vars
        assert {
            "name": "PREFECT_API_AUTH_STRING",
            "valueSource": {
                "secretKeyRef": {
                    "secret": "env-from-secrets-auth-string",
                    "version": "latest",
                }
            },
        } in env_vars

        # Other env vars should still be present
        assert {"name": "ENV1", "value": "VALUE1"} in env_vars
        assert {"name": "ENV2", "value": "VALUE2"} in env_vars


class TestCloudRunWorkerJobV2ConfigurationWarnings:
    def test_warn_about_plaintext_api_key(
        self, cloud_run_worker_v2_job_config, flow_run, caplog
    ):
        # Add plaintext API key to env
        cloud_run_worker_v2_job_config.env["PREFECT_API_KEY"] = "plaintext-api-key"

        cloud_run_worker_v2_job_config.prepare_for_flow_run(
            flow_run=flow_run, deployment=None, flow=None
        )

        assert (
            "PREFECT_API_KEY is provided as a plaintext environment variable"
            in caplog.text
        )
        assert "consider providing it as a secret using" in caplog.text
        assert "'prefect_api_key_secret' or 'env_from_secrets'" in caplog.text

    def test_warn_about_plaintext_auth_string(
        self, cloud_run_worker_v2_job_config, flow_run, caplog
    ):
        # Add plaintext auth string to env
        cloud_run_worker_v2_job_config.env["PREFECT_API_AUTH_STRING"] = (
            "plaintext-auth-string"
        )

        cloud_run_worker_v2_job_config.prepare_for_flow_run(
            flow_run=flow_run, deployment=None, flow=None
        )

        assert (
            "PREFECT_API_AUTH_STRING is provided as a plaintext environment variable"
            in caplog.text
        )
        assert "consider providing it as a secret using" in caplog.text
        assert "'prefect_api_auth_string_secret' or 'env_from_secrets'" in caplog.text

    def test_warn_about_both_plaintext_credentials(
        self, cloud_run_worker_v2_job_config, flow_run, caplog
    ):
        # Add both plaintext credentials to env
        cloud_run_worker_v2_job_config.env["PREFECT_API_KEY"] = "plaintext-api-key"
        cloud_run_worker_v2_job_config.env["PREFECT_API_AUTH_STRING"] = (
            "plaintext-auth-string"
        )

        cloud_run_worker_v2_job_config.prepare_for_flow_run(
            flow_run=flow_run, deployment=None, flow=None
        )

        # Should warn about both
        assert "PREFECT_API_KEY is provided as a plaintext" in caplog.text
        assert "PREFECT_API_AUTH_STRING is provided as a plaintext" in caplog.text

    def test_no_warning_when_api_key_secret_configured(
        self, cloud_run_worker_v2_job_config, flow_run, caplog
    ):
        # Add plaintext API key but configure secret
        cloud_run_worker_v2_job_config.env["PREFECT_API_KEY"] = "plaintext-api-key"
        cloud_run_worker_v2_job_config.prefect_api_key_secret = SecretKeySelector(
            secret="prefect-api-key", version="latest"
        )

        cloud_run_worker_v2_job_config.prepare_for_flow_run(
            flow_run=flow_run, deployment=None, flow=None
        )

        # Should not warn since secret is configured
        assert "PREFECT_API_KEY is provided as a plaintext" not in caplog.text

    def test_no_warning_when_auth_string_in_env_from_secrets(
        self, cloud_run_worker_v2_job_config, flow_run, caplog
    ):
        # Add plaintext auth string but configure it in env_from_secrets
        cloud_run_worker_v2_job_config.env["PREFECT_API_AUTH_STRING"] = (
            "plaintext-auth-string"
        )
        cloud_run_worker_v2_job_config.env_from_secrets = {
            "PREFECT_API_AUTH_STRING": SecretKeySelector(
                secret="prefect-auth-string", version="latest"
            )
        }

        cloud_run_worker_v2_job_config.prepare_for_flow_run(
            flow_run=flow_run, deployment=None, flow=None
        )

        # Should not warn since secret is configured via env_from_secrets
        assert "PREFECT_API_AUTH_STRING is provided as a plaintext" not in caplog.text

    def test_no_warning_when_no_plaintext_credentials(
        self, cloud_run_worker_v2_job_config, flow_run, caplog
    ):
        # Don't add any plaintext credentials
        cloud_run_worker_v2_job_config.prepare_for_flow_run(
            flow_run=flow_run, deployment=None, flow=None
        )

        # Should not warn since no plaintext credentials are present
        assert "is provided as a plaintext environment variable" not in caplog.text
