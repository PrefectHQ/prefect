import pytest
from pytest import raises

from distributed.deploy import Cluster

from prefect.environments.execution import DaskCloudProviderEnvironment


def test_create_environment():
    environment = DaskCloudProviderEnvironment(Cluster)
    assert environment
