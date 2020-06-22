import pytest

from distributed.security import Security

from prefect.environments import RemoteDaskEnvironment


def test_create_remote_environment():
    address_kwargs = {"address": "tcp://127.0.0.1:8786"}
    environment = RemoteDaskEnvironment(address=address_kwargs["address"])
    assert environment
    assert environment.executor == "prefect.engine.executors.DaskExecutor"
    assert environment.executor_kwargs == address_kwargs
    assert environment.labels == set()
    assert environment.on_start is None
    assert environment.on_exit is None
    assert environment.metadata == {}
    assert environment.logger.name == "prefect.RemoteDaskEnvironment"


def test_create_remote_environment_populated():
    def f():
        pass

    address_kwargs = {"address": "tcp://127.0.0.1:8786"}
    security = Security(
        tls_ca_file="cluster_ca.pem",
        tls_client_cert="cli_cert.pem",
        tls_client_key="cli_key.pem",
        require_encryption=True,
    )
    arbitrary_kwargs = {"arbitrary": "value"}
    environment = RemoteDaskEnvironment(
        address=address_kwargs["address"],
        security=security,
        executor_kwargs=arbitrary_kwargs,
        labels=["foo", "bar", "good"],
        on_start=f,
        on_exit=f,
    )
    arbitrary_kwargs["address"] = address_kwargs["address"]
    arbitrary_kwargs["security"] = security
    assert environment
    assert environment.executor == "prefect.engine.executors.DaskExecutor"
    assert environment.executor_kwargs == arbitrary_kwargs
    assert environment.labels == set(["foo", "bar", "good"])
    assert environment.on_start is f
    assert environment.on_exit is f


def test_remote_environment_dependencies():
    environment = RemoteDaskEnvironment("tcp://127.0.0.1:8786")
    assert environment.dependencies == []
