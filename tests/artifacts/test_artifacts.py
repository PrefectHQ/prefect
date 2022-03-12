import pytest
from unittest.mock import MagicMock

from prefect import artifacts, context


@pytest.fixture()
def client(monkeypatch):
    c = MagicMock(
        create_task_run_artifact=MagicMock(return_value="id"),
        update_task_run_artifact=MagicMock(return_value=True),
        delete_task_run_artifact=MagicMock(return_value=True),
    )
    monkeypatch.setattr("prefect.Client", MagicMock(return_value=c))
    yield c


def test_old_create_link(client, running_with_backend):
    with context(task_run_id="trid"):
        with pytest.warns(
            UserWarning,
            match="has been moved to `prefect.backend.create_link_artifact`",
        ):
            artifact_id = artifacts.create_link(link="link_here")
        assert artifact_id == "id"
        assert client.create_task_run_artifact.called
        assert client.create_task_run_artifact.call_args[1] == {
            "data": {"link": "link_here"},
            "kind": "link",
            "task_run_id": "trid",
        }


def test_old_update_link(client, running_with_backend):
    with pytest.warns(
        UserWarning,
        match="has been moved to `prefect.backend.update_link_artifact`",
    ):
        artifacts.update_link(task_run_artifact_id="trid", link="link_here")

    assert client.update_task_run_artifact.called
    assert client.update_task_run_artifact.call_args[1] == {
        "data": {"link": "link_here"},
        "task_run_artifact_id": "trid",
    }


def test_old_create_markdown(client, running_with_backend):
    with context(task_run_id="trid"):
        with pytest.warns(
            UserWarning,
            match="has been moved to `prefect.backend.create_markdown_artifact`",
        ):
            artifact_id = artifacts.create_markdown(markdown="markdown_here")
        assert artifact_id == "id"
        assert client.create_task_run_artifact.called
        assert client.create_task_run_artifact.call_args[1] == {
            "data": {"markdown": "markdown_here"},
            "kind": "markdown",
            "task_run_id": "trid",
        }


def test_old_update_markdown(client, running_with_backend):
    with pytest.warns(
        UserWarning,
        match="has been moved to `prefect.backend.update_markdown_artifact`",
    ):
        artifacts.update_markdown(task_run_artifact_id="trid", markdown="markdown_here")
    assert client.update_task_run_artifact.called
    assert client.update_task_run_artifact.call_args[1] == {
        "data": {"markdown": "markdown_here"},
        "task_run_artifact_id": "trid",
    }


def test_old_delete_artifact(client, running_with_backend):
    with pytest.warns(
        UserWarning,
        match="has been moved to `prefect.backend.delete_artifact`",
    ):
        artifacts.delete_artifact(task_run_artifact_id="trid")
    assert client.delete_task_run_artifact.called
    assert client.delete_task_run_artifact.call_args[1] == {
        "task_run_artifact_id": "trid",
    }
