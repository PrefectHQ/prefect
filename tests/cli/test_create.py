from click.testing import CliRunner

from prefect.cli.create import create
from prefect.utilities.configuration import set_temporary_config


def test_create_init():
    runner = CliRunner()
    result = runner.invoke(create)
    assert result.exit_code == 0
    assert (
        "Create commands that refer to mutations of Prefect API metadata."
        in result.output
    )


def test_create_help():
    runner = CliRunner()
    result = runner.invoke(create, ["--help"])
    assert result.exit_code == 0
    assert (
        "Create commands that refer to mutations of Prefect API metadata."
        in result.output
    )


def test_create_project(patch_post):
    patch_post(dict(data=dict(create_project=dict(id="id"))))

    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        runner = CliRunner()
        result = runner.invoke(create, ["project", "test"])
        assert result.exit_code == 0
        assert "test created" in result.output


def test_create_project_error(patch_post):
    patch_post(dict(errors=dict(error="bad")))

    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        runner = CliRunner()
        result = runner.invoke(create, ["project", "test"])
        assert result.exit_code == 0
        assert "Error creating project" in result.output


def test_create_project_description(patch_post):
    patch_post(dict(data=dict(create_project=dict(id="id"))))

    with set_temporary_config(
        {"cloud.graphql": "http://my-cloud.foo", "cloud.auth_token": "secret_token"}
    ):
        runner = CliRunner()
        result = runner.invoke(create, ["project", "test", "-d", "description"])
        assert result.exit_code == 0
        assert "test created" in result.output
