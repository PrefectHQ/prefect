import pytest

pytest.importorskip("dask_gateway")

from prefect.environments.execution import DaskGatewayEnvironment


def test_create_environment():
    environment = DaskGatewayEnvironment(gateway_address="")
    assert environment


def test_create_dask_gateway_environment():
    environment = DaskGatewayEnvironment(gateway_address="")
    assert environment
    assert environment.executor_kwargs == {"address": ""}
    assert environment.labels == set()
    assert environment._on_execute is None
    assert environment.on_start is None
    assert environment.on_exit is None
    assert environment.logger.name == "prefect.DaskGatewayEnvironment"


def test_create_dask_gateway_environment_with_executor_kwargs():
    environment = DaskGatewayEnvironment(
        gateway_address="", executor_kwargs={"test": "here"}
    )
    assert environment
    assert environment.executor_kwargs == {"address": "", "test": "here"}


def test_create_dask_gateway_environment_labels():
    environment = DaskGatewayEnvironment(gateway_address="", labels=["foo"])
    assert environment
    assert environment.labels == set(["foo"])


def test_create_dask_gateway_environment_callbacks():
    def f():
        pass

    environment = DaskGatewayEnvironment(
        gateway_address="", labels=["foo"], on_execute=f, on_start=f, on_exit=f,
    )
    assert environment
    assert environment.labels == set(["foo"])
    assert environment._on_execute is f
    assert environment.on_start is f
    assert environment.on_exit is f


def test_dask_gateway_environment_dependencies():
    environment = DaskGatewayEnvironment(gateway_address="")
    assert environment.dependencies == ["dask_gateway"]
