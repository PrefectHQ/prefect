import pytest
from cryptography.fernet import Fernet
from distributed import Client

import prefect
from prefect.engine.executors import DaskExecutor, LocalExecutor, SynchronousExecutor
from prefect.utilities import tests


@pytest.fixture(scope="module")
def threaded():
    with Client(processes=False) as client:
        yield DaskExecutor(client.scheduler.address)


@pytest.fixture(scope="module")
def local():
    yield LocalExecutor()


@pytest.fixture(scope="module")
def sync():
    yield SynchronousExecutor()


@pytest.fixture(scope="module")
def multi():
    with Client(processes=True) as client:
        yield DaskExecutor(client.scheduler.address)


@pytest.fixture()
def switch(threaded, local, sync, multi):
    execs = dict(threaded=threaded, local=local, sync=sync, multi=multi)
    return lambda e: execs[e]


@pytest.fixture()
def executor(request, switch):
    return switch(request.param)


@pytest.fixture(autouse=True, scope="session")
def set_config():
    """
    Creates a registry encryption key for testing
    """
    with tests.set_temporary_config("registry.encryption_key", Fernet.generate_key()):
        yield


@pytest.fixture(autouse=True)
def clear_registry():
    """
    Clear the flow registry after every test
    """
    yield
    prefect.core.registry.REGISTRY.clear()
