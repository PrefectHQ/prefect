from unittest.mock import MagicMock

import pytest

from prefect import context, Flow
from prefect.storage import GitLab


gitlab = pytest.importorskip("gitlab")


def test_create_gitlab_storage():
    storage = GitLab(repo="test/repo")
    assert storage
    assert storage.logger


def test_create_gitlab_storage_init_args():
    storage = GitLab(repo="test/repo", path="flow.py", secrets=["auth"])
    assert storage
    assert storage.flows == dict()
    assert storage.repo == "test/repo"
    assert storage.path == "flow.py"
    assert storage.secrets == ["auth"]


@pytest.mark.parametrize(
    "secret_name,secret_arg", [("TEST", "TEST"), ("GITLAB_ACCESS_TOKEN", None)]
)
@pytest.mark.parametrize("host", [None, "https://localhost:1234"])
def test_get_gitlab_client(monkeypatch, secret_name, secret_arg, host):
    orig_gitlab = gitlab.Gitlab
    mock_gitlab = MagicMock(wraps=gitlab.Gitlab)
    monkeypatch.setattr("gitlab.Gitlab", mock_gitlab)
    storage = GitLab(
        repo="test/repo", path="flow.py", host=host, access_token_secret=secret_arg
    )
    with context(secrets={secret_name: "TEST-VAL"}):
        client = storage._get_gitlab_client()
    assert isinstance(client, orig_gitlab)
    assert mock_gitlab.call_args[0][0] == (host or "https://gitlab.com")
    assert mock_gitlab.call_args[1]["private_token"] == "TEST-VAL"


def test_get_gitlab_client_errors_if_secret_provided_and_not_found(monkeypatch):
    mock_gitlab = MagicMock(wraps=gitlab.Gitlab)
    monkeypatch.setattr("gitlab.Gitlab", mock_gitlab)
    storage = GitLab(repo="test/repo", path="flow.py", access_token_secret="MISSING")
    with context(secrets={}):
        with pytest.raises(Exception, match="MISSING"):
            storage._get_gitlab_client()


def test_add_flow_to_gitlab_storage():
    storage = GitLab(repo="test/repo", path="flow.py")

    f = Flow("test")
    assert f.name not in storage
    assert storage.add_flow(f) == "flow.py"
    assert f.name in storage


def test_add_flow_to_gitlab_already_added():
    storage = GitLab(repo="test/repo", path="flow.py")

    f = Flow("test")
    assert f.name not in storage
    assert storage.add_flow(f) == "flow.py"
    assert f.name in storage

    with pytest.raises(ValueError) as ex:
        storage.add_flow(f)

    assert "Name conflict" in str(ex.value)


def test_get_flow_gitlab(monkeypatch):
    f = Flow("test")

    gitlab = MagicMock()
    monkeypatch.setattr("gitlab.Gitlab", gitlab)

    extract_flow_from_file = MagicMock(return_value=f)
    monkeypatch.setattr(
        "prefect.storage.gitlab.extract_flow_from_file",
        extract_flow_from_file,
    )

    storage = GitLab(repo="test/repo", path="flow.py")

    assert f.name not in storage
    storage.add_flow(f)

    new_flow = storage.get_flow(f.name)
    assert extract_flow_from_file.call_args[1]["flow_name"] == f.name
    assert new_flow.run()
