import json
import os
from pathlib import Path

import pytest
import toml
from prefect_kubernetes.settings import KubernetesSettings


def test_set_values_via_environment_variables(monkeypatch: pytest.MonkeyPatch):
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


def test_set_values_via_dot_env_file(tmp_path: Path):
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


def test_set_values_via_prefect_toml_file(tmp_path: Path):
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


def test_set_values_via_pyproject_toml_file(tmp_path: Path):
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


class TestObserverSettings:
    @pytest.mark.parametrize(
        "env_var_value",
        [
            "key1=value1,key2=value2",
            json.dumps({"key1": "value1", "key2": "value2"}),
        ],
    )
    def test_additional_label_filters(
        self, monkeypatch: pytest.MonkeyPatch, env_var_value: str
    ):
        monkeypatch.setenv(
            "PREFECT_INTEGRATIONS_KUBERNETES_OBSERVER_ADDITIONAL_LABEL_FILTERS",
            env_var_value,
        )
        settings = KubernetesSettings()
        assert settings.observer.additional_label_filters == {
            "key1": "value1",
            "key2": "value2",
        }

    @pytest.mark.parametrize(
        "env_var_value",
        [
            "namespace1,namespace2",
            json.dumps(["namespace1", "namespace2"]),
        ],
    )
    def test_namespaces(self, monkeypatch: pytest.MonkeyPatch, env_var_value: str):
        monkeypatch.setenv(
            "PREFECT_INTEGRATIONS_KUBERNETES_OBSERVER_NAMESPACES",
            env_var_value,
        )
        settings = KubernetesSettings()
        assert settings.observer.namespaces == {"namespace1", "namespace2"}
