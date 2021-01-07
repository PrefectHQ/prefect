from unittest.mock import MagicMock

import pytest

from prefect import context, Flow
from prefect.storage import Bitbucket


pytest.importorskip("atlassian")


def test_create_bitbucket_storage():
    storage = Bitbucket(project="PROJECT", repo="test-repo")
    assert storage
    assert storage.logger


def test_create_bitbucket_storage_init_args():
    storage = Bitbucket(
        project="PROJECT", repo="test-repo", path="test-flow.py", secrets=["auth"]
    )
    assert storage
    assert storage.project == "PROJECT"
    assert storage.repo == "test-repo"
    assert storage.path == "test-flow.py"
    assert storage.secrets == ["auth"]


def test_bitbucket_client_cloud(monkeypatch):
    bitbucket = MagicMock()
    monkeypatch.setattr("prefect.utilities.git.Bitbucket", bitbucket)

    storage = Bitbucket(project="PROJECT", repo="test-repo")

    credentials = "ACCESS_TOKEN"
    with context(secrets=dict(BITBUCKET_ACCESS_TOKEN=credentials)):
        bitbucket_client = storage._bitbucket_client

    assert bitbucket_client
    assert bitbucket.call_args[0][0] == "https://bitbucket.org"
    assert (
        bitbucket.call_args[1]["session"].headers["Authorization"]
        == "Bearer ACCESS_TOKEN"
    )


def test_bitbucket_client_server(monkeypatch):
    bitbucket = MagicMock()
    monkeypatch.setattr("prefect.utilities.git.Bitbucket", bitbucket)

    storage = Bitbucket(
        project="PROJECT",
        repo="test-repo",
        host="http://localhost:1234",
    )

    credentials = "ACCESS_TOKEN"
    with context(secrets=dict(BITBUCKET_ACCESS_TOKEN=credentials)):
        bitbucket_client = storage._bitbucket_client

    assert bitbucket_client
    assert bitbucket.call_args[0][0] == "http://localhost:1234"
    assert (
        bitbucket.call_args[1]["session"].headers["Authorization"]
        == "Bearer ACCESS_TOKEN"
    )


def test_add_flow_to_bitbucket_storage():
    storage = Bitbucket(project="PROJECT", repo="test-repo", path="test-flow.py")

    f = Flow("test")
    assert f.name not in storage
    assert storage.add_flow(f) == "test-flow.py"
    assert f.name in storage

    with pytest.raises(ValueError) as ex:
        storage.add_flow(f)

    assert "Name conflict" in str(ex.value)


def test_get_flow_bitbucket(monkeypatch):
    f = Flow("test")

    bitbucket = MagicMock()
    monkeypatch.setattr("prefect.utilities.git.Bitbucket", bitbucket)

    monkeypatch.setattr(
        "prefect.storage.bitbucket.extract_flow_from_file",
        MagicMock(return_value=f),
    )

    with pytest.raises(ValueError) as ex:
        storage = Bitbucket(project="PROJECT", repo="test-repo")
        storage.get_flow()

    assert "No flow location provided" in str(ex.value)

    storage = Bitbucket(project="PROJECT", repo="test-repo", path="test-flow.py")

    assert f.name not in storage
    flow_location = storage.add_flow(f)

    new_flow = storage.get_flow(flow_location)
    assert new_flow.run()
