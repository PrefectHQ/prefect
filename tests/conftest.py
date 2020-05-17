import os
import sys
import tempfile
from unittest.mock import MagicMock

import pytest
from distributed import Client

import prefect
from prefect.engine.executors import DaskExecutor, LocalDaskExecutor, LocalExecutor
from prefect.utilities import configuration, debug


@pytest.fixture(autouse=True)
def logging_heartbeat():
    with configuration.set_temporary_config({"cloud.logging_heartbeat": 0.15}):
        yield


@pytest.fixture(autouse=True)
def prefect_home_dir():
    """
    Sets a temporary home directory
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmp = os.path.join(tmp, ".prefect")
        os.makedirs(tmp)
        with configuration.set_temporary_config({"home_dir": tmp}):
            yield tmp


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
        try:
            client.shutdown()
        except:
            pass


@pytest.fixture()
def local():
    "Local, immediate execution executor"
    yield LocalExecutor()


@pytest.fixture()
def sync():
    "Synchronous dask (not dask.distributed) executor"
    yield LocalDaskExecutor()


@pytest.fixture(scope="session")
def mproc():
    "Multi-processing executor"
    with Client(processes=True) as client:
        yield DaskExecutor(client.scheduler.address, local_processes=True)
        try:
            client.shutdown()
        except:
            pass


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


@pytest.fixture()
def patch_post(monkeypatch):
    """
    Patches `prefect.client.Client.post()` (and `graphql()`) to return the specified response.

    The return value of the fixture is a function that is called on the response to patch it.

    Typically, the response will contain up to two keys, `data` and `errors`.
    """

    def patch(response):
        post = MagicMock(return_value=MagicMock(json=MagicMock(return_value=response)))
        session = MagicMock()
        session.return_value.post = post
        monkeypatch.setattr("requests.Session", session)
        return post

    return patch


@pytest.fixture()
def patch_posts(monkeypatch):
    """
    Patches `prefect.client.Client.post()` (and `graphql()`) to return the specified sequence of responses.

    The return value of the fixture is a function that is called on the response to patch it.

    Typically, the response will contain up to two keys, `data` and `errors`.
    """

    def patch(responses):
        if not isinstance(responses, list):
            responses = [responses]

        resps = []
        for response in responses:
            resps.append(MagicMock(json=MagicMock(return_value=response)))

        post = MagicMock(side_effect=resps)
        session = MagicMock()
        session.return_value.post = post
        monkeypatch.setattr("requests.Session", session)
        return post

    return patch


@pytest.fixture()
def runner_token(monkeypatch):
    monkeypatch.setattr("prefect.agent.agent.Agent._verify_token", MagicMock())
    monkeypatch.setattr("prefect.agent.agent.Agent._register_agent", MagicMock())


@pytest.fixture()
def cloud_api():
    with prefect.utilities.configuration.set_temporary_config(
        {"cloud.api": "https://api.prefect.io", "backend": "cloud"}
    ):
        yield


@pytest.fixture()
def server_api():
    with prefect.utilities.configuration.set_temporary_config(
        {"cloud.api": "https:/localhost:4200", "backend": "server"}
    ):
        yield


# ----------------
# set up platform fixtures
# for every test that performs OS dependent logic
# ----------------


@pytest.fixture()
def linux_platform(monkeypatch):
    monkeypatch.setattr("sys.platform", "linux")


@pytest.fixture()
def windows_platform(monkeypatch):
    monkeypatch.setattr("sys.platform", "windows")


@pytest.fixture()
def macos_platform(monkeypatch):
    monkeypatch.setattr("sys.platform", "darwin")
