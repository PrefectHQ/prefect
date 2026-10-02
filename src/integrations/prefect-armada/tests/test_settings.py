from pathlib import Path

import pytest
from prefect_armada.settings import (
    ArmadaSettings,
    ArmadaWorkerSubmitJobRetrySettings,
)


def test_defaults():
    settings = ArmadaSettings()

    assert settings.cluster_uid is None
    assert settings.connection.host == "localhost"
    assert settings.connection.port == 50051
    assert settings.connection.binoculars_port == 50053
    assert settings.worker.default_queue == "prefect"
    assert settings.worker.add_grpc_keepalive is True
    assert settings.worker.submit_job_retry.max_retries == 3
    assert settings.observer.enabled is True
    assert settings.observer.replicate_job_events is True
    assert settings.observer.job_sets == set()


def test_set_values_via_environment_variables(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(
        "PREFECT_INTEGRATIONS_ARMADA_CONNECTION_HOST", "armada.example.com"
    )
    monkeypatch.setenv("PREFECT_INTEGRATIONS_ARMADA_CONNECTION_PORT", "50055")
    monkeypatch.setenv("PREFECT_INTEGRATIONS_ARMADA_WORKER_DEFAULT_QUEUE", "batch")
    monkeypatch.setenv("PREFECT_INTEGRATIONS_ARMADA_OBSERVER_ENABLED", "false")
    monkeypatch.setenv("PREFECT_INTEGRATIONS_ARMADA_CLUSTER_UID", "test-cluster-uid")

    settings = ArmadaSettings()

    assert settings.connection.host == "armada.example.com"
    assert settings.connection.port == 50055
    assert settings.worker.default_queue == "batch"
    assert settings.observer.enabled is False
    assert settings.cluster_uid == "test-cluster-uid"


def test_connection_settings_honor_armada_tooling_variables(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("ARMADA_SERVER", "armada.example.com")
    monkeypatch.setenv("ARMADA_PORT", "50057")
    monkeypatch.setenv("ARMADA_DISABLE_SSL", "true")

    settings = ArmadaSettings()

    assert settings.connection.host == "armada.example.com"
    assert settings.connection.port == 50057
    assert settings.connection.disable_ssl is True


def test_prefect_settings_take_precedence_over_armada_variables(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("ARMADA_SERVER", "armada-tooling.example.com")
    monkeypatch.setenv(
        "PREFECT_INTEGRATIONS_ARMADA_CONNECTION_HOST", "armada-prefect.example.com"
    )

    assert ArmadaSettings().connection.host == "armada-prefect.example.com"


def test_token_is_a_secret(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PREFECT_INTEGRATIONS_ARMADA_CONNECTION_TOKEN", "abc123")

    token = ArmadaSettings().connection.token

    assert token is not None
    assert "abc123" not in repr(token)
    assert token.get_secret_value() == "abc123"


def test_observer_job_sets_are_parsed_from_a_delimited_string(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv(
        "PREFECT_INTEGRATIONS_ARMADA_OBSERVER_JOB_SETS",
        "queue-a/set-1,queue-b/set-2",
    )

    assert ArmadaSettings().observer.job_sets == {"queue-a/set-1", "queue-b/set-2"}


def test_submit_job_retry_settings(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(
        "PREFECT_INTEGRATIONS_ARMADA_WORKER_SUBMIT_JOB_RETRY_MAX_RETRIES", "5"
    )
    monkeypatch.setenv(
        "PREFECT_INTEGRATIONS_ARMADA_WORKER_SUBMIT_JOB_RETRY_DELAY_SECONDS", "2"
    )

    settings = ArmadaWorkerSubmitJobRetrySettings()

    assert settings.max_retries == 5
    assert settings.delay_seconds == 2
    assert ArmadaSettings().worker.submit_job_retry.max_retries == 5


def test_max_retries_must_be_positive(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(
        "PREFECT_INTEGRATIONS_ARMADA_WORKER_SUBMIT_JOB_RETRY_MAX_RETRIES", "0"
    )
    with pytest.raises(ValueError):
        ArmadaWorkerSubmitJobRetrySettings()


def test_root_certificates_path_from_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    ca_file = tmp_path / "ca.crt"
    monkeypatch.setenv(
        "PREFECT_INTEGRATIONS_ARMADA_CONNECTION_ROOT_CERTIFICATES_PATH", str(ca_file)
    )

    assert ArmadaSettings().connection.root_certificates_path == ca_file


def test_root_certificates_honor_the_armada_tooling_variable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    ca_file = tmp_path / "ca.crt"
    monkeypatch.setenv("ARMADA_ROOT_CERTIFICATES_PATH", str(ca_file))

    assert ArmadaSettings().connection.root_certificates_path == ca_file


def test_root_certificates_are_a_secret(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(
        "PREFECT_INTEGRATIONS_ARMADA_CONNECTION_ROOT_CERTIFICATES", "a-pem-blob"
    )

    root_certificates = ArmadaSettings().connection.root_certificates

    assert root_certificates is not None
    assert root_certificates.get_secret_value() == "a-pem-blob"
    assert "a-pem-blob" not in str(root_certificates)
