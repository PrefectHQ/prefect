import pytest
import sys
from cryptography.fernet import Fernet


import prefect
from prefect.engine.executors import LocalExecutor, SynchronousExecutor
from prefect.utilities import tests

if sys.version_info >= (3, 5):
    from prefect.engine.executors import DaskExecutor
    from distributed import Client

# ----------------
# set up executor fixtures
# so that we don't have to spin up / tear down a dask cluster
# for every test that needs a dask executor
# ----------------
@pytest.fixture(scope="module")
def mthread():
    "Multi-threaded executor"
    if sys.version_info >= (3, 5):
        with Client(processes=False) as client:
            yield DaskExecutor(client.scheduler.address)
    else:
        pytest.skip("dask.distributed does not support Python 3.4")


@pytest.fixture(scope="module")
def local():
    "Local, immediate execution executor"
    yield LocalExecutor()


@pytest.fixture(scope="module")
def sync():
    "Synchronous dask (not dask.distributed) executor"
    yield SynchronousExecutor()


@pytest.fixture(scope="module")
def mproc():
    "Multi-processing executor"
    if sys.version_info >= (3, 5):
        with Client(processes=True) as client:
            yield DaskExecutor(client.scheduler.address, processes=True)
    else:
        pytest.skip("dask.distributed does not support Python 3.4")


@pytest.fixture()
def _switch(mthread, local, sync, mproc):
    """
    A construct needed so we can parametrize the executor fixture.

    This isn't straightforward since each executor needs to be initialized
    in slightly different ways.
    """
    execs = dict(mthread=mthread, local=local, sync=sync, mproc=mproc)
    return lambda e: execs[e]


@pytest.fixture()
def executor(request, _switch):
    """
    The actual fixture that should be used in testing.
    Parametrize your test by decorating:
        ```
        @pytest.mark.parametrize(
            "executor", ["local", "sync", "mproc", "mthread"], indirect=True
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
