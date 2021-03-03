from unittest.mock import MagicMock

import pytest

pytest.importorskip("boto3")
pytest.importorskip("botocore")

from prefect import context, Flow
from prefect.storage import CodeCommit
from prefect.utilities.aws import _CLIENT_CACHE


@pytest.fixture(autouse=True)
def clear_boto3_cache():
    _CLIENT_CACHE.clear()


def test_create_codecommit_storage():
    storage = CodeCommit(repo="test/repo")
    assert storage
    assert storage.logger


def test_create_codecommit_storage_init_args():
    storage = CodeCommit(
        repo="test/repo",
        path="flow.py",
        commit="master",
        client_options={"endpoint_url": "http://some-endpoint", "use_ssl": False},
        secrets=["auth"],
    )
    assert storage
    assert storage.flows == dict()
    assert storage.repo == "test/repo"
    assert storage.path == "flow.py"
    assert storage.commit == "master"
    assert storage.client_options == {
        "endpoint_url": "http://some-endpoint",
        "use_ssl": False,
    }
    assert storage.secrets == ["auth"]


def test_serialize_codecommit_storage():
    storage = CodeCommit(
        repo="test/repo",
        path="flow.py",
        commit="master",
        client_options={"endpoint_url": "http://some-endpoint", "use_ssl": False},
        secrets=["auth"],
    )
    serialized_storage = storage.serialize()

    assert serialized_storage["type"] == "CodeCommit"
    assert serialized_storage["repo"] == "test/repo"
    assert serialized_storage["path"] == "flow.py"
    assert serialized_storage["commit"] == "master"
    assert serialized_storage["client_options"] == {
        "endpoint_url": "http://some-endpoint",
        "use_ssl": False,
    }
    assert serialized_storage["secrets"] == ["auth"]


def test_codecommit_client_property(monkeypatch):
    client = MagicMock()
    boto3 = MagicMock(client=MagicMock(return_value=client))
    monkeypatch.setattr("boto3.client", boto3)

    storage = CodeCommit(
        repo="test/repo",
        client_options={"endpoint_url": "http://some-endpoint", "use_ssl": False},
    )

    credentials = dict(
        ACCESS_KEY="id", SECRET_ACCESS_KEY="secret", SESSION_TOKEN="session"
    )
    with context(secrets=dict(AWS_CREDENTIALS=credentials)):
        boto3_client = storage._boto3_client
    assert boto3_client
    boto3.assert_called_with(
        "codecommit",
        aws_access_key_id="id",
        aws_secret_access_key="secret",
        aws_session_token="session",
        region_name=None,
        endpoint_url="http://some-endpoint",
        use_ssl=False,
    )


def test_add_flow_to_codecommit_storage():
    storage = CodeCommit(repo="test/repo", path="flow.py", commit="master")

    f = Flow("test")
    assert f.name not in storage
    assert storage.add_flow(f) == "flow.py"
    assert f.name in storage


def test_add_flow_to_codecommit_already_added():
    storage = CodeCommit(repo="test/repo", path="flow.py", commit="master")

    f = Flow("test")
    assert f.name not in storage
    assert storage.add_flow(f) == "flow.py"
    assert f.name in storage

    with pytest.raises(ValueError):
        storage.add_flow(f)


def test_get_flow_codecommit(monkeypatch):
    client = MagicMock()
    d = {"fileContent": b'import prefect; flow = prefect.Flow("test")'}
    client.__getitem__.side_effect = d.__getitem__
    boto3 = MagicMock(get_file=MagicMock(return_value=client))
    monkeypatch.setattr("prefect.storage.CodeCommit._boto3_client", boto3)

    f = Flow("test")

    extract_flow_from_file = MagicMock(return_value=f)
    monkeypatch.setattr(
        "prefect.storage.codecommit.extract_flow_from_file",
        extract_flow_from_file,
    )

    storage = CodeCommit(repo="test/repo", path="flow", commit="master")

    assert f.name not in storage
    storage.add_flow(f)

    new_flow = storage.get_flow(f.name)
    assert extract_flow_from_file.call_args[1]["flow_name"] == f.name
    assert new_flow.run()
