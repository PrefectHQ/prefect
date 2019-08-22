from unittest.mock import MagicMock

from click.testing import CliRunner

from prefect.cli.create import create
from prefect.utilities.configuration import set_temporary_config


def test_create_init():
    runner = CliRunner()
    result = runner.invoke(create)
    assert result.exit_code == 0
    assert (
        "Create commands that refer to mutations of Prefect Cloud metadata."
        in result.output
    )


def test_create_help():
    runner = CliRunner()
    result = runner.invoke(create, ["--help"])
    assert result.exit_code == 0
    assert (
        "Create commands that refer to mutations of Prefect Cloud metadata."
        in result.output
    )


def test_create_project(monkeypatch):

    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(return_value=dict(data=dict(createProject=dict(id="id"))))
        )
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        runner = CliRunner()
        result = runner.invoke(create, ["project", "--name", "test"])
        assert result.exit_code == 0
        assert "test created" in result.output


def test_create_project_error(monkeypatch):

    post = MagicMock(
        return_value=MagicMock(
            json=MagicMock(return_value=dict(errors=dict(error="bad")))
        )
    )
    session = MagicMock()
    session.return_value.post = post
    monkeypatch.setattr("requests.Session", session)

    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        runner = CliRunner()
        result = runner.invoke(create, ["project", "--name", "test"])
        assert result.exit_code == 0
        assert "Error creating project" in result.output
