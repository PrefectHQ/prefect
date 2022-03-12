import pytest
from unittest.mock import MagicMock

from prefect.backend import artifacts
from prefect import context


@pytest.fixture()
def client(monkeypatch):
    c = MagicMock(
        create_task_run_artifact=MagicMock(return_value="id"),
        update_task_run_artifact=MagicMock(return_value=True),
        delete_task_run_artifact=MagicMock(return_value=True),
    )
    monkeypatch.setattr("prefect.Client", MagicMock(return_value=c))
    yield c


def test_running_with_backend():
    with context(running_with_backend=False):
        assert artifacts._running_with_backend() is False


def test_create_link_artifact(client, running_with_backend):
    with context(task_run_id="trid"):
        artifact_id = artifacts.create_link_artifact(link="link_here")
        assert artifact_id == "id"
        assert client.create_task_run_artifact.called
        assert client.create_task_run_artifact.call_args[1] == {
            "data": {"link": "link_here"},
            "kind": "link",
            "task_run_id": "trid",
        }


def test_create_link_artifact_not_using_backend(client):
    with context(task_run_id="trid"):
        artifact_id = artifacts.create_link_artifact(link="link_here")
        assert artifact_id == None
        assert not client.create_task_run_artifact.called


def test_update_link_artifact(client, running_with_backend):
    artifacts.update_link_artifact(task_run_artifact_id="trid", link="link_here")
    assert client.update_task_run_artifact.called
    assert client.update_task_run_artifact.call_args[1] == {
        "data": {"link": "link_here"},
        "task_run_artifact_id": "trid",
    }


def test_update_link_artifact_not_using_backend(client):
    artifacts.update_link_artifact(task_run_artifact_id="trid", link="link_here")
    assert not client.update_task_run_artifact.called


def test_create_markdown_artifact(client, running_with_backend):
    with context(task_run_id="trid"):
        artifact_id = artifacts.create_markdown_artifact(markdown="markdown_here")
        assert artifact_id == "id"
        assert client.create_task_run_artifact.called
        assert client.create_task_run_artifact.call_args[1] == {
            "data": {"markdown": "markdown_here"},
            "kind": "markdown",
            "task_run_id": "trid",
        }


def test_create_markdown_artifact_not_using_backend(client):
    with context(task_run_id="trid"):
        artifact_id = artifacts.create_markdown_artifact(markdown="markdown_here")
        assert artifact_id == None
        assert not client.create_task_run_artifact.called


def test_update_markdown_artifact(client, running_with_backend):
    artifacts.update_markdown_artifact(
        task_run_artifact_id="trid", markdown="markdown_here"
    )
    assert client.update_task_run_artifact.called
    assert client.update_task_run_artifact.call_args[1] == {
        "data": {"markdown": "markdown_here"},
        "task_run_artifact_id": "trid",
    }


def test_update_markdown_artifact_not_using_backend(client):
    artifacts.update_markdown_artifact(
        task_run_artifact_id="trid", markdown="markdown_here"
    )
    assert not client.update_task_run_artifact.called


def test_delete_artifact(client, running_with_backend):
    artifacts.delete_artifact(task_run_artifact_id="trid")
    assert client.delete_task_run_artifact.called
    assert client.delete_task_run_artifact.call_args[1] == {
        "task_run_artifact_id": "trid",
    }


def test_delete_artifact_not_using_backend(client):
    artifacts.delete_artifact(task_run_artifact_id="trid")
    assert not client.delete_task_run_artifact.called
