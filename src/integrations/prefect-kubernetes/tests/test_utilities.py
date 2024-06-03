from unittest.mock import MagicMock

import pytest
from kubernetes.config import ConfigException
from prefect_kubernetes.utilities import (
    enable_socket_keep_alive,
)

FAKE_CLUSTER = "fake-cluster"


@pytest.fixture
def mock_cluster_config(monkeypatch):
    mock = MagicMock()
    # We cannot mock this or the `except` clause will complain
    mock.config.ConfigException = ConfigException
    mock.list_kube_config_contexts.return_value = (
        [],
        {"context": {"cluster": FAKE_CLUSTER}},
    )
    monkeypatch.setattr("kubernetes.config", mock)
    monkeypatch.setattr("kubernetes.config.ConfigException", ConfigException)
    return mock


@pytest.fixture
def mock_api_client(mock_cluster_config):
    return MagicMock()


def test_keep_alive_updates_socket_options(mock_api_client):
    enable_socket_keep_alive(mock_api_client)

    assert (
        mock_api_client.rest_client.pool_manager.connection_pool_kw[
            "socket_options"
        ]._mock_set_call
        is not None
    )
