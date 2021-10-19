from unittest.mock import MagicMock

import pytest

pytest.importorskip("kubernetes")

from kubernetes import client
from kubernetes.config.config_exception import ConfigException

import prefect
from prefect.utilities.kubernetes import get_kubernetes_client
from prefect.utilities.configuration import set_temporary_config


@pytest.fixture
def kube_secret():
    with set_temporary_config({"cloud.use_local_secrets": True}):
        with prefect.context(secrets=dict(KUBERNETES_API_KEY="test_key")):
            yield


class TestGetKubernetesClient:
    @pytest.mark.parametrize(
        "resource,client_type",
        [
            ("job", client.BatchV1Api),
            ("pod", client.CoreV1Api),
            ("service", client.CoreV1Api),
            ("deployment", client.AppsV1Api),
        ],
    )
    def test_returns_correct_kubernetes_client(
        self, resource, client_type, kube_secret
    ):
        k8s_client = get_kubernetes_client(resource)
        assert isinstance(k8s_client, client_type)

    def test_api_key_pulled_from_secret(self, monkeypatch, kube_secret):
        client = MagicMock()
        monkeypatch.setattr("prefect.utilities.kubernetes.client", client)

        api_key = {}
        conf_call = MagicMock()
        conf_call.return_value.api_key = api_key
        monkeypatch.setattr(
            "prefect.utilities.kubernetes.client.Configuration", conf_call
        )
        get_kubernetes_client("job")
        assert api_key == {"authorization": "test_key"}

    def test_kube_config_in_cluster(self, monkeypatch):
        config = MagicMock()
        monkeypatch.setattr("prefect.utilities.kubernetes.kube_config", config)

        batchapi = MagicMock()
        monkeypatch.setattr(
            "prefect.utilities.kubernetes.client",
            MagicMock(BatchV1Api=MagicMock(return_value=batchapi)),
        )

        get_kubernetes_client("job", kubernetes_api_key_secret=None)
        assert config.load_incluster_config.called

    def test_kube_config_out_of_cluster(self, monkeypatch):
        config = MagicMock()
        config.load_incluster_config.side_effect = ConfigException()
        monkeypatch.setattr("prefect.utilities.kubernetes.kube_config", config)

        batchapi = MagicMock()
        monkeypatch.setattr(
            "prefect.utilities.kubernetes.client",
            MagicMock(BatchV1Api=MagicMock(return_value=batchapi)),
        )

        get_kubernetes_client("job", kubernetes_api_key_secret=None)
        assert config.load_kube_config.called

    @pytest.mark.parametrize("keep_alive_enabled", [True, False])
    def test_kube_client_with_keep_alive(self, keep_alive_enabled, monkeypatch, cloud_api, kube_secret):
        with set_temporary_config({"cloud.agent.kubernetes_keep_alive": keep_alive_enabled}):
            k8s_client = get_kubernetes_client("job", kubernetes_api_key_secret=None)

            assert not ('socket_options' in k8s_client.api_client.rest_client.pool_manager.connection_pool_kw) ^ \
                   keep_alive_enabled
            assert not ('socket_options' in k8s_client.api_client.rest_client.pool_manager.connection_pool_kw) ^ \
                   keep_alive_enabled
