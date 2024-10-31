import os

import toml
from prefect_kubernetes.settings import KubernetesSettings


def test_set_values_via_environment_variables(monkeypatch):
    monkeypatch.setenv(
        "PREFECT_INTEGRATIONS_KUBERNETES_WORKER_API_KEY_SECRET_NAME", "test-secret"
    )
    monkeypatch.setenv(
        "PREFECT_INTEGRATIONS_KUBERNETES_WORKER_CREATE_SECRET_FOR_API_KEY", "true"
    )
    monkeypatch.setenv(
        "PREFECT_INTEGRATIONS_KUBERNETES_WORKER_ADD_TCP_KEEPALIVE", "false"
    )
    monkeypatch.setenv(
        "PREFECT_INTEGRATIONS_KUBERNETES_CLUSTER_UID", "test-cluster-uid"
    )

    settings = KubernetesSettings()

    assert settings.worker.api_key_secret_name == "test-secret"
    assert settings.worker.create_secret_for_api_key is True
    assert settings.worker.add_tcp_keepalive is False
    assert settings.cluster_uid == "test-cluster-uid"


def test_set_values_via_dot_env_file(tmp_path):
    dot_env_path = tmp_path / ".env"
    with open(dot_env_path, "w") as f:
        f.write(
            "PREFECT_INTEGRATIONS_KUBERNETES_WORKER_API_KEY_SECRET_NAME=test-secret\n"
            "PREFECT_INTEGRATIONS_KUBERNETES_WORKER_CREATE_SECRET_FOR_API_KEY=true\n"
            "PREFECT_INTEGRATIONS_KUBERNETES_WORKER_ADD_TCP_KEEPALIVE=false\n"
            "PREFECT_INTEGRATIONS_KUBERNETES_CLUSTER_UID=test-cluster-uid\n"
        )

    original_dir = os.getcwd()
    try:
        os.chdir(tmp_path)
        settings = KubernetesSettings()
    finally:
        os.chdir(original_dir)

    assert settings.worker.api_key_secret_name == "test-secret"
    assert settings.worker.create_secret_for_api_key is True
    assert settings.worker.add_tcp_keepalive is False
    assert settings.cluster_uid == "test-cluster-uid"


def test_set_values_via_prefect_toml_file(tmp_path):
    toml_path = tmp_path / "prefect.toml"
    toml_data = {
        "integrations": {
            "kubernetes": {
                "worker": {
                    "api_key_secret_name": "test-secret",
                    "create_secret_for_api_key": True,
                    "add_tcp_keepalive": False,
                },
                "cluster_uid": "test-cluster-uid",
            },
        },
    }
    toml_path.write_text(toml.dumps(toml_data))

    original_dir = os.getcwd()
    try:
        os.chdir(tmp_path)
        settings = KubernetesSettings()
    finally:
        os.chdir(original_dir)

    assert settings.worker.api_key_secret_name == "test-secret"
    assert settings.worker.create_secret_for_api_key is True
    assert settings.worker.add_tcp_keepalive is False
    assert settings.cluster_uid == "test-cluster-uid"


def test_set_values_via_pyproject_toml_file(tmp_path):
    pyproject_toml_path = tmp_path / "pyproject.toml"
    pyproject_toml_data = {
        "tool": {
            "prefect": {
                "integrations": {
                    "kubernetes": {
                        "cluster_uid": "test-cluster-uid",
                        "worker": {
                            "api_key_secret_name": "test-secret",
                            "create_secret_for_api_key": True,
                            "add_tcp_keepalive": False,
                        },
                    },
                },
            },
        },
    }
    pyproject_toml_path.write_text(toml.dumps(pyproject_toml_data))

    original_dir = os.getcwd()
    try:
        os.chdir(tmp_path)
        settings = KubernetesSettings()
    finally:
        os.chdir(original_dir)

    assert settings.worker.api_key_secret_name == "test-secret"
    assert settings.worker.create_secret_for_api_key is True
    assert settings.worker.add_tcp_keepalive is False
    assert settings.cluster_uid == "test-cluster-uid"
