import pytest
from cryptography.fernet import Fernet
from distributed import Client

import prefect
from prefect.engine.executors import DaskExecutor, LocalExecutor, SynchronousExecutor
from prefect.utilities import tests


# ----------------
# set up executor fixtures
# so that we don't have to spin up / tear down a dask cluster
# for every test that needs a dask executor
# ----------------
@pytest.fixture(scope="module")
def threaded():
    "Multi-threaded executor"
    with Client(processes=False) as client:
        yield DaskExecutor(client.scheduler.address)


@pytest.fixture(scope="module")
def local():
    "Local, immediate execution executor"
    yield LocalExecutor()


@pytest.fixture(scope="module")
def sync():
    "Synchronous dask (not dask.distributed) executor"
    yield SynchronousExecutor()


@pytest.fixture(scope="module")
def multi():
    "Multi-threaded executor"
    with Client(processes=True) as client:
        yield DaskExecutor(client.scheduler.address, processes=True)


@pytest.fixture()
def _switch(threaded, local, sync, multi):
    """
    A construct needed so we can parametrize the executor fixture.

    This isn't straightforward since each executor needs to be initialized
    in slightly different ways.
    """
    execs = dict(threaded=threaded, local=local, sync=sync, multi=multi)
    return lambda e: execs[e]


@pytest.fixture()
def executor(request, _switch):
    """
    The actual fixture that should be used in testing.
    Parametrize your test by decorating:
        ```
        @pytest.mark.parametrize(
            "executor", ["local", "sync", "multi", "threaded"], indirect=True
        )
        ```
    or with some subset of executors that you want to use.
    """
    return _switch(request.param)


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
