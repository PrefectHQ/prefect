from unittest.mock import MagicMock

import pytest

from prefect import context, Flow
from prefect.environments.storage import GitLab


pytest.importorskip("gitlab")


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


def test_gitlab_client_cloud(monkeypatch):
    gitlab = MagicMock()
    monkeypatch.setattr("prefect.utilities.git.Gitlab", gitlab)

    storage = GitLab(repo="test/repo")

    credentials = "ACCESS_TOKEN"
    with context(secrets=dict(GITLAB_ACCESS_TOKEN=credentials)):
        gitlab_client = storage._gitlab_client

    assert gitlab_client
    gitlab.assert_called_with("https://gitlab.com", private_token="ACCESS_TOKEN")


def test_gitlab_client_server(monkeypatch):
    gitlab = MagicMock()
    monkeypatch.setattr("prefect.utilities.git.Gitlab", gitlab)

    storage = GitLab(repo="test/repo", host="http://localhost:1234")

    credentials = "ACCESS_TOKEN"
    with context(secrets=dict(GITLAB_ACCESS_TOKEN=credentials)):
        gitlab_client = storage._gitlab_client

    assert gitlab_client
    gitlab.assert_called_with("http://localhost:1234", private_token="ACCESS_TOKEN")


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
    monkeypatch.setattr("prefect.utilities.git.Gitlab", gitlab)

    monkeypatch.setattr(
        "prefect.environments.storage.gitlab.extract_flow_from_file",
        MagicMock(return_value=f),
    )

    with pytest.raises(ValueError) as ex:
        storage = GitLab(repo="test/repo")
        storage.get_flow()

    assert "No flow location provided" in str(ex.value)

    storage = GitLab(repo="test/repo", path="flow.py")

    assert f.name not in storage
    flow_location = storage.add_flow(f)

    new_flow = storage.get_flow(flow_location)
    assert new_flow.run()
