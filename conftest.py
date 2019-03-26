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


def pytest_addoption(parser):
    parser.addoption(
        "--airflow",
        action="store_true",
        dest="airflow",
        help="including this flag will attempt to ONLY run airflow compatibility tests",
    )
    parser.addoption(
        "--skip-formatting",
        action="store_true",
        dest="formatting",
        help="including this flag will skip all formatting tests",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "airflow: mark test to run only when --airflow flag is provided."
    )
    config.addinivalue_line(
        "markers",
        "formatting: mark test as formatting to skip when --skip-formatting flag is provided.",
    )


def pytest_runtest_setup(item):
    air_mark = item.get_closest_marker("airflow")

    # if a test IS marked as "airflow" and the airflow flag IS NOT set, skip it
    if air_mark is not None and item.config.getoption("--airflow") is False:
        pytest.skip(
            "Airflow tests skipped by default unless --airflow flag provided to pytest."
        )

    # if a test IS NOT marked as airflow and the airflow flag IS set, skip it
    elif air_mark is None and item.config.getoption("--airflow") is True:
        pytest.skip("Non-Airflow tests skipped because --airflow flag was provided.")

    formatting_mark = item.get_closest_marker("formatting")

    # if a test IS marked as "formatting" and the --skip-formatting flag IS set, skip it
    if (
        formatting_mark is not None
        and item.config.getoption("--skip-formatting") is True
    ):
        pytest.skip(
            "Formatting tests skipped because --skip-formatting flag was provided."
        )
