from unittest import mock

import pytest
from prefect_gcp.settings import (
    CloudRunV2Settings,
    CloudRunV2WorkerSettings,
    GcpSettings,
)
from pydantic import ValidationError


class TestCloudRunV2WorkerSettings:
    def test_defaults(self):
        settings = CloudRunV2WorkerSettings()

        assert settings.create_job_max_attempts == 3
        assert settings.create_job_initial_delay_seconds == 1.0
        assert settings.create_job_max_delay_seconds == 10.0

    def test_load_from_env(self):
        with mock.patch.dict(
            "os.environ",
            {
                "PREFECT_INTEGRATIONS_GCP_CLOUD_RUN_V2_WORKER_CREATE_JOB_MAX_ATTEMPTS": "7",
                "PREFECT_INTEGRATIONS_GCP_CLOUD_RUN_V2_WORKER_CREATE_JOB_INITIAL_DELAY_SECONDS": "2.5",
                "PREFECT_INTEGRATIONS_GCP_CLOUD_RUN_V2_WORKER_CREATE_JOB_MAX_DELAY_SECONDS": "20.0",
            },
        ):
            settings = CloudRunV2WorkerSettings()

        assert settings.create_job_max_attempts == 7
        assert settings.create_job_initial_delay_seconds == 2.5
        assert settings.create_job_max_delay_seconds == 20.0

    @pytest.mark.parametrize("invalid_value", [0, -1])
    def test_invalid_max_attempts_raises(self, invalid_value):
        with pytest.raises(ValidationError):
            CloudRunV2WorkerSettings(create_job_max_attempts=invalid_value)

    @pytest.mark.parametrize("invalid_value", [0, -1.0])
    def test_invalid_initial_delay_raises(self, invalid_value):
        with pytest.raises(ValidationError):
            CloudRunV2WorkerSettings(create_job_initial_delay_seconds=invalid_value)

    @pytest.mark.parametrize("invalid_value", [0, -1.0])
    def test_invalid_max_delay_raises(self, invalid_value):
        with pytest.raises(ValidationError):
            CloudRunV2WorkerSettings(create_job_max_delay_seconds=invalid_value)


class TestSettingsHierarchy:
    def test_gcp_settings_includes_cloud_run_v2(self):
        settings = GcpSettings()

        assert isinstance(settings.cloud_run_v2, CloudRunV2Settings)
        assert isinstance(settings.cloud_run_v2.worker, CloudRunV2WorkerSettings)

    def test_nested_env_var_loading(self):
        with mock.patch.dict(
            "os.environ",
            {
                "PREFECT_INTEGRATIONS_GCP_CLOUD_RUN_V2_WORKER_CREATE_JOB_MAX_ATTEMPTS": "9",
            },
        ):
            settings = GcpSettings()

        assert settings.cloud_run_v2.worker.create_job_max_attempts == 9
