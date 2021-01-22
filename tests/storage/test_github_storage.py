from unittest.mock import MagicMock

import pytest

from prefect import context, Flow
from prefect.storage import GitHub

github = pytest.importorskip("github")


def test_create_github_storage():
    storage = GitHub(repo="test/repo", path="flow.py")
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

    storage = GitHub(repo="test/repo", path="flow.py")

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


@pytest.fixture
def github_client(monkeypatch):
    client = MagicMock(spec=github.Github)
    monkeypatch.setattr("prefect.utilities.git.Github", MagicMock(return_value=client))
    repo = client.get_repo.return_value
    repo.default_branch = "main"
    repo.get_commit.return_value.sha = "mycommitsha"
    repo.get_contents.return_value.decoded_content = (
        b"from prefect import Flow\nflow=Flow('extra')\nflow=Flow('test')"
    )
    return client


@pytest.mark.parametrize("ref", [None, "myref"])
def test_get_flow(github_client, ref, caplog):
    storage = GitHub(repo="test/repo", path="flow.py", ref=ref)
    storage.add_flow(Flow("test"))

    f = storage.get_flow("test")
    assert github_client.get_repo.call_args[0][0] == "test/repo"
    repo = github_client.get_repo.return_value

    assert repo.get_commit.call_args[0][0] == ref or "main"
    assert repo.get_contents.call_args[0][0] == "flow.py"
    assert repo.get_contents.call_args[1]["ref"] == "mycommitsha"

    assert f.name == "test"
    state = f.run()
    assert state.is_successful()

    msg = "Downloading flow from GitHub storage - repo: 'test/repo', path: 'flow.py'"
    if ref is not None:
        msg += f", ref: {ref!r}"
    assert msg in caplog.text
    assert "Flow successfully downloaded. Using commit: mycommitsha" in caplog.text


def test_get_flow_missing_repo(github_client, caplog):
    github_client.get_repo.side_effect = github.UnknownObjectException(404, {})

    storage = GitHub(repo="test/repo", path="flow.py")
    storage.add_flow(Flow("test"))

    with pytest.raises(github.UnknownObjectException):
        storage.get_flow("test")

    assert "Repo 'test/repo' not found." in caplog.text


@pytest.mark.parametrize("ref", [None, "myref"])
def test_get_flow_missing_ref(github_client, ref, caplog):
    repo = github_client.get_repo.return_value
    repo.get_commit.side_effect = github.UnknownObjectException(404, {})

    storage = GitHub(repo="test/repo", path="flow.py", ref=ref)
    storage.add_flow(Flow("test"))

    ref = ref or "main"

    with pytest.raises(github.UnknownObjectException):
        storage.get_flow("test")

    assert f"Ref {ref!r} not found in repo 'test/repo'" in caplog.text


@pytest.mark.parametrize("ref", [None, "myref"])
def test_get_flow_missing_file(github_client, ref, caplog):
    repo = github_client.get_repo.return_value
    repo.get_contents.side_effect = github.UnknownObjectException(404, {})

    storage = GitHub(repo="test/repo", path="flow.py", ref=ref)
    storage.add_flow(Flow("test"))

    ref = ref or "main"

    with pytest.raises(github.UnknownObjectException):
        storage.get_flow("test")

    assert f"File 'flow.py' not found in repo 'test/repo', ref {ref!r}" in caplog.text
