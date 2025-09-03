from unittest.mock import MagicMock

import pytest
from kubernetes_asyncio.config import ConfigException

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
    monkeypatch.setattr("kubernetes_asyncio.config", mock)
    monkeypatch.setattr("kubernetes_asyncio.config.ConfigException", ConfigException)
    return mock


@pytest.fixture
def mock_api_client(mock_cluster_config):
    return MagicMock()
