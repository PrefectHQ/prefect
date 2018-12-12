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
        yield


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
        yield


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
    if sys.version_info < (3, 5) and request.param in ["mthread", "mproc"]:
        request.applymarker(
            pytest.mark.xfail(
                run=False,
                reason="dask.distributed does not officially support Python 3.4",
            )
        )
    return _switch(request.param)


def pytest_addoption(parser):
    parser.addoption(
        "--airflow",
        action="store_true",
        dest="airflow",
        help="including this flag will attempt to ONLY run airflow compatibility tests",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "airflow: mark test to run only when --airflow flag is provided."
    )


def pytest_runtest_setup(item):
    mark = item.get_marker("airflow")

    # if a test IS marked as "airflow" and the airflow flag IS NOT set, skip it
    if mark is not None and item.config.getoption("--airflow") is False:
        pytest.skip(
            "Airflow tests skipped by default unless --airflow flag provided to pytest."
        )

    # if a test IS NOT marked as airflow and the airflow flag IS set, skip it
    elif mark is None and item.config.getoption("--airflow") is True:
        pytest.skip("Non-Airflow tests skipped because --airflow flag was provided.")
