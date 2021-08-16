from unittest.mock import MagicMock

import pytest

from prefect import context, Flow
from prefect.storage import Bitbucket


atlassian = pytest.importorskip("atlassian")


def test_create_bitbucket_storage():
    storage = Bitbucket(project="PROJECT", repo="test-repo")
    assert storage
    assert storage.logger


def test_create_bitbucket_storage_init_args():
    storage = Bitbucket(
        project="PROJECT",
        repo="test-repo",
        workspace="test-workspace",
        path="test-flow.py",
        secrets=["auth"],
    )
    assert storage
    assert storage.project == "PROJECT"
    assert storage.repo == "test-repo"
    assert storage.workspace == "test-workspace"
    assert storage.path == "test-flow.py"
    assert storage.secrets == ["auth"]


@pytest.mark.parametrize(
    "secret_name,secret_arg", [("TEST", "TEST"), ("BITBUCKET_ACCESS_TOKEN", None)]
)
@pytest.mark.parametrize("host", [None, "https://localhost:1234"])
def test_get_bitbucket_server_client(monkeypatch, secret_name, secret_arg, host):
    orig_bitbucket = atlassian.Bitbucket
    mock_bitbucket = MagicMock(wraps=atlassian.Bitbucket)
    monkeypatch.setattr("atlassian.Bitbucket", mock_bitbucket)
    storage = Bitbucket(
        project="test",
        repo="test/repo",
        path="flow.py",
        host=host,
        access_token_secret=secret_arg,
    )
    with context(secrets={secret_name: "TEST-VAL"}):
        client = storage._get_bitbucket_server_client()
    assert isinstance(client, orig_bitbucket)
    assert mock_bitbucket.call_args[0][0] == (host or "https://bitbucket.org")
    assert (
        mock_bitbucket.call_args[1]["session"].headers["Authorization"]
        == "Bearer TEST-VAL"
    )


def test_get_bitbucket_server_client_errors_if_secret_provided_and_not_found(
    monkeypatch,
):
    mock_bitbucket = MagicMock(wraps=atlassian.Bitbucket)
    monkeypatch.setattr("atlassian.Bitbucket", mock_bitbucket)
    storage = Bitbucket(
        project="test", repo="test/repo", path="flow.py", access_token_secret="MISSING"
    )
    with context(secrets={}):
        with pytest.raises(Exception, match="MISSING"):
            storage._get_bitbucket_server_client()


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
    monkeypatch.setattr("atlassian.Bitbucket", bitbucket)

    extract_flow_from_file = MagicMock(return_value=f)
    monkeypatch.setattr(
        "prefect.storage.bitbucket.extract_flow_from_file", extract_flow_from_file
    )

    storage = Bitbucket(project="PROJECT", repo="test-repo", path="test-flow.py")

    assert f.name not in storage
    storage.add_flow(f)

    new_flow = storage.get_flow(f.name)
    assert extract_flow_from_file.call_args[1]["flow_name"] == f.name
    assert new_flow.run()


def test_get_flow_bitbucket_cloud(monkeypatch):
    f = Flow("test")

    bitbucket = MagicMock()
    monkeypatch.setattr("atlassian.bitbucket.cloud.Cloud", bitbucket)

    extract_flow_from_file = MagicMock(return_value=f)
    monkeypatch.setattr(
        "prefect.storage.bitbucket.extract_flow_from_file", extract_flow_from_file
    )

    storage = Bitbucket(
        project="PROJECT",
        repo="test-repo",
        workspace="test-workspace",
        path="test-flow.py",
        ref="ac75ea3fa670e37bb351f27df4753e8821cad015",
    )

    assert f.name not in storage
    storage.add_flow(f)

    new_flow = storage.get_flow(f.name)
    assert extract_flow_from_file.call_args[1]["flow_name"] == f.name
    assert new_flow.run()
