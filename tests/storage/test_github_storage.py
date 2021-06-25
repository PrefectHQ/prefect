from unittest.mock import MagicMock

import pytest

from prefect import context, Flow
from prefect.storage import GitHub

github = pytest.importorskip("github")


@pytest.fixture
def github_client(monkeypatch):
    client = MagicMock(spec=github.Github)
    monkeypatch.setattr("github.Github", MagicMock(return_value=client))
    repo = client.get_repo.return_value
    repo.default_branch = "main"
    repo.get_commit.return_value.sha = "mycommitsha"
    repo.get_contents.return_value.decoded_content = (
        b"from prefect import Flow\nflow=Flow('extra')\nflow=Flow('test')"
    )
    return client


def test_create_github_storage():
    storage = GitHub(repo="test/repo", path="flow.py")
    assert storage
    assert storage.logger


def test_create_github_storage_init_args():
    storage = GitHub(
        repo="test/repo",
        path="flow.py",
        ref="my_branch",
        base_url="https://some-url",
        secrets=["auth"],
    )
    assert storage
    assert storage.flows == dict()
    assert storage.repo == "test/repo"
    assert storage.path == "flow.py"
    assert storage.ref == "my_branch"
    assert storage.base_url == "https://some-url"
    assert storage.secrets == ["auth"]


def test_serialize_github_storage():
    storage = GitHub(repo="test/repo", path="flow.py", secrets=["auth"])
    serialized_storage = storage.serialize()

    assert serialized_storage["type"] == "GitHub"
    assert serialized_storage["repo"] == "test/repo"
    assert serialized_storage["path"] == "flow.py"
    assert serialized_storage["secrets"] == ["auth"]


@pytest.mark.parametrize(
    "secret_name,secret_arg", [("TEST", "TEST"), ("GITHUB_ACCESS_TOKEN", None)]
)
def test_github_access_token_secret(monkeypatch, secret_name, secret_arg):
    orig_github = github.Github
    mock_github = MagicMock(wraps=github.Github)
    monkeypatch.setattr("github.Github", mock_github)
    storage = GitHub(repo="test/repo", path="flow.py", access_token_secret=secret_arg)
    with context(secrets={secret_name: "TEST-VAL"}):
        client = storage._get_github_client()
    assert isinstance(client, orig_github)
    assert mock_github.call_args[0][0] == "TEST-VAL"


def test_github_access_token_errors_if_provided_and_not_found(monkeypatch):
    mock_github = MagicMock(wraps=github.Github)
    monkeypatch.setattr("github.Github", mock_github)
    storage = GitHub(repo="test/repo", path="flow.py", access_token_secret="MISSING")
    with context(secrets={}):
        with pytest.raises(Exception, match="MISSING"):
            storage._get_github_client()


def test_github_base_url(monkeypatch):
    orig_github = github.Github
    mock_github = MagicMock(wraps=github.Github)
    monkeypatch.setattr("github.Github", mock_github)
    storage = GitHub(
        repo="test/repo",
        path="flow.py",
        access_token_secret="TEST",
        base_url="https://some-url",
    )
    with context(secrets={"TEST": "TEST-VAL"}):
        client = storage._get_github_client()
    assert isinstance(client, orig_github)
    assert mock_github.call_args[1]["base_url"] == "https://some-url"


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
    github_client.get_repo.side_effect = github.UnknownObjectException(
        status=404, data={}, headers={}
    )

    storage = GitHub(repo="test/repo", path="flow.py")
    storage.add_flow(Flow("test"))

    with pytest.raises(github.UnknownObjectException):
        storage.get_flow("test")

    assert "Repo 'test/repo' not found." in caplog.text


@pytest.mark.parametrize("ref", [None, "myref"])
def test_get_flow_missing_ref(github_client, ref, caplog):
    repo = github_client.get_repo.return_value
    repo.get_commit.side_effect = github.UnknownObjectException(
        status=404, data={}, headers={}
    )

    storage = GitHub(repo="test/repo", path="flow.py", ref=ref)
    storage.add_flow(Flow("test"))

    ref = ref or "main"

    with pytest.raises(github.UnknownObjectException):
        storage.get_flow("test")

    assert f"Ref {ref!r} not found in repo 'test/repo'" in caplog.text


@pytest.mark.parametrize("ref", [None, "myref"])
def test_get_flow_missing_file(github_client, ref, caplog):
    repo = github_client.get_repo.return_value
    repo.get_contents.side_effect = github.UnknownObjectException(
        status=404, data={}, headers={}
    )

    storage = GitHub(repo="test/repo", path="flow.py", ref=ref)
    storage.add_flow(Flow("test"))

    ref = ref or "main"

    with pytest.raises(github.UnknownObjectException):
        storage.get_flow("test")

    assert f"File 'flow.py' not found in repo 'test/repo', ref {ref!r}" in caplog.text
