from unittest.mock import MagicMock

import pytest

from prefect import context, Flow
from prefect.environments.storage import GitHub

pytest.importorskip("github")


def test_create_github_storage():
    storage = GitHub(repo="test/repo")
    assert storage
    assert storage.logger


def test_create_github_storage_init_args():
    storage = GitHub(
        repo="test/repo", path="flow.py", ref="my_branch", secrets=["auth"]
    )
    assert storage
    assert storage.flows == dict()
    assert storage.repo == "test/repo"
    assert storage.path == "flow.py"
    assert storage.ref == "my_branch"
    assert storage.secrets == ["auth"]


def test_serialize_github_storage():
    storage = GitHub(repo="test/repo", path="flow.py", secrets=["auth"])
    serialized_storage = storage.serialize()

    assert serialized_storage["type"] == "GitHub"
    assert serialized_storage["repo"] == "test/repo"
    assert serialized_storage["path"] == "flow.py"
    assert serialized_storage["secrets"] == ["auth"]


def test_github_client_property(monkeypatch):
    github = MagicMock()
    monkeypatch.setattr("prefect.utilities.git.Github", github)

    storage = GitHub(repo="test/repo")

    credentials = "ACCESS_TOKEN"
    with context(secrets=dict(GITHUB_ACCESS_TOKEN=credentials)):
        github_client = storage._github_client
    assert github_client
    github.assert_called_with("ACCESS_TOKEN")


def test_add_flow_to_github_storage():
    storage = GitHub(repo="test/repo", path="flow.py")

    f = Flow("test")
    assert f.name not in storage
    assert storage.add_flow(f) == "flow.py"
    assert f.name in storage


def test_add_flow_to_github_already_added():
    storage = GitHub(repo="test/repo", path="flow.py")

    f = Flow("test")
    assert f.name not in storage
    assert storage.add_flow(f) == "flow.py"
    assert f.name in storage

    with pytest.raises(ValueError):
        storage.add_flow(f)


def test_get_flow_github(monkeypatch):
    f = Flow("test")

    github = MagicMock()
    monkeypatch.setattr("prefect.utilities.git.Github", github)

    monkeypatch.setattr(
        "prefect.environments.storage.github.extract_flow_from_file",
        MagicMock(return_value=f),
    )

    with pytest.raises(ValueError):
        storage = GitHub(repo="test/repo")
        storage.get_flow()

    storage = GitHub(repo="test/repo", path="flow")

    assert f.name not in storage
    flow_location = storage.add_flow(f)

    new_flow = storage.get_flow(flow_location, ref="my_branch")
    assert new_flow.run()
