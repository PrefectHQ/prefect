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


def test_create_project(patch_post, cloud_api):
    patch_post(dict(data=dict(create_project=dict(id="id"))))

    runner = CliRunner()
    result = runner.invoke(create, ["project", "test"])
    assert result.exit_code == 0
    assert "test created" in result.output


def test_create_project_error(patch_post):
    patch_post(dict(errors=[dict(error={})]))

    runner = CliRunner()
    result = runner.invoke(create, ["project", "test"])
    assert result.exit_code == 0
    assert "Error creating project" in result.output


def test_create_project_description(patch_post, cloud_api):
    patch_post(dict(data=dict(create_project=dict(id="id"))))

    runner = CliRunner()
    result = runner.invoke(create, ["project", "test", "-d", "description"])
    assert result.exit_code == 0
    assert "test created" in result.output


def test_create_project_skip_if_exists(patch_posts):
    patch_posts(
        [
            {
                "errors": [
                    {"message": "Uniqueness violation.", "path": ["create_project"]}
                ],
                "data": {"create_project": None},
            },
            {"data": {"project": [{"id": "proj-id"}]}},
        ]
    )

    runner = CliRunner()
    result = runner.invoke(create, ["project", "test", "--skip-if-exists"])
    assert result.exit_code == 0
    assert "test created" in result.output
