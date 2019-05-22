import sys

import pytest
from cryptography.fernet import Fernet
from distributed import Client

import prefect
from prefect.engine.executors import DaskExecutor, LocalExecutor, SynchronousExecutor
from prefect.utilities import debug


# ----------------
# set up executor fixtures
# so that we don't have to spin up / tear down a dask cluster
# for every test that needs a dask executor
# ----------------
@pytest.fixture(scope="session")
def mthread():
    "Multi-threaded executor"
    with Client(processes=False) as client:
        yield DaskExecutor(client.scheduler.address)


@pytest.fixture()
def local():
    "Local, immediate execution executor"
    yield LocalExecutor()


@pytest.fixture()
def sync():
    "Synchronous dask (not dask.distributed) executor"
    yield SynchronousExecutor()


@pytest.fixture(scope="session")
def mproc():
    "Multi-processing executor"
    with Client(processes=True) as client:
        yield DaskExecutor(client.scheduler.address, local_processes=True)


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
